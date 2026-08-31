# A0 — Baseline reproduction (pin before touching anything)

Before claiming any flaw, verify the report's numbers come from the shipped script +
shipped corpora, so that every later delta is attributable to a deliberate change.

```
cd starter_kit/starter_kit
python fertility.py --corpus eng=corpus_sample/eng_sample.txt \
                    --corpus hin=corpus_sample/hin_sample.txt --tokenizer gpt2
```

Output (2026-08-31, Python 3.14.4, tiktoken 0.14.0):

```
lang      fertility (tok/word)    tok/char
------------------------------------------
eng                       1.27       0.226
hin                       7.45       1.579

hin is 5.89x the fertility of eng (worse tokenization)
```

**Matches REPORT_v0.md exactly** (1.27 / 0.226, 7.45 / 1.579, "5.89×"). Full-precision
values (from `experiments.py`): eng 1.2652 / 0.2256, hin 7.4485 / 1.5791, ratio 5.8871.

Additionally, `experiments.py` re-implements the v0 pipeline and asserts equality
against the shipped module's own functions (`gold check: True`), so the experiment
runner and the shipped script are provably the same baseline.

One more baseline for later reference — the **unmodified v0 script run on the real
corpus** (FLORES-200 devtest, see `../corpus/`):

```
python fertility.py --corpus eng=../../submission/partA/corpus/data/eng.txt \
    --corpus hin=...hin.txt --corpus kan=...kan.txt --corpus tam=...tam.txt \
    --corpus tel=...tel.txt --tokenizer gpt2
```

```
eng 1.29   hin 7.87 (6.11x)   kan 22.57 (17.53x)   tam 25.13 (19.52x)   tel 20.57 (15.97x)
```

Kept as the "what the intern's method says on real data" reference point for A3.
