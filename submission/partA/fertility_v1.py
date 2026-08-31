#!/usr/bin/env python3
"""A3: corrected cross-language tokenizer analysis.

Fixes vs the intern's v0 (each fix isolated and measured in audit/experiments.py):
  - no lowercasing (measure the distribution we serve)
  - whitespace split() (no empty "words" on double spaces)
  - micro aggregation: corpus totals, not mean of per-line ratios
  - four denominators side by side: whitespace word, extended grapheme cluster,
    UTF-8 byte, and PARALLEL SENTENCE (the only content-constant one)
  - parity vs English on parallel text, with a paired bootstrap 95% CI
  - NFC applied (v0 kept; cleared in the audit — and actively useful here:
    93/1012 FLORES hin lines are not NFC-normalized as shipped)

Usage (defaults shown; any subset works):
  python fertility_v1.py \
      --tokenizers gpt2,cl100k_base,o200k_base,hf:xlm-roberta-base,hf:google/muril-base-cased
  # defense overrides: --data-dir DIR, and/or --corpus LANG=PATH (repeatable) to
  # swap in a pasted file; files must stay line-aligned with eng (parallel corpus).
"""

import argparse
import random
import sys
import unicodedata
from pathlib import Path

import regex

HERE = Path(__file__).resolve().parent
DATA = HERE / "corpus" / "data"
LANGS = ["eng", "hin", "kan", "tam", "tel", "ben", "mar"]
SEED = 42
N_BOOT = 2000


def load_tokenizer(spec):
    """Return (encode_fn, unk_token_id_or_None).

    unk matters: WordPiece/SentencePiece map unknown spans to a single <unk>
    token, which UNDERCOUNTS tokens and would fake good fertility. Byte-level
    BPE (tiktoken) cannot produce unk. We measure the unk rate and disqualify
    any (tokenizer, language) cell where it is material.
    """
    if spec.startswith("hf:"):
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(spec[3:])
        return (lambda s: tok.encode(s, add_special_tokens=False)), tok.unk_token_id
    import tiktoken
    return tiktoken.get_encoding(spec).encode, None


def read_lines(path, nfc=True):
    lines = [l for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]
    return [unicodedata.normalize("NFC", l) for l in lines] if nfc else lines


def paired_bootstrap_ci(tok_lang, tok_eng, n_boot=N_BOOT, seed=SEED):
    """95% CI for sum(tok_lang)/sum(tok_eng) resampling parallel sentence indices."""
    rng = random.Random(seed)
    n = len(tok_eng)
    reps = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        reps.append(sum(tok_lang[i] for i in idx) / sum(tok_eng[i] for i in idx))
    reps.sort()
    return reps[int(0.025 * n_boot)], reps[int(0.975 * n_boot)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizers", default="gpt2,cl100k_base,o200k_base,"
                    "hf:xlm-roberta-base,hf:google/muril-base-cased")
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--corpus", action="append", default=[], metavar="LANG=PATH",
                    help="override one language's file (repeatable), e.g. hin=pasted.txt")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    langs = args.langs.split(",")
    assert langs[0] == "eng", "first language is the parity baseline (English)"

    files = {lang: args.data_dir / f"{lang}.txt" for lang in langs}
    for spec in args.corpus:
        lang, path = spec.split("=", 1)
        files[lang] = Path(path)
    texts = {lang: read_lines(files[lang]) for lang in langs}
    n_sents = {lang: len(t) for lang, t in texts.items()}
    assert len(set(n_sents.values())) == 1, (
        f"files are not line-aligned (parity needs parallel text): {n_sents}")

    units = {lang: dict(
        words=[len(l.split()) for l in t],
        graphemes=[len(regex.findall(r"\X", l)) for l in t],
        bytes=[len(l.encode("utf-8")) for l in t],
    ) for lang, t in texts.items()}

    args.out.mkdir(exist_ok=True)
    csv_rows = ["tokenizer,lang,tok_total,tok_per_word,tok_per_grapheme,tok_per_byte,"
                "tok_per_sent,fert_macro_v0style,parity_vs_eng,parity_ci_lo,parity_ci_hi,unk_pct"]
    md = []

    for spec in args.tokenizers.split(","):
        encode, unk_id = load_tokenizer(spec)
        ids = {lang: [encode(l) for l in texts[lang]] for lang in langs}
        toks = {lang: [len(x) for x in ids[lang]] for lang in langs}
        md.append(f"\n### tokenizer: `{spec}`\n")
        md.append("| lang | tok/sent | **parity vs eng (95% CI)** | tok/word | tok/grapheme | tok/byte | macro fert | unk% |")
        md.append("|---|---|---|---|---|---|---|---|")
        for lang in langs:
            t, u = toks[lang], units[lang]
            total = sum(t)
            n = len(t)
            per_word = total / sum(u["words"])
            per_g = total / sum(u["graphemes"])
            per_b = total / sum(u["bytes"])
            per_s = total / n
            macro = sum(tt / w for tt, w in zip(t, u["words"])) / n
            unk_pct = (100 * sum(x.count(unk_id) for x in ids[lang]) / total) if unk_id is not None else 0.0
            unk_str = f"{unk_pct:.2f}" if unk_id is not None else "n/a"
            if lang == "eng":
                parity, lo, hi = 1.0, 1.0, 1.0
                parity_str = "1.00 (baseline)"
            else:
                parity = total / sum(toks["eng"])
                lo, hi = paired_bootstrap_ci(t, toks["eng"])
                parity_str = f"**{parity:.2f}x** [{lo:.2f}, {hi:.2f}]"
            csv_rows.append(f"{spec},{lang},{total},{per_word:.4f},{per_g:.4f},"
                            f"{per_b:.4f},{per_s:.2f},{macro:.4f},{parity:.4f},{lo:.4f},{hi:.4f},{unk_pct:.4f}")
            md.append(f"| {lang} | {per_s:.1f} | {parity_str} | {per_word:.2f} | "
                      f"{per_g:.2f} | {per_b:.3f} | {macro:.2f} | {unk_str} |")

    # units-per-sentence table (tokenizer-independent): what each denominator "holds constant"
    md.append("\n### units per sentence (same 1012 parallel sentences)\n")
    md.append("| lang | words/sent | graphemes/sent | bytes/sent |")
    md.append("|---|---|---|---|")
    for lang in langs:
        u, n = units[lang], n_sents[lang]
        md.append(f"| {lang} | {sum(u['words'])/n:.1f} | {sum(u['graphemes'])/n:.1f} | {sum(u['bytes'])/n:.1f} |")

    # NFC footnote on the audited tokenizer (tokens AND bytes, raw vs NFC —
    # corpus_card/corpus_stats list RAW file bytes; the tables above are post-NFC)
    import tiktoken
    g2 = tiktoken.get_encoding("gpt2").encode
    md.append("\n### NFC effect (raw file vs NFC-normalized, the pipeline's text)\n")
    md.append("| lang | gpt2 tok raw | gpt2 tok NFC | tok delta | bytes raw | bytes NFC | byte delta |")
    md.append("|---|---|---|---|---|---|---|")
    byte_deltas = {}
    for lang in langs:
        raw_lines = read_lines(files[lang], nfc=False)
        raw_t = sum(len(g2(l)) for l in raw_lines)
        nfc_t = sum(len(g2(l)) for l in texts[lang])
        raw_b = sum(len(l.encode("utf-8")) for l in raw_lines)
        nfc_b = sum(len(l.encode("utf-8")) for l in texts[lang])
        byte_deltas[lang] = 100 * (nfc_b - raw_b) / raw_b
        md.append(f"| {lang} | {raw_t:,} | {nfc_t:,} | {100*(nfc_t-raw_t)/raw_t:+.3f}% | "
                  f"{raw_b:,} | {nfc_b:,} | {byte_deltas[lang]:+.3f}% |")
    top = sorted(byte_deltas.items(), key=lambda kv: -abs(kv[1]))[:2]
    md.append("\nAll per-unit metrics and the units-per-sentence table above are measured "
              "post-NFC (the measurement pipeline's text); corpus_card.md lists raw file "
              "bytes, which differ where NFC rewrites lines ("
              + ", ".join(f"{l} {d:+.1f}%" for l, d in top) + ").")

    (args.out / "results.csv").write_text("\n".join(csv_rows) + "\n", encoding="utf-8")
    tables = "\n".join(md) + "\n"
    (args.out / "results_tables.md").write_text(tables, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(tables)
    print(f"[written to {args.out / 'results.csv'} and results_tables.md]")


if __name__ == "__main__":
    main()
