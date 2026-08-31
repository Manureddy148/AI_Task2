# A4 — Recommendation memo: Indic tokenizer cost & routing

**To:** Leadership, before the routing/capacity decision  ·  **From:** the audit  ·  **Date:** 2026-08-31

## Corrected headline numbers

Tokens per identical content relative to English (1012 parallel FLORES-200
sentences; sampling 95% CIs within ±1.3%, worst 1.28%; all values asserted by
`verify.py`):

| tokenizer under decision | hin | kan | tam | tel | ben | mar |
|---|---|---|---|---|---|---|
| v0's tokenizer (gpt2) | **7.4×** | **13.6×** | **15.5×** | **13.0×** | **9.6×** | **7.9×** |
| Indic-focused vocab (MuRIL-class) | **1.16×** | **1.07×** | **1.06×** | **1.20×** | **1.00×** | **1.06×** |

REPORT_v0's "Hindi ≈ 6×, robust, no further measurement needed" is wrong three
ways: it *understates* Hindi (7.4× — the 5.89× came from a biased denominator and
a lowercasing bug), it never measured the other five product languages (7.9-15.5×
— four of the five carry a bigger premium than Hindi), and its root-cause claim
("property of the script") is falsified: the premium collapses 6.4× by changing
tokenizer alone. One caution the audit surfaced in v0's own materials: the
serving spec lists a 128k vocabulary, which is not gpt2 — so the *production*
stack's premium is bracketed by these rows, not settled, until recommendation 4
runs.

## Recommendation

1. **Do route Indic traffic to an Indic-aware tokenizer/model** — v0's direction
   survives the audit, its numbers don't. Versus v0's tokenizer the saving is
   ~6× for Hindi and ~11-15× for Dravidian languages, far larger than v0
   promised.
2. **Do not budget "6× for Hindi".** Budget per language against the *target*
   stack's tokenizer: ≈1.0-1.2× English for all six languages if an Indic-aware
   route ships; 5-16× only for whatever traffic stays on an English-centric
   vocabulary. (Reverse trade, measured: multilingual vocabs price English +2%
   (MuRIL-class) to +13% (xlm-r-class) — route per-language, not fleet-wide.)
3. **Weigh script mix before trusting any single premium.** Measured: chat-style
   *romanized* Hindi costs 2.25× on gpt2 (vs 7.42× native) — but on a modern
   o200k-class vocab romanization is *worse* than native for Hindi (1.87× vs
   1.57×), a tie for Kannada, and cheaper for Telugu. The premium on real
   traffic is a function of script mix × tokenizer generation, so it must come
   off a dashboard, not out of this memo.
4. **Re-measure parity with the actual candidate model's tokenizer on scrubbed
   real traffic before the budget is signed** — including the production FLM-4B
   tokenizer the 128k-vocab spec implies. One afternoon with `fertility_v1.py`;
   this memo's numbers are the decision's shape, not its final invoice.

## Biggest caveat

Parity was measured on formal, translated wiki prose. Production assistant
traffic is conversational, code-mixed and noisy; romanization was measured via a
clean transliteration scheme, which bounds the effect rather than settles it —
a probe with attested chat conventions moved Hindi o200k parity from 1.87× to
1.76×, still above native 1.57×, and Tamil's scheme output is aspirate-inflated
(honest range 2.37-3.09× on gpt2). Domain shift, not sampling noise, is the
error bar: sampling CIs are ±1.3%, but domain effects are plausibly tens of
percent — and the toy-corpus era of this analysis moved numbers ±9% from 10
sentences alone.

## The one production metric

**Weekly tokens-per-request by detected language and script, normalized by a
content-size proxy (UTF-8 bytes of the user turn), on live traffic** — with each
language's expected value **anchored in byte space at launch** from the measured
tok/byte ratios (`results.csv`, e.g. gpt2 hin 2.91×, ben 3.64× English), because
byte-normalized premiums are a different quantity from content parity (bytes per
content differ ~2.6× between Hindi and English — the per-byte denominator is
disqualified for *comparing* languages, which is exactly why the monitor
compares each language only against **its own anchor**). If the live value
drifts >20% from its anchor — romanization share, domain mix — this analysis is
wrong in production, and the routing split gets re-derived from that dashboard,
not from this memo.
