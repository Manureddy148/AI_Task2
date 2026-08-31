#!/usr/bin/env python3
"""Replay every row of the bench log against the B1 spec-only prediction.

For each row, predict:
  - peak KV utilization  = min(n, capacity) * (prompt+gen) * KV_BYTES_PER_TOKEN / KV_BUDGET
  - preempted sequences  = max(0, n - capacity)
    where capacity = floor(KV_BUDGET / ((prompt+gen) * KV_BYTES_PER_TOKEN))
and compare against the logged kv_cache_util / preempted_seqs columns.

Also decompose reported_tok_s (it equals (prompt+gen)*n / wall on every row — the
harness counts PREFILL tokens as throughput), derive honest generation goodput,
and close the mechanism with a one-parameter bandwidth roofline.

Usage: python reconcile.py [--log PATH]   (default: bench_log.csv via _paths.py)
Every printed number is computed from the loaded rows and kv_math constants —
nothing numeric is retyped as literal text, so live edits to the spec or the log
flow through.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # submission/ -> _paths
from _paths import find_starter_kit
from kv_math import (KV_BYTES_PER_TOKEN, KV_BUDGET, WEIGHT_BYTES, GPU_MEM_UTIL,
                     GPU_BYTES, OVERHEAD_BYTES)

BANDWIDTH = 300e9      # bytes/s, model_spec.md peak
FLOPS = 121e12         # fp16 dense peak, model_spec.md
PARAMS = 4.2e9


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]


def pick(rows, batch, plen):
    """Select exactly one row by (batch_size, prompt_len); fail loudly otherwise."""
    matches = [r for r in rows if r["batch_size"] == batch and r["prompt_len"] == plen]
    assert len(matches) == 1, f"expected 1 row for batch={batch}, prompt={plen}; got {len(matches)}"
    return matches[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=None, help="bench log CSV path")
    args = ap.parse_args()
    log_path = args.log or (find_starter_kit() / "bench" / "bench_log.csv")
    rows = load_rows(log_path)

    sys.stdout.reconfigure(encoding="utf-8")
    out = []
    p = out.append

    p(f"== 1. KV utilization & preemption: prediction vs log (all {len(rows)} rows) ==")
    p(f"{'n':>3} {'p_len':>6} {'gen':>5} | {'util_log':>8} {'util_pred':>9} | {'pre_log':>7} {'pre_pred':>8}")
    max_util_err = 0.0
    pre_exact = True
    for r in rows:
        n, plen, gen = int(r["batch_size"]), int(r["prompt_len"]), int(r["gen_len"])
        seq_bytes = (plen + gen) * KV_BYTES_PER_TOKEN
        capacity = math.floor(KV_BUDGET / seq_bytes)
        pred_pre = max(0, n - capacity)
        pred_util = min(n, capacity) * seq_bytes / KV_BUDGET
        max_util_err = max(max_util_err, abs(pred_util - r["kv_cache_util"]))
        pre_exact &= pred_pre == int(r["preempted_seqs"])
        p(f"{n:>3} {plen:>6} {gen:>5} | {r['kv_cache_util']:>8.2f} {pred_util:>9.4f} | "
          f"{int(r['preempted_seqs']):>7} {pred_pre:>8}")
    cap4096 = KV_BUDGET / (4096 * KV_BYTES_PER_TOKEN)
    p(f"capacity at 4096 tok/seq: {math.floor(cap4096)} seqs (exact: {cap4096:.2f})")
    p(f"max |util_pred - util_log| = {max_util_err:.4f} (log has 2 decimals -> perfect within rounding)"
      if max_util_err <= 0.005 else f"max util error {max_util_err:.4f} — INVESTIGATE")
    p("preempted_seqs predicted exactly on every row: " + str(pre_exact))
    p("")

    p(f"== 2. What reported_tok_s actually counts (all {len(rows)} rows) ==")
    p(f"{'n':>3} {'p_len':>6} | {'reported':>9} {'(p+g)*n/wall':>13} {'gen*n/wall':>11}")
    worst = 0.0
    for r in rows:
        n, plen, gen = int(r["batch_size"]), int(r["prompt_len"]), int(r["gen_len"])
        total_rate = (plen + gen) * n / r["wall_clock_s"]
        goodput = gen * n / r["wall_clock_s"]
        worst = max(worst, abs(total_rate - r["reported_tok_s"]) / r["reported_tok_s"])
        p(f"{n:>3} {plen:>6} | {r['reported_tok_s']:>9.1f} {total_rate:>13.1f} {goodput:>11.1f}")
    p(f"max relative gap between reported_tok_s and (prompt+gen)*n/wall: {100*worst:.3f}%")
    p("-> reported_tok_s counts PREFILL tokens as throughput; goodput (gen only) is the honest column")
    p("")

    p("== 3. B3: honest goodput of the batch-24 long-prompt row ==")
    r24 = pick(rows, 24, 3584)
    n24, g24, w24, itl24 = 24, r24["gen_len"], r24["wall_clock_s"], r24["itl_ms_p50"] / 1000
    good24 = g24 * n24 / w24
    p(f"by definition:  gen*n/wall = {g24:.0f}*{n24}/{w24} = {good24:.1f} tok/s")
    mix = (r24["prompt_len"] + g24) / g24
    p(f"counter decomposition (an IDENTITY given section 2, not independent evidence): "
      f"reported/((p+g)/g) = {r24['reported_tok_s']}/{mix:.0f} = {r24['reported_tok_s']/mix:.1f} tok/s")
    steady = n24 / itl24
    decode_s = (g24 - 1) * itl24
    p(f"independent latency-side corroboration: steady-state decode rate n/itl = {n24}/{itl24:.5f} "
      f"= {steady:.1f} tok/s over a decode phase of (gen-1)*itl = {decode_s:.1f} s of the {w24} s wall "
      f"-> consistent with ~{good24:.0f} tok/s full-run goodput; the roofline (section 6) ties the same "
      f"ITL column to the hardware independently")
    p("")

    p("== 4. B2: the long-context sweep anomaly ==")
    long_rows = [r for r in rows if r["prompt_len"] == 3584]
    p(f"{'n':>3} | {'wall_s':>7} {'reported':>9} {'goodput':>8} {'ttft_p50':>8} {'itl_p50':>7} {'preempt':>7} {'kv_util':>7}")
    for r in long_rows:
        n = int(r["batch_size"])
        p(f"{n:>3} | {r['wall_clock_s']:>7.2f} {r['reported_tok_s']:>9.1f} "
          f"{r['gen_len']*n/r['wall_clock_s']:>8.1f} {r['ttft_ms_p50']:>8.1f} "
          f"{r['itl_ms_p50']:>7.2f} {int(r['preempted_seqs']):>7} {r['kv_cache_util']:>7.2f}")
    r32 = pick(rows, 32, 3584)
    naive32 = w24 * 32 / 24
    excess = r32["wall_clock_s"] - naive32
    p(f"naive scaling from n=24: wall(32) ~ {w24:.2f} * 32/24 = {naive32:.1f}s; measured "
      f"{r32['wall_clock_s']}s (excess {excess:.1f}s, +{100*excess/naive32:.0f}%)")
    prefill_phase = w24 - decode_s
    per_prefill = prefill_phase / n24
    pre32 = int(r32["preempted_seqs"])
    recompute_s = pre32 * per_prefill
    p(f"recompute accounting in SECONDS: batch-24 prefill phase ~ wall - (gen-1)*itl = "
      f"{prefill_phase:.1f}s for {n24} prompts -> ~{per_prefill:.2f}s per {int(r24['prompt_len'])}-token prefill; "
      f"{pre32} re-prefills ~ {recompute_s:.1f}s — the TRIGGER and a lower bound, ~"
      f"{100*recompute_s/excess:.0f}% of the {excess:.1f}s excess. The bulk is the {pre32} evicted "
      f"sequences rejoining past the {math.floor(cap4096)}-slot KV ceiling: waiting for blocks, "
      f"re-prefilling, then finishing decode as a serialized tail (ttft p50 "
      f"{r24['ttft_ms_p50']:.0f} -> {r32['ttft_ms_p50']:.0f} ms corroborates queueing)")
    p("")

    p("== 5. B2 fix prediction: admission control max_num_seqs=24 ==")
    r48 = pick(rows, 48, 3584)
    two_waves = 2 * w24
    gen_total48 = int(r48["gen_len"] * r48["batch_size"])
    p(f"batch 48 as two full waves of 24: 2 * {w24}s = {two_waves:.1f}s vs measured {r48['wall_clock_s']}s "
      f"({100*(two_waves-r48['wall_clock_s'])/r48['wall_clock_s']:+.0f}% wall)")
    p(f"goodput: {gen_total48}/{two_waves:.1f} = {gen_total48/two_waves:.1f} tok/s vs measured "
      f"{gen_total48/r48['wall_clock_s']:.1f} "
      f"({100*(gen_total48/two_waves - gen_total48/r48['wall_clock_s'])/(gen_total48/r48['wall_clock_s']):+.0f}%), "
      f"predicted preemptions: 0")
    p("")

    p(f"== 6. Roofline: one bandwidth model explains every ITL in the log ==")
    p("model: itl = (weights + resident_seqs * avg_ctx * kv_bytes) / (eff * 300 GB/s)")
    p("       avg_ctx = prompt + gen/2 (KV grows during decode); resident = min(n, capacity)")
    p(f"{'n':>3} {'p_len':>6} | {'itl_log_ms':>10} {'ideal_ms':>9} {'implied_eff':>11}")
    effs = []
    ideal24 = None
    for r in rows:
        n, plen, gen = int(r["batch_size"]), int(r["prompt_len"]), int(r["gen_len"])
        capacity = math.floor(KV_BUDGET / ((plen + gen) * KV_BYTES_PER_TOKEN))
        resident = min(n, capacity)
        step_bytes = WEIGHT_BYTES + resident * (plen + gen / 2) * KV_BYTES_PER_TOKEN
        ideal_ms = step_bytes / BANDWIDTH * 1000
        if n == 24 and plen == 3584:
            ideal24 = ideal_ms
        eff = ideal_ms / r["itl_ms_p50"]
        effs.append(eff)
        p(f"{n:>3} {plen:>6} | {r['itl_ms_p50']:>10.2f} {ideal_ms:>9.2f} {eff:>11.3f}")
    mean_eff = sum(effs) / len(effs)
    spread = max(abs(e - mean_eff) / mean_eff for e in effs)
    p(f"implied memory-bandwidth efficiency: mean {mean_eff:.3f}, max deviation {100*spread:.1f}% "
      f"-> a single ~{mean_eff:.0%} MBU explains all {len(rows)} rows")
    flops_ms_24 = 2 * PARAMS * n24 / FLOPS * 1000
    p(f"compute check at n=24: 2*{PARAMS/1e9}e9 FLOPs/token * {n24} / {FLOPS/1e12:.0f} TFLOPS = "
      f"{flops_ms_24:.1f} ms per step vs {ideal24:.1f} ms of memory traffic -> decode is "
      f"memory-bound ~{ideal24/flops_ms_24:.0f}x over")
    p("")

    p("== 7. fp8 KV-cache prediction (from the same bandwidth model) ==")
    kv8 = KV_BYTES_PER_TOKEN / 2
    cap8 = math.floor(KV_BUDGET / (4096 * kv8))
    b24_itl = (WEIGHT_BYTES + n24 * (r24["prompt_len"] + g24 / 2) * kv8) / (mean_eff * BANDWIDTH) * 1000
    b48_itl = (WEIGHT_BYTES + 48 * (r24["prompt_len"] + g24 / 2) * kv8) / (mean_eff * BANDWIDTH) * 1000
    p(f"capacity: {cap8} concurrent 4096-tok seqs ({cap8/math.floor(cap4096):.1f}x, arithmetic-certain); "
      f"predicted itl at n=24: {b24_itl:.0f} ms (vs {r24['itl_ms_p50']:.1f} today, "
      f"{100*(b24_itl - r24['itl_ms_p50'])/r24['itl_ms_p50']:+.0f}%); n=48 fits with itl {b48_itl:.0f} ms "
      f"~= today's n=24 -> steady decode ~{48/b48_itl*1000:.0f} tok/s vs {steady:.0f} today (~2x), "
      f"0 preemptions. Caveats: (a) quality impact of fp8 KV must be evaluated; (b) the ITL prediction "
      f"assumes the {mean_eff:.0%} MBU transfers to fp8-KV attention kernels — dequant overhead can make "
      f"realized gains sub-proportional; the capacity doubling does NOT depend on that assumption.")

    text = "\n".join(out)
    (HERE / "reconcile_output.md").write_text("```\n" + text + "\n```\n", encoding="utf-8")
    print(text)
    print(f"\n[written to {HERE / 'reconcile_output.md'}]")


if __name__ == "__main__":
    main()
