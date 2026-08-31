#!/usr/bin/env python3
"""A2 bug-isolation experiments for fertility.py (the shipped v0 script).

Method: re-implement v0's pipeline, ASSERT it matches the shipped module's own
functions to full float precision, then toggle ONE candidate flaw at a time and
report the delta on the numbers REPORT_v0.md quotes. No flaw is claimed without
a nonzero measured delta (or a demonstrated conceptual failure on data).

Run:  python experiments.py            (from anywhere; paths resolved from repo root)
Out:  prints a report and writes experiment_output.md next to this file.
"""

import argparse
import importlib.util
import random
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # submission/ -> _paths
from _paths import find_starter_kit

KIT = find_starter_kit()
ENG = KIT / "corpus_sample" / "eng_sample.txt"
HIN = KIT / "corpus_sample" / "hin_sample.txt"

import tiktoken

ENC = tiktoken.get_encoding("gpt2")


# ---------- v0 semantics, re-implemented with toggles ----------

def read_lines(path, nfc=True):
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if nfc:
                line = unicodedata.normalize("NFC", line)
            lines.append(line)
    return lines


def analyze(lines, lower=True, split_fixed=False, agg="macro"):
    """v0 defaults: lower=True, split(' '), macro-average of per-line ratios."""
    tok_counts, word_counts, char_counts = [], [], []
    for line in lines:
        if lower:
            line = line.lower()
        tokens = ENC.encode(line)
        words = line.split() if split_fixed else line.split(" ")
        tok_counts.append(len(tokens))
        word_counts.append(len(words))
        char_counts.append(len(line))
    if agg == "macro":
        fert = sum(t / w for t, w in zip(tok_counts, word_counts)) / len(tok_counts)
        tpc = sum(t / c for t, c in zip(tok_counts, char_counts)) / len(tok_counts)
    else:  # micro: corpus-level totals
        fert = sum(tok_counts) / sum(word_counts)
        tpc = sum(tok_counts) / sum(char_counts)
    return fert, tpc


def run_variant(nfc=True, lower=True, split_fixed=False, agg="macro"):
    out = {}
    for lang, path in (("eng", ENG), ("hin", HIN)):
        out[lang] = analyze(read_lines(path, nfc=nfc), lower=lower,
                            split_fixed=split_fixed, agg=agg)
    out["ratio"] = out["hin"][0] / out["eng"][0]
    return out


# ---------- gold check against the shipped module ----------

def gold_check():
    spec = importlib.util.spec_from_file_location("fertility_v0", KIT / "fertility.py")
    v0 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v0)
    enc = v0.load_tokenizer("gpt2")
    for lang, path in (("eng", ENG), ("hin", HIN)):
        theirs = v0.analyze(v0.read_lines(str(path)), enc)
        mine = analyze(read_lines(path))
        assert theirs == mine, f"reimplementation mismatch for {lang}: {theirs} vs {mine}"
    return True


# ---------- data-level facts ----------

def data_facts():
    facts = []
    for lang, path in (("eng", ENG), ("hin", HIN)):
        raw = read_lines(path, nfc=False)
        nfc = [unicodedata.normalize("NFC", l) for l in raw]
        multi_space = [i + 1 for i, l in enumerate(raw) if "  " in l]
        nfc_changed = [i + 1 for i, (a, b) in enumerate(zip(raw, nfc)) if a != b]
        lower_changed = [i + 1 for i, l in enumerate(nfc) if l.lower() != l]
        tok_nfc = sum(len(ENC.encode(l)) for l in nfc)
        tok_raw = sum(len(ENC.encode(l)) for l in raw)
        tok_lower = sum(len(ENC.encode(l.lower())) for l in nfc)
        facts.append(dict(lang=lang, n=len(raw), multi_space=multi_space,
                          nfc_changed=nfc_changed, lower_changed=lower_changed,
                          tok_raw=tok_raw, tok_nfc=tok_nfc, tok_lower=tok_lower))
    return facts


def per_line_lower_effect():
    """For English: which lines change token count when lowercased, and by how much."""
    rows = []
    for i, line in enumerate(read_lines(ENG), 1):
        a, b = len(ENC.encode(line)), len(ENC.encode(line.lower()))
        if a != b:
            rows.append((i, line, a, b))
    return rows


def bootstrap_ratio_ci(n_boot=10_000, seed=42):
    """95% CI for the hin/eng macro-fertility ratio under line resampling.

    The two toy files are NOT aligned (see findings), so resample independently.
    Sizes are derived from the files so a pasted extra line changes the CI too.
    """
    rng = random.Random(seed)
    per_line = {}
    for lang, path in (("eng", ENG), ("hin", HIN)):
        vals = []
        for line in read_lines(path):
            line = line.lower()
            vals.append(len(ENC.encode(line)) / len(line.split(" ")))
        per_line[lang] = vals
    ne, nh = len(per_line["eng"]), len(per_line["hin"])
    ratios = []
    for _ in range(n_boot):
        e = [per_line["eng"][rng.randrange(ne)] for _ in range(ne)]
        h = [per_line["hin"][rng.randrange(nh)] for _ in range(nh)]
        ratios.append((sum(h) / nh) / (sum(e) / ne))
    ratios.sort()
    return ratios[int(0.025 * n_boot)], ratios[int(0.975 * n_boot)]


# ---------- report ----------

def fmt(v):
    return f"eng {v['eng'][0]:.4f} tok/w, {v['eng'][1]:.4f} tok/c | " \
           f"hin {v['hin'][0]:.4f} tok/w, {v['hin'][1]:.4f} tok/c | " \
           f"ratio {v['ratio']:.4f}x"


def main():
    global ENG, HIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--eng", type=Path, default=ENG, help="English toy corpus path")
    ap.add_argument("--hin", type=Path, default=HIN, help="Hindi toy corpus path")
    args = ap.parse_args()
    ENG, HIN = args.eng, args.hin

    lines = []
    p = lines.append

    p("# A2 experiment output (generated by experiments.py)\n")
    p(f"gold check (reimplementation == shipped fertility.py functions): {gold_check()}\n")

    base = run_variant()
    p("## Variants (one toggle at a time vs v0)\n")
    variants = [
        ("V0 as shipped", dict()),
        ("E1 split() instead of split(' ')", dict(split_fixed=True)),
        ("E2 no lowercasing", dict(lower=False)),
        ("E3 micro (corpus-level) aggregation", dict(agg="micro")),
        ("E4 no NFC normalization", dict(nfc=False)),
        ("E6 combined fix: E1+E2+E3 (NFC kept)", dict(split_fixed=True, lower=False, agg="micro")),
    ]
    for name, kw in variants:
        v = run_variant(**kw)
        d_ratio = 100 * (v["ratio"] - base["ratio"]) / base["ratio"]
        d_e = 100 * (v["eng"][0] - base["eng"][0]) / base["eng"][0]
        d_h = 100 * (v["hin"][0] - base["hin"][0]) / base["hin"][0]
        p(f"- **{name}**: {fmt(v)}")
        p(f"  - delta vs v0: eng fert {d_e:+.2f}%, hin fert {d_h:+.2f}%, ratio {d_ratio:+.2f}%\n")

    p("## Data-level facts\n")
    for f in data_facts():
        p(f"- **{f['lang']}**: {f['n']} lines; lines with runs of 2+ spaces: {f['multi_space']}; "
          f"lines changed by NFC: {f['nfc_changed']}; lines changed by lower(): {f['lower_changed']}; "
          f"total gpt2 tokens raw/NFC/NFC+lower: {f['tok_raw']}/{f['tok_nfc']}/{f['tok_lower']}")
    p("")

    p("## English lines whose gpt2 token count changes under lower()\n")
    for i, line, a, b in per_line_lower_effect():
        p(f"- line {i}: {a} -> {b} tokens | {line}")
    p("")

    lo, hi = bootstrap_ratio_ci()
    ne, nh = len(read_lines(ENG)), len(read_lines(HIN))
    p("## Sample-size fragility of the 5.89x headline\n")
    p(f"- bootstrap 95% CI (10,000 resamples, seed 42) of the hin/eng fertility ratio "
      f"on the {ne}/{nh}-line toys: [{lo:.2f}x, {hi:.2f}x]\n")

    text = "\n".join(lines)
    out = HERE / "experiment_output.md"
    out.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    print(f"[written to {out}]")


if __name__ == "__main__":
    main()
