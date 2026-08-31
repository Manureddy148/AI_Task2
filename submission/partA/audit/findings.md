# A2 — Script & metric audit: findings

Every claim below was isolated and measured. Reproduce with:

```
python submission/partA/audit/experiments.py      # writes experiment_output.md
```

Baseline (v0 as shipped, full precision): eng fertility **1.2652**, hin **7.4485**,
ratio **5.8871×** — exact match to REPORT_v0 (see `repro_v0.md`).

## Verdict summary

| # | item | verdict | effect on the 5.89× headline |
|---|---|---|---|
| B1 | `line.split(" ")` instead of `split()` | **bug** | headline understated by 0.59% |
| B2 | `line.lower()` before tokenizing | **bug** | headline understated by 2.92% |
| B3 | macro-average of per-line ratios | **methodological bug** | headline understated by 0.35% |
| C1 | tokens-per-word compared **across languages** | **conceptual — the big one** | metric cannot answer the routing/cost question at all (−15% to +36% distortion per language on real data) |
| C2 | "tok/char agrees, so the result is robust" | **conceptual** | false confirmation; the two numbers don't agree (5.89 vs 7.0) and can't confirm each other |
| C3 | "property of the script, any tokenizer will struggle" | **conceptual, falsified** | tokenizer swap moves Hindi from 7.42× to 1.16× on identical content |
| D1 | corpora: 10 unaligned sentences | **data flaw** | ±9% sampling noise alone (bootstrap CI 5.37–6.43×) |
| N1 | `random.seed(1337)` | **cleared — fine** | zero (proven byte-identical) |
| N2 | `unicodedata.normalize("NFC", ...)` | **cleared — fine, actually useful** | zero on toy corpora; ≤0.11% on FLORES, and it removes a real inconsistency there |
| N3 | `add_special_tokens=False` on the HF path | **cleared — fine** | consistent with the tiktoken path (which adds none); fertility should count content tokens |

Net effect of the three code bugs combined (E6): ratio 5.887× → **6.114×** (+3.85%).
The code bugs are real but small, and they all pushed the same way (making Hindi look
slightly *less* bad). The decision-relevant damage is in C1–C3 and D1.

---

## B1. `split(" ")` counts empty strings as words

[fertility.py:62](../../../starter_kit/starter_kit/fertility.py#L62): `words = line.split(" ")`.
On a run of two spaces, `split(" ")` emits an empty string that counts as a word;
`split()` does not. Both sample files contain exactly one planted double space
(eng line 7, hin line 10 — the same sentence pair, incidentally).

* **Experiment (E1)**: toggle only `split(" ")` → `split()`, all else v0.
* **Numbers**: eng fertility 1.2652 → 1.2831 (**+1.41%**), hin 7.4485 → 7.5985
  (**+2.01%**), ratio 5.8871 → 5.9221 (**+0.59%**).
* **Why this proves it**: the only change is the word-count denominator on the
  double-space lines; token counts are untouched, so the whole delta is the
  phantom-word undercount. Direction: v0 *understates* fertility for both languages.

## B2. `lower()` distorts tokenization, asymmetrically

[fertility.py:60](../../../starter_kit/starter_kit/fertility.py#L60): the comment says
lowercasing removes "noise", but GPT-2's BPE is case-sensitive: lowercasing changes
which merges apply. Devanagari has no case, so the distortion applies **only to
English** — it biases the cross-language ratio, exactly what the script exists to measure.

* **Experiment (E2)**: toggle only lowercasing off.
* **Numbers**: eng fertility 1.2652 → 1.2293 (**−2.84%**); hin unchanged (0.00%);
  ratio 5.8871 → 6.0590 (**+2.92%**). Per-line: 3 of 10 English lines change token
  count, all upward under lowering ("The Quarterly Review…" 8→9, "NASA and ISRO…"
  10→11, "The GPU cluster…" 12→13) — cased proper nouns/acronyms tokenize better
  than their lowercased forms.
* **Why this proves it**: hin is bit-identical under `lower()` while eng gains
  tokens, so the ratio shift is pure English-side distortion. Direction: v0
  *understates* the ratio by ~2.9%. Independent of the delta: production traffic is
  cased, so v0 measures a distribution we don't serve.

## B3. Macro-average of per-line ratios

[fertility.py:64-67](../../../starter_kit/starter_kit/fertility.py#L64-L67): v0 averages
per-line `tokens/words`, weighting a 4-word line as much as a 12-word one (mean of
ratios ≠ ratio of sums). The corpus-level quantity that maps to cost is
`total tokens / total words`.

* **Experiment (E3)**: toggle only aggregation macro → micro.
* **Numbers**: eng 1.2652 → 1.2532 (−0.95%), hin 7.4485 → 7.4032 (−0.61%), ratio
  → 5.9076 (**+0.35%**). On FLORES with gpt2 the gap is similarly small (hin macro
  7.87 vs micro 7.83) because line lengths are homogeneous within each corpus.
* **Honest magnitude note**: small here; it grows with line-length variance. Claimed
  as a bug because the correct aggregation is free and the biased one is a latent
  hazard for any less-uniform corpus.

---

## C1. The conceptual flaw: the denominator doesn't hold content constant

The script computes exactly what it says — tokens per whitespace word — and that is
the wrong thing to compare **across languages**. A routing/cost decision pays for
tokens per *request content*; "word" is not a stable unit of content across
languages. Measured on 1012 parallel FLORES sentences (identical content in all
languages, gpt2, corrected pipeline — see `../results/results.md`):

| lang | words per sentence | per-word ratio vs eng | content-constant ratio (tokens per parallel sentence) | per-word error |
|---|---|---|---|---|
| hin | 25.3 (eng: 21.6) | 6.34× | **7.42×** | **−15%** (understates) |
| kan | 15.9 | 18.48× | **13.59×** | **+36%** (overstates) |
| tam | 16.6 | 20.28× | **15.54×** | +31% |
| tel | 16.7 | 16.77× | **12.97×** | +29% |
| ben | 19.3 | 10.79× | **9.61×** | +12% |
| mar | 18.8 | 9.04× | **7.86×** | +15% |

(Ratios computed from full-precision totals in `../results/results.csv`, e.g. hin
per-word = (200,704/25,643)/(27,044/21,901) = 7.827/1.235 = 6.34.)

* **Why this proves it**: same data, same tokenizer, same numerator — only the
  denominator changes, and the error has *opposite signs* for Hindi (analytic, more
  words per content) vs the Dravidian languages (agglutinative, fewer words per
  content). A metric whose language ranking flips with an arbitrary unit choice
  cannot drive routing. The parallel-sentence denominator is the only one that holds
  the paid-for quantity constant.

## C2. "The tok/char column agrees, which confirms the per-word number" — false

Two failures. (1) The numbers don't agree: 5.89× vs 7.0× are 19% apart; the report
rounds that into "confirmation". (2) They *couldn't* confirm each other anyway: both
share the same numerator (token count), so they are correlated by construction;
agreement between them carries no independent information about the denominator
choice. Measured demonstration of (2): on FLORES/gpt2 the hin-vs-eng ratio is 6.34×
per word, 11.39× per grapheme, 2.90× per byte — three "confirming" metrics, three
wildly different answers, because each denominator inflates differently across
scripts (Devanagari: 3 UTF-8 bytes per code point; matras merge into grapheme
clusters; words carry different content). `len(line)` counts code points — none of
Python's notions of "character" is script-fair.

## C3. "Root cause: property of the script, not the tokenizer" — falsified

* **Experiment**: identical parallel corpus, identical script, five tokenizers
  (`fertility_v1.py`). Content-constant premium vs English:

| tokenizer | hin | kan | tam | tel | ben | mar |
|---|---|---|---|---|---|---|
| gpt2 (the report's) | 7.42× | 13.59× | 15.54× | 12.97× | 9.61× | 7.86× |
| cl100k_base | 4.77× | 8.86× | 7.64× | 8.29× | 5.88× | 5.06× |
| o200k_base | 1.57× | 1.97× | 1.98× | 1.93× | 1.71× | 1.82× |
| xlm-roberta-base (multilingual SP) | 1.25× | 1.35× | 1.35× | 1.32× | 1.37× | 1.22× |
| MuRIL (Indic-focused WordPiece) | **1.16×** | **1.07×** | **1.06×** | **1.20×** | **1.00×** | **1.06×** |

* **Why this proves it**: the script is held constant; the premium varies **6.4×**
  (7.42 → 1.16 for Hindi; 14.7× for Tamil) with tokenizer choice alone. GPT-2's
  byte-BPE simply has almost no learned merges for Devanagari/Dravidian scripts,
  so it falls back to ~byte-level tokens (gpt2 hin tok/byte 0.595 ≈ byte-level;
  MuRIL 0.095). Integrity note: WordPiece/SentencePiece `<unk>` collapse could
  fake low counts, so unk rates are measured — worst cell 0.38% (MuRIL/tel), all
  others ≤0.02% (see results). The report's "no further measurement needed" rests
  on this false attribution.

## D1. The corpora cannot support the conclusion

1. **n = 10 sentences.** Bootstrap over lines (10,000 resamples, seed 42): 95% CI on
   the v0 headline ratio is **[5.37×, 6.43×]** — ±9% from sampling noise alone,
   before any domain question. The report presents 5.89× with no uncertainty and
   "numbers final".
2. **They are not parallel**, despite being described as parallel line-by-line: only
   5 of 10 sentence pairs correspond at all, in scrambled order (eng3↔hin3, eng4↔hin7,
   eng5↔hin6, eng7↔hin10, eng8↔hin4 — and two of those are loose paraphrases, e.g.
   eng3 mentions "a small shop near MG Road", hin3 doesn't). The other five lines in
   each file have no counterpart. So even the valid content-constant metric is
   uncomputable on the shipped data.

---

## Cleared items (looked suspicious, measured fine)

**N1. `random.seed(1337)`** ([fertility.py:25](../../../starter_kit/starter_kit/fertility.py#L25)).
A seeded RNG in a deterministic script smells like removed sampling logic. Cleared:
`random.` appears nowhere else in the file (grep), and running a copy with the seed
line deleted produces **byte-identical output** (SHA-256 equal on captured stdout).
Dead code, zero effect. Not a bug — just delete it for hygiene.

**N2. NFC normalization** ([fertility.py:49](../../../starter_kit/starter_kit/fertility.py#L49)).
Unicode normalization *can* change token counts (NFC decomposes precomposed
Devanagari nukta consonants like फ़ U+095E — they're composition-exclusions — which
changes byte length and hence BPE output). Measured: on both sample files NFC changes
**0 of 10 lines** (already normalized) → exactly zero effect on every reported
number (E4: all deltas 0.00%). On FLORES it normalizes 93/1012 Hindi and 609/1012
Bengali lines (token effect ≤ +0.11% hin, +0.51% ben) — i.e., the call is doing
its job: removing an encoding inconsistency that would otherwise add noise.
Verdict: keep it.

**N3. `add_special_tokens=False`** ([fertility.py:33](../../../starter_kit/starter_kit/fertility.py#L33)).
Might look like undercounting (BOS/EOS excluded), but the tiktoken path adds no
specials either, so the two paths are consistent, and per-request special tokens are
a constant that doesn't belong in a per-content comparison. Fine as designed.
