#!/usr/bin/env python3
"""Numbers-under-test: re-derive and assert every headline figure in this submission
(the run prints its check count; documents cite that count).

Fast mode (default, ~30 s): recomputes the Part A toy experiments, corpus hashes,
romanization headline and ALL of Part B live; checks A3 headline values against
results.csv (regenerate that with fertility_v1.py or --full).

    python verify.py          # fast (~30 s)
    python verify.py --full   # regenerates results/romanization/reconcile first (~3 min)

Exit code 0 = every published number reproduces. Run this at the start of the
defense.
"""

import csv
import hashlib
import importlib.util
import math
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILS = []
N_CHECKS = 0


def check(name, ok, detail=""):
    global N_CHECKS
    N_CHECKS += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(name)


def close(a, b, tol):
    return abs(a - b) <= tol


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    if "--full" in sys.argv:
        for script in ("partA/fertility_v1.py", "partA/audit/romanization.py",
                       "partB/reconcile.py"):
            print(f"== regenerating via {script} ==")
            # stdout suppressed (progress noise); stderr passes through so a
            # failure shows its actual cause, not a bare CalledProcessError
            subprocess.run([sys.executable, str(HERE / script)],
                           check=True, stdout=subprocess.DEVNULL)

    print("== A0/A2: toy-corpus experiments (live recompute) ==")
    ex = load(HERE / "partA" / "audit" / "experiments.py", "experiments")
    base = ex.run_variant()
    check("v0 baseline eng fertility = 1.2652", close(base["eng"][0], 1.2652, 5e-4))
    check("v0 baseline hin fertility = 7.4485", close(base["hin"][0], 7.4485, 5e-4))
    check("v0 baseline ratio = 5.8871", close(base["ratio"], 5.8871, 5e-4))
    check("gold check vs shipped fertility.py", ex.gold_check())
    e1 = ex.run_variant(split_fixed=True)
    check("E1 split() ratio delta = +0.59%",
          close(100 * (e1["ratio"] / base["ratio"] - 1), 0.59, 0.02))
    e2 = ex.run_variant(lower=False)
    check("E2 no-lower ratio delta = +2.92%",
          close(100 * (e2["ratio"] / base["ratio"] - 1), 2.92, 0.02))
    check("E2 leaves hin untouched", e2["hin"][0] == base["hin"][0])
    e3 = ex.run_variant(agg="micro")
    check("E3 micro ratio delta = +0.35%",
          close(100 * (e3["ratio"] / base["ratio"] - 1), 0.35, 0.02))
    e4 = ex.run_variant(nfc=False)
    check("E4 NFC is a no-op on toys (cleared item)", e4 == base)

    print("== A1: corpus integrity ==")
    pinned = {"eng": "612e9fbe8799", "hin": "5f5fd39acadc", "kan": "58e8ed5ef79c",
              "tam": "a18b26bf278e", "tel": "2dc641b4fb69", "ben": "6699aa77b4c9",
              "mar": "63d0d1bfdcfa"}
    for lang, want in pinned.items():
        f = HERE / "partA" / "corpus" / "data" / f"{lang}.txt"
        got = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
        n = len([l for l in f.read_text(encoding="utf-8").split("\n") if l.strip()])
        check(f"corpus {lang}: sha256/12 {want}, 1012 lines", got == want and n == 1012, got)

    print("== A3: headline parities (results.csv vs pinned) ==")
    with open(HERE / "partA" / "results" / "results.csv", newline="", encoding="utf-8") as f:
        rows = {(r["tokenizer"], r["lang"]): r for r in csv.DictReader(f)}
    for tok, lang, want in [
        ("gpt2", "hin", 7.4214), ("gpt2", "kan", 13.5877), ("gpt2", "tam", 15.5366),
        ("gpt2", "tel", 12.9708), ("gpt2", "ben", 9.6054), ("gpt2", "mar", 7.8638),
        ("cl100k_base", "hin", 4.7675), ("o200k_base", "hin", 1.5727),
        ("hf:xlm-roberta-base", "hin", 1.2466),
        ("hf:google/muril-base-cased", "hin", 1.1575),
        ("hf:google/muril-base-cased", "ben", 1.0012),
    ]:
        got = float(rows[(tok, lang)]["parity_vs_eng"])
        check(f"parity {tok}/{lang} = {want}", close(got, want, 5e-4), f"{got}")
    check("max unk rate across all cells = 0.38% (tel/muril)",
          max(float(r["unk_pct"]) for r in rows.values()) < 0.4)
    # prose-quoted derived figures (findings.md C1 verdict range, REPORT_v1 rec 1)
    def perword_err(lang):
        pw = float(rows[("gpt2", lang)]["tok_per_word"]) / float(rows[("gpt2", "eng")]["tok_per_word"])
        return 100 * (pw / float(rows[("gpt2", lang)]["parity_vs_eng"]) - 1)
    check("C1 per-word error hin = -15% (verdict-table range low)",
          close(perword_err("hin"), -14.6, 0.2), f"{perword_err('hin'):.1f}%")
    check("C1 per-word error kan = +36% (verdict-table range high)",
          close(perword_err("kan"), 36.0, 0.3), f"{perword_err('kan'):.1f}%")
    tam_saving = float(rows[("gpt2", "tam")]["parity_vs_eng"]) / \
        float(rows[("hf:google/muril-base-cased", "tam")]["parity_vs_eng"])
    check("REPORT rec-1 Tamil saving gpt2->MuRIL = 14.7x",
          close(tam_saving, 14.67, 0.05), f"{tam_saving:.2f}")
    ci_half = max(max(float(r["parity_vs_eng"]) - float(r["parity_ci_lo"]),
                      float(r["parity_ci_hi"]) - float(r["parity_vs_eng"]))
                  / float(r["parity_vs_eng"])
                  for r in rows.values() if r["lang"] != "eng")
    check("worst parity CI half-width in (1.2%, 1.3%] as documented",
          0.012 < ci_half <= 0.013, f"{100*ci_half:.2f}%")
    # results.md code-point clause (per NFC text, tokens from results.csv)
    cp = {}
    for lang in ("eng", "hin"):
        txt = (HERE / "partA" / "corpus" / "data" / f"{lang}.txt").read_text(encoding="utf-8")
        cp[lang] = sum(len(unicodedata.normalize("NFC", l)) for l in txt.split("\n") if l.strip())
    cp_ratio = (float(rows[("gpt2", "hin")]["tok_total"]) / cp["hin"]) / \
               (float(rows[("gpt2", "eng")]["tok_total"]) / cp["eng"])
    check("gpt2 hin per-code-point ratio = 7.46 (results.md '~7.5x')",
          close(cp_ratio, 7.4647, 5e-3), f"{cp_ratio:.4f}")

    print("== A4 romanization claims (live recompute, hin, both tokenizers) ==")
    rom = load(HERE / "partA" / "audit" / "romanization.py", "romanization")
    import tiktoken
    g2 = tiktoken.get_encoding("gpt2").encode
    o2 = tiktoken.get_encoding("o200k_base").encode
    eng_lines, hin = rom.read("eng"), rom.read("hin")
    roman = [rom.chatify(l, rom.SCHEMES["hin"]) for l in hin]
    for name, enc, want_nat, want_rom in [("gpt2", g2, 7.4214, 2.2483),
                                          ("o200k", o2, 1.5727, 1.8697)]:
        eng_t = sum(len(enc(l)) for l in eng_lines)
        nat = sum(len(enc(l)) for l in hin) / eng_t
        romp = sum(len(enc(l)) for l in roman) / eng_t
        check(f"{name} hin native parity = {want_nat}", close(nat, want_nat, 5e-3), f"{nat:.4f}")
        check(f"{name} hin romanized parity = {want_rom}", close(romp, want_rom, 5e-3), f"{romp:.4f}")
    check("romanized hin has zero residual source-script letters",
          rom.residual_stats(roman) == (0, 0))

    print("== Part B: full live recompute ==")
    km = load(HERE / "partB" / "kv_math.py", "kv_math")
    check("KV bytes/token = 114,688", km.KV_BYTES_PER_TOKEN == 114688)
    check("KV budget = 12.08 GB", close(km.KV_BUDGET, 12.08e9, 1e6))
    check("capacity ~25 (25.72)", close(km.MAX_CONCURRENT, 25.72, 0.01))
    from _paths import find_starter_kit
    log = find_starter_kit() / "bench" / "bench_log.csv"
    with open(log, newline="", encoding="utf-8") as f:
        brows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    util_ok, pre_ok, rep_ok, effs = True, True, True, []
    for r in brows:
        n, p, g = int(r["batch_size"]), int(r["prompt_len"]), int(r["gen_len"])
        cap = math.floor(km.KV_BUDGET / ((p + g) * km.KV_BYTES_PER_TOKEN))
        util_ok &= abs(min(n, cap) * (p + g) * km.KV_BYTES_PER_TOKEN / km.KV_BUDGET
                       - r["kv_cache_util"]) <= 0.005
        pre_ok &= max(0, n - cap) == int(r["preempted_seqs"])
        rep_ok &= abs((p + g) * n / r["wall_clock_s"] - r["reported_tok_s"]) / r["reported_tok_s"] <= 1e-3
        effs.append((km.WEIGHT_BYTES + min(n, cap) * (p + g / 2) * km.KV_BYTES_PER_TOKEN)
                    / 300e9 * 1000 / r["itl_ms_p50"])
    check("kv_cache_util predicted on all 13 rows (<=0.005)", util_ok)
    check("preempted_seqs predicted EXACTLY on all 13 rows", pre_ok)
    check("reported_tok_s = (p+g)*n/wall on all rows (<=0.1%)", rep_ok)
    m24 = [r for r in brows if r["batch_size"] == 24 and r["prompt_len"] == 3584]
    check("exactly one batch-24 long-prompt row (unique binding)", len(m24) == 1)
    r24 = m24[0]
    good = r24["gen_len"] * 24 / r24["wall_clock_s"]
    check("b24 goodput (by definition) = 200.9 tok/s", close(good, 200.9, 0.05), f"{good:.2f}")
    check("b24 counter decomposition consistent with the section-2 identity",
          close(r24["reported_tok_s"] / 8, good, 0.1))
    steady = 24 / (r24["itl_ms_p50"] / 1000)
    check("b24 steady decode rate n/itl = 249.8 tok/s (independent latency route)",
          close(steady, 249.8, 0.2), f"{steady:.1f}")
    mean_eff = sum(effs) / len(effs)
    check("roofline: mean MBU = 0.649", close(mean_eff, 0.649, 0.005), f"{mean_eff:.4f}")
    check("roofline: max deviation < 3%",
          max(abs(e - mean_eff) / mean_eff for e in effs) < 0.03)

    ok = len(FAILS) == 0
    print(f"\n{f'ALL {N_CHECKS} NUMBERS VERIFIED' if ok else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
