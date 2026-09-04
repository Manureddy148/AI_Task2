#!/usr/bin/env python3
"""Guided defense drill — walks the candidate through the AI_USAGE checklist.

Each step runs the real command, shows expected vs actual, and (interactively)
waits so you can absorb it. ~10 minutes total. The point is not the green
output — it's that YOU have derived each number once before the panel asks.

    python defense_drill.py          # interactive (press Enter between steps)
    python defense_drill.py --auto   # non-interactive smoke of the same steps
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import find_starter_kit

AUTO = "--auto" in sys.argv
PY = sys.executable


def pause(msg="  [Enter to continue]"):
    if not AUTO:
        input(msg)


def banner(n, title):
    print(f"\n{'='*72}\nSTEP {n}: {title}\n{'='*72}")


def run(cmd, tail=None):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "") + (r.stderr or "")
    lines = out.strip().splitlines()
    for l in (lines[-tail:] if tail else lines):
        print(f"  | {l}")
    return r.returncode, out


def main():
    kit = find_starter_kit()

    banner(1, "Run the full verification harness yourself")
    print("  Expected final line: ALL 50 NUMBERS VERIFIED")
    rc, out = run([PY, str(HERE / "verify.py")], tail=3)
    assert rc == 0 and "ALL 50 NUMBERS VERIFIED" in out, "verify.py did not pass!"
    pause()

    banner(2, "A0 — reproduce REPORT_v0's numbers from the shipped script")
    print("  Expected: eng 1.27 / 0.226, hin 7.45 / 1.579, 'hin is 5.89x'")
    run([PY, str(kit / "fertility.py"),
         "--corpus", f"eng={kit/'corpus_sample'/'eng_sample.txt'}",
         "--corpus", f"hin={kit/'corpus_sample'/'hin_sample.txt'}",
         "--tokenizer", "gpt2"])
    pause()

    banner(3, "Live toggle — paste a line into the Hindi toy, watch every number move")
    with tempfile.TemporaryDirectory() as td:
        pasted = Path(td) / "hin_pasted.txt"
        shutil.copy(kit / "corpus_sample" / "hin_sample.txt", pasted)
        with open(pasted, "a", encoding="utf-8") as f:
            f.write("यह एक नयी पंक्ति है।\n")
        print("  Appended one Hindi line. Baseline ratio was 5.8871x; it should now differ,")
        print("  and the bootstrap line should read '10/11-line toys'.")
        run([PY, str(HERE / "partA" / "audit" / "experiments.py"), "--hin", str(pasted)], tail=6)
    print("  Restoring the canonical output (re-running with defaults)...")
    rc, out = run([PY, str(HERE / "partA" / "audit" / "experiments.py")], tail=2)
    assert rc == 0
    pause()

    banner(4, "B1 on paper — the arithmetic the whole of Part B stands on")
    from partB.kv_math import (LAYERS, KV_HEADS, HEAD_DIM, BYTES_FP16,  # noqa: E402
                               KV_BYTES_PER_TOKEN, GPU_MEM_UTIL, GPU_BYTES,
                               WEIGHT_BYTES, OVERHEAD_BYTES, KV_BUDGET,
                               BYTES_PER_4096_SEQ, MAX_CONCURRENT)
    print(f"  KV/token = 2 (K,V) x {LAYERS} x {KV_HEADS} x {HEAD_DIM} x {BYTES_FP16}"
          f" = {KV_BYTES_PER_TOKEN:,} B  ({KV_BYTES_PER_TOKEN/1024:.0f} KiB)")
    print(f"  KV budget = {GPU_MEM_UTIL}x{GPU_BYTES/1e9:.0f} - {WEIGHT_BYTES/1e9:.1f} - "
          f"{OVERHEAD_BYTES/1e9:.1f} = {KV_BUDGET/1e9:.2f} GB")
    print(f"  per 4k seq = 4096 x {KV_BYTES_PER_TOKEN:,} = {BYTES_PER_4096_SEQ/2**20:.0f} MiB")
    print(f"  capacity  = {KV_BUDGET/1e9:.2f} / {BYTES_PER_4096_SEQ/1e9:.4f} = {MAX_CONCURRENT:.1f} -> ~25")
    print("  Now write those four lines by hand once. Seriously.")
    pause()

    banner(5, "One bench row by hand — batch 32, prompt 3584")
    import csv
    import math
    with open(find_starter_kit() / "bench" / "bench_log.csv", encoding="utf-8", newline="") as f:
        r32 = next(r for r in csv.DictReader(f)
                   if r["batch_size"] == "32" and r["prompt_len"] == "3584")
    cap = math.floor(KV_BUDGET / (4096 * KV_BYTES_PER_TOKEN))
    pred_util = cap * 4096 * KV_BYTES_PER_TOKEN / KV_BUDGET
    print(f"  capacity floor = {cap}; predicted preempted = 32 - {cap} = {32-cap} "
          f"(logged: {r32['preempted_seqs']})")
    print(f"  predicted util = {cap}x4096x{KV_BYTES_PER_TOKEN:,}/{KV_BUDGET/1e9:.2f}GB = "
          f"{pred_util:.4f} (logged: {r32['kv_cache_util']})")
    print(f"  reported check: (3584+512)*32/{r32['wall_clock_s']} = "
          f"{4096*32/float(r32['wall_clock_s']):.1f} (logged reported_tok_s: {r32['reported_tok_s']})")
    pause()

    banner(6, "Read REPORT_v1.md end to end")
    print(f"  Open: {HERE / 'REPORT_v1.md'}")
    print("  Note anything you would phrase or decide differently — and say so in the")
    print("  defense. Disagreement with the AI drafts is evidence of ownership.")
    print("\nDrill complete. Now update the checklist in AI_USAGE.md honestly.")


if __name__ == "__main__":
    main()
