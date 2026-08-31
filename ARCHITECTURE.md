# Audit Architecture

How this audit is organized, and why. The design goal is a submission where **every
claim is one command away from being re-derived live** — because the defense session
will demand exactly that.

## 1. What is being audited

`REPORT_v0.md` makes two families of claims feeding two leadership decisions:

| report section | claim | decision at risk |
|---|---|---|
| §1 Tokenizer fertility | Hindi is ~6× more expensive than English; the two metrics (tok/word, tok/char) confirm each other; it's a property of the script, so route Indic traffic separately and budget 6× | routing + cost budgeting |
| §2 Serving throughput | longer prompts give better throughput; plan capacity at ~1600 tok/s per L4 and scale linearly to ~3200 tok/s at batch 48 | capacity planning |

Both claims rest on artifacts we have in `starter_kit/`: the script (`fertility.py`),
the corpora (`corpus_sample/`), the serving spec (`bench/model_spec.md`) and the load
test log (`bench/bench_log.csv`). So every claim is checkable, and gets checked.

## 2. Evidence discipline (the design principle)

The assignment scores unverified claims at **−5 each**. The architecture enforces the
evidence rule mechanically:

1. **One variable at a time.** Each suspected bug in `fertility.py` is toggled in
   isolation against the as-shipped baseline, holding corpus and tokenizer fixed.
   The experiment runner re-derives: baseline numbers → single-fix numbers → Δ and
   direction. No fix is claimed as a bug unless its measured Δ ≠ 0 or its conceptual
   wrongness is demonstrated on data.
2. **Cleared items are deliverables too.** Things that look suspicious but measure
   out clean (the assignment plants at least one) are reported as *cleared*, with
   the clearing experiment. Not flagging the harmless thing is worth points; flagging
   it without evidence costs points.
3. **Pin the baseline first.** Before claiming anything, reproduce REPORT_v0's exact
   numbers from the shipped script + shipped corpora. If they don't reproduce, that
   is itself a finding; if they do, all deltas are attributable to my changes.
4. **Scripts over prose.** Every table in the submission is emitted by a script under
   version control. Defense-time "add this flag live" is served by CLI flags, not by
   editing code.
5. **Numbers under test.** `submission/verify.py` re-derives and asserts every
   headline figure published in the documents (50 checks: baseline reproduction,
   per-bug deltas, corpus hashes, the parity grid, prose-quoted derived ratios,
   romanization on both tokenizer generations, all 13 bench-log reconciliations,
   the roofline fit). A document number with no assertion behind it is treated
   as unpublished.

## 3. Part A — tokenizer audit pipeline

```
                    ┌────────────────────────────────────────────────┐
starter_kit corpora │ A0  repro: pin REPORT_v0 numbers, byte-exact   │
        ──────────► │ A2  bug isolation: toggle one candidate flaw   │──► partA/audit/findings.md
                    │     at a time, measure Δ on the v0 numbers     │    (claims + cleared items)
                    └────────────────────────────────────────────────┘
                    ┌────────────────────────────────────────────────┐
FLORES-200 devtest  │ A1  corpus build: 7 languages (eng + the six   │──► partA/corpus/ + corpus card
        ──────────► │     product languages: hin, kan, tam, tel,     │    (incl. what it CANNOT tell us)
                    │     ben, mar), line-aligned parallel, stats    │
                    └────────────────────────────────────────────────┘
                    ┌────────────────────────────────────────────────┐
                    │ A3  corrected analysis: 5 tokenizers (incl.    │──► partA/results/results.md
                    │     Indic-focused MuRIL, unk-rate guarded) ×   │    + results.csv
                    │     4 denominators (word, grapheme, byte,      │
                    │     parallel sentence) + bootstrap CIs          │
                    └────────────────────────────────────────────────┘
                    ┌────────────────────────────────────────────────┐
                    │ A4x romanization: transliterate the corpus,    │──► partA/audit/romanization.py
                    │     measure chat-script parity per tokenizer   │    (memo claims must be measured too)
                    └────────────────────────────────────────────────┘
                                        │
                                        ▼
                    A4 one-page memo: corrected headline number, routing
                    recommendation, biggest caveat, production monitor
```

**The denominator question (A3's core).** A cross-language cost comparison needs a
denominator that holds constant *the thing being paid for* — the content of a request.
Words, characters (code points), graphemes and bytes all vary across languages for
identical content, each in a different direction. A **parallel corpus** is the one
instrument that holds content fixed, which is why A1 builds one and why the corrected
headline is tokens-per-same-content relative to English, per tokenizer. The audit
measures all four denominators side by side to show how each distorts, rather than
asserting it.

**Tokenizer axis.** The report's root-cause claim ("property of the script, any
tokenizer will struggle") is falsifiable by running one Indic-focused tokenizer next
to GPT-2. A3 runs: `gpt2` (tiktoken, the intern's choice), two modern OpenAI
encodings, a general multilingual comparator (XLM-R), and **an Indic-focused
tokenizer (MuRIL)** with unk-rate integrity checks — same corpus, same script,
same denominators.

## 4. Part B — capacity reconciliation pipeline

Part B is pure arithmetic against two files, so it is built as **executable
arithmetic**: `partB/kv_math.py` derives KV bytes/token and max concurrency from
`model_spec.md` alone (B1), then `partB/reconcile.py` replays every row of
`bench_log.csv` against the prediction — per-row predicted KV utilization and
predicted preemptions vs. the logged columns. The B2 anomaly (throughput collapse in
the long-context sweep) and the B3 misreading (what `reported_tok_s` actually counts)
must both fall out of that reconciliation, each cross-checked at least two independent
ways before being claimed. The reconciliation ends in a **roofline**: a single
bandwidth-efficiency parameter must explain every measured inter-token latency, or
the claimed mechanism is incomplete. Written answers live in `partB/capacity.md`;
every number in it is regenerated by the two scripts.

## 5. Part C — decision memo

No experiments possible (scenario is hypothetical), so the architecture is: explicit
assumptions → back-of-envelope arithmetic that respects all four constraints (GPU
budget, reviewer 10 h/wk Hindi+Kannada only, 3-week deadline, no external APIs) →
a day-1 experiment designed as a *gate between paths*, not a formality → numeric
success threshold and a kill criterion with a date. One page, in `partC/memo.md`.

## 6. Chronology and honesty artifacts

- `submission/NOTEBOOK.md` — written **as the work happens**, not reconstructed:
  hypothesis → experiment → result → revision, dead ends kept.
- `submission/AI_USAGE.md` — where AI tooling helped, where it was wrong, and which
  parts I verified by hand. Populated from real incidents during the work, not
  invented ones.

## 7. Repo map (deliverable)

```text
submission/
  REPORT_v1.md              the product: corrected report for the leadership deck
  verify.py                 numbers-under-test harness (50 assertions; defense entry point)
  README.md                 intro + how to reproduce every number (defense quick-start)
  requirements.txt          pinned deps (tokenizers, transliteration, matplotlib; no torch)
  NOTEBOOK.md               chronological lab notebook
  AI_USAGE.md               honest AI usage account
  figures/
    make_figures.py         regenerates the two report figures from the data
  partA/
    audit/
      repro_v0.md           A0: exact reproduction of the report's numbers
      experiments.py        A2: one-flag-per-flaw isolation runner
      findings.md           A2: claims with evidence + cleared items
      romanization.py       measured chat-script parity (the memo's romanization claim)
    corpus/
      build_corpus.py       A1: FLORES-200 download/extract/stats (deterministic)
      corpus_card.md        A1: sizes, domain, preprocessing, what it cannot tell us
      data/                 7 line-aligned parallel files (committed, hash-pinned)
    fertility_v1.py         A3: corrected metric engine (5 tokenizers × 4 denominators, CIs, unk%)
    results/
      results.csv           A3: machine-readable numbers
      results.md            A3: tables + denominator reasoning + the one number
    memo.md                 A4: one-page recommendation
  partB/
    kv_math.py              B1: KV-cache + concurrency arithmetic, executable
    reconcile.py            B1/B2: per-row prediction vs bench_log.csv + roofline
    capacity.md             B1–B4 written answers
  partC/
    memo.md                 C: one-page decision memo
```
