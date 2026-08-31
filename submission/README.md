# Submission — The Audit

Audit of `REPORT_v0.md` (tokenizer fertility + serving throughput) before
leadership uses it for routing and capacity decisions.

**Start here → [REPORT_v1.md](REPORT_v1.md)** — the corrected, deck-ready
replacement for REPORT_v0, with figures. Everything else is its evidence chain.

**Then run `python verify.py`** — every headline number in the submission is
re-derived and asserted (50 checks: byte-exact v0 reproduction, per-bug deltas,
corpus hashes, parity table, prose-quoted derived ratios, romanization on both
tokenizer generations, all 13 bench-log reconciliations, roofline fit). Green =
nothing in these documents is hand-typed folklore.

*Layout note:* the scripts locate the audited inputs via `_paths.py` — either
the `starter_kit/` folder next to `submission/` (both nestings handled) or a
`STARTER_KIT=<path>` environment variable.

## TL;DR of findings

* **Part A**: v0's 5.89× Hindi headline came from a biased pipeline (3 measured
  code bugs, net −3.7%) and — the real damage — a denominator that mis-ranks
  languages (−15% Hindi, +36% Kannada). On parallel content with v0's own
  tokenizer: **hin 7.42×, ben 9.61×, mar 7.86×, tel 12.97×, kan 13.59×,
  tam 15.54×**. The "property of the script" root-cause is falsified twice over:
  an Indic-focused vocab (MuRIL) serves the same content at **1.00-1.20×**
  (UNK-integrity-checked), and *romanized* Hindi on the same gpt2 tokenizer
  costs 2.25× (yet is *worse* than native on o200k for Hindi — script mix and
  tokenizer generation interact; a dashboard quantity). Two planted "suspicious"
  items (`random.seed`, NFC) are **cleared with evidence**, and a third planted
  inconsistency — the serving spec's 128k vocab vs v0's gpt2 benchmark — is
  surfaced in REPORT_v1 §4.
* **Part B**: KV cache = **112 KiB/token** ⇒ **~25** concurrent 4k sequences — a
  spec-only prediction that matches all 13 bench rows (utilization to rounding,
  preemptions exactly: 7 = 32−25, 23 = 48−25). `reported_tok_s` proven to count
  prefill (0.022% on all rows): honest goodput is **201 tok/s** at the stable
  peak, not 1607, and batch 48 measures 162, not 3200. A one-parameter roofline
  (**65% MBU**) reproduces every ITL within ±2.8% — decode is memory-bound 40×
  over — and prices the two fixes: `max_num_seqs=24` (−19% wall, +24% goodput at
  offered 48) and fp8 KV (2× capacity, ~2× decode throughput, quality eval
  pending).
* **Part C**: LoRA SFT on self-casualized pairs, gated day-1 by a prompt-only
  baseline; reviewer bandwidth (1,800 judgments), not GPU (~65 runs), binds.
  Kill: <60% synthetic-pair acceptance by day 4; success metrics are tie-proof
  (win share of non-ties + absolute rubric rate). Anchored to Part A's measured
  premiums for the same six languages.

## Layout

```text
REPORT_v1.md           the corrected report (deck-ready; figures/)
verify.py              numbers-under-test harness (50 assertions)
_paths.py              starter-kit locator (sibling layout or STARTER_KIT env var)
NOTEBOOK.md            chronological log (hypotheses, dead ends, self-caught errors)
AI_USAGE.md            honest AI usage account
figures/make_figures.py  regenerates fig1 (parity) & fig2 (throughput)
partA/
  audit/repro_v0.md      A0: byte-exact baseline reproduction
  audit/experiments.py   A2: one-toggle-per-flaw isolation runner
  audit/findings.md      A2: claims + evidence + cleared items
  audit/romanization.py  measured romanization effect (chat-style Latin)
  corpus/build_corpus.py A1: FLORES-200 builder, 7 languages (hash-pinned)
  corpus/corpus_card.md  A1: corpus card incl. what it cannot tell us
  fertility_v1.py        A3: corrected engine (5 tokenizers × 4 denominators, CIs, unk%)
  results/results.md     A3: full grid + denominator reasoning + the decision number
  memo.md                A4: one-page recommendation
partB/
  kv_math.py             B1 arithmetic (executable)
  reconcile.py           per-row prediction vs bench_log.csv + roofline (§1-§7)
  capacity.md            B1-B4 answers
partC/memo.md            C: one-page decision memo
```

## Reproduce every number

Python 3.14 (3.10+ should work); network for first-time downloads (FLORES
tarball 24 MB, tokenizer files):

```powershell
pip install -r requirements.txt
python verify.py                      # assert all published numbers (start here)

# or regenerate everything from scratch:
python partA/corpus/build_corpus.py   # corpus (downloads on first run)
python partA/audit/experiments.py     # A2 bug isolation
python partA/fertility_v1.py          # A3 grid
python partA/audit/romanization.py    # romanization effect
python partB/kv_math.py               # B1 arithmetic
python partB/reconcile.py             # B reconciliation + roofline
python figures/make_figures.py        # report figures
python verify.py --full               # regenerate + assert
```

Determinism: bootstrap seeds fixed (parity CIs seed 42 × 2000; toy CI seed 42 ×
10,000); corpus files hash-pinned; no GPU or torch required — tokenizers only.
