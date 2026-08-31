# A1 — Eval corpus card

## What it is

**FLORES-200 devtest**: 1012 sentences, professionally translated from English
into 200+ languages, **n-way parallel at sentence level**. Languages: English +
the six languages the product roadmap names (Part C): Hindi, Kannada, Tamil,
Telugu, Bengali, Marathi — three Dravidian and three Indo-Aryan languages across
five scripts (assignment minimum: ≥4 languages, ≥2 Dravidian).

Parallelism is the load-bearing property: the audit's central correction (A2-C1)
is that a cross-language cost comparison needs a denominator that holds *content*
constant, and only parallel text provides that. Line `i` says the same thing in
all seven files.

* Source: `https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz` (public,
  no auth), NLLB team / Meta AI, **CC-BY-SA 4.0**.
* Build: `python build_corpus.py` — downloads, extracts the seven devtest files
  verbatim, writes UTF-8 with LF newlines. Deterministic; hashes below are
  asserted by `verify.py`.
* Domain: wiki-style prose (Wikipedia / Wikinews / Wikijunior source articles).

## Size & unit statistics (generated: `corpus_stats.md`)

| lang | FLORES code | sentences | words | graphemes | code points | UTF-8 bytes | NFC-changed lines | sha256/12 |
|---|---|---|---|---|---|---|---|---|
| eng | eng_Latn | 1012 | 21,901 | 131,966 | 131,966 | 132,096 | 0 | `612e9fbe8799` |
| hin | hin_Deva | 1012 | 25,643 | 85,978 | 131,079 | 337,094 | 93 | `5f5fd39acadc` |
| kan | kan_Knda | 1012 | 16,100 | 90,471 | 138,140 | 375,480 | 7 | `58e8ed5ef79c` |
| tam | tam_Taml | 1012 | 16,775 | 99,724 | 154,133 | 421,641 | 2 | `a18b26bf278e` |
| tel | tel_Telu | 1012 | 16,938 | 76,602 | 132,505 | 353,711 | 1 | `2dc641b4fb69` |
| ben | ben_Beng | 1012 | 19,506 | 81,693 | 129,042 | 344,682 | 609 | `6699aa77b4c9` |
| mar | mar_Deva | 1012 | 19,046 | 80,489 | 133,252 | 355,712 | 0 | `63d0d1bfdcfa` |

Already visible before any tokenizer runs: for identical content, Hindi uses
**more** words than English (25.6k vs 21.9k) while the Dravidian languages use
**fewer** (~16-17k, agglutination) with Bengali/Marathi in between; Hindi and
Bengali have *fewer* graphemes than English but ~2.6× the bytes. No per-unit
denominator is language-neutral — this table is Exhibit A for the denominator
argument, independent of any tokenizer.

(It also directly falsifies REPORT_v0's "Hindi simply has more Unicode characters
per word": true per *word*, but for the same content Hindi has fewer graphemes
and roughly equal code points vs English — the per-word framing was the artifact.
And the NFC-changed column shows the audited script's NFC call earning its keep
on real data: 609/1012 Bengali and 93/1012 Hindi lines arrive
non-NFC-normalized.)

## Preprocessing

Deliberately minimal: none beyond dropping empty lines (there are none) and
writing UTF-8/LF. **No lowercasing** (A2-B2 shows it biases the comparison), no
punctuation stripping, no NFC at build time — normalization stays in the
measurement script (`fertility_v1.py`) where it is a measured, versioned choice
(token effect of normalizing: ≤ +0.11% hin, +0.51% ben).

## What this corpus cannot tell you

FLORES is formal, wiki-register, *translated* prose. Production traffic for an
assistant is conversational, code-mixed, full of typos, and domain-shifted from
encyclopedic text; translationese also tends to be more verbose and formal than
natively-authored text, likely inflating non-English token counts somewhat.
Romanized traffic is a separately *measured* quantity here
(`../audit/romanization.py`) but via a clean transliteration scheme — organic
chat spelling is noisier, so those numbers bound the effect rather than settle
it. n = 1012 sentences from one domain gives tight *sampling* CIs (within ±1.3%
on parity, worst case 1.28%) but says nothing about *domain* variance — the
honest error bar on production parity is dominated by domain shift, not sample
size. (One statistical caveat on the CIs themselves: the bootstrap resamples
sentences i.i.d., while FLORES devtest draws contiguous sentences from articles;
mild within-article correlation makes the stated CIs slightly anti-conservative
— a block bootstrap over articles is the strict variant, and would not change
any conclusion at these effect sizes.) Use these
numbers to compare tokenizers and reason about routing direction; re-estimate
absolute premiums on scrubbed real traffic before committing budgets — that
re-estimation is the production monitor in the A4 memo and REPORT_v1.
