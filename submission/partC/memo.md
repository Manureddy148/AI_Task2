# Part C — Casual-tone in 6 Indic languages: recommendation

**Recommendation: (a) LoRA SFT on self-generated casualized pairs, gated by a day-1
prompt-engineering baseline.** (c) is the gate and the fallback, not the plan; (b)
is rejected on arithmetic below.

**Assumptions** (labelled, checkable): main model is our ~4B-class instruct, served
in-house, and can batch-generate on the A100 (no external API needed for synthetic
data — the model rewrites its own formal outputs into casual register per language);
"casual" is definable per language by a 1-page rubric (pronoun/honorific choice,
loanword tolerance, particle use); reviewer judges ~1 sample/min; launch review
accepts a staged scope (hi+kn human-verified; ta/te/bn/mr judge-verified, flagged).
One assumption is *measured*, not assumed (Part A, same six languages): on v0's
gpt2 tokenizer these languages cost 7.4-15.5× English tokens per content (the
production tokenizer is unmeasured — the serving spec's 128k vocab is not gpt2 —
so treat this as the bracket's top), meaning every per-token option here —
especially (b)'s second decode pass — carries an Indic premium unless the stack
is Indic-aware; and much of real chat is romanized, measured at ~2.2-2.4× on
gpt2 (Tamil scheme-inflated to 3.1×, bounded ≥2.4×;
`partA/audit/romanization.py`).

**Back-of-envelope arithmetic.**

* *Data volume*: 6 langs × 10k pairs = 60k pairs ≈ 30M tokens to generate
  (~500 tok/pair). At ~2k tok/s batched on the A100 ≈ 4 h; ×2 for rejection
  sampling/filtering → **<1 GPU-day**.
* *Training*: LoRA on 4B, 60k pairs × ~500 tok full sequence (loss on the ~300
  target tok, but forward/backward run over prompt+target) × 3 epochs ≈ 90M
  processed tokens at ~5k tok/s ≈ **5 h/run** → the 2-week budget (~336 GPU-h)
  allows ~65 runs; GPU is not the bottleneck. Serving cost delta after merge:
  **zero**.
* *Rewriter (b) rejected*: a second pass adds reply-length decode on the
  production L4s — ~100 tok/s per stream (starter_kit/starter_kit/bench/
  model_spec.md: 300 GB/s memory-bound; a 1B fp16 rewriter's ~2 GB weight read
  caps single-stream decode near 150 tok/s, less under batch load), so ~300 tok
  ≈ **+3 s p50 latency forever**, plus permanent extra memory/compute per
  request. And any ≤1B rewriter would need its own Indic casual-register SFT
  and eval, consuming the same reviewer budget with none of (a)'s serving
  payoff — (b) is path (a) plus latency plus a new meaning-drift surface placed
  *after* the aligned model. Its one real advantage — zero main-model
  regression risk and instant rollback — is real but purchasable more cheaply:
  (a) ships behind a flag with the base model as rollback.
* *Reviewer throughput* (the real bottleneck): 10 h/wk × 3 wk = 30 h ≈ **1,800
  judgments**, hi+kn only. Allocation: day-1 gate 200; rubric calibration 100;
  synthetic-data spot-checks 300 (wk 1); final blind eval 600 (300/lang, wk 3);
  reserve 600. ta/te/bn/mr get an LLM-judge **validated against the reviewer on
  hi/kn** (license to use it elsewhere requires ≥80% agreement).

**Success metric (numeric, tie-proof).** On 300 fresh prompts per language (hi,
kn), blind pairwise vs current model on casualness-and-naturalness: **win ≥60%
of non-tie comparisons AND win−loss ≥ +30 points AND tie rate ≤50%** (a
near-100% tie rate is direct evidence of a null intervention and auto-fails —
"win-or-tie" thresholds would pass a model that changed nothing), plus an
absolute clause: **≥70% of the new model's outputs independently rubric-rated
"casual"**; **meaning preserved ≥95%**; capability suite regression **≤1%**;
judge-reviewer agreement **≥80%** (else non-reviewable languages don't launch).

**Kill criterion (with date).** End of **day 4**: if <60% of synthetic pairs pass
reviewer spot-check (casual + meaning-preserving) after two iterations of the
generation prompt, the model cannot teach itself this register — kill (a), ship (c)
for hi+kn only, descope the rest at launch review. Secondary kill, **day 10**:
win <50% of non-tie comparisons, or rubric-rated casual <55%, or capability
regression >2% → revert to (c).

**Day-1 experiment.** 50 real prompts × {current system prompt, best casual prompt}
× {hi, kn} → 200 outputs → 3 h blind reviewer session. It simultaneously (1) gates
path (c): if prompting alone already clears the tie-proof success bar (≥60% of
non-ties, ≥70% rubric-casual), skip SFT and spend the GPU on evaluation breadth
instead; (2) calibrates the rubric and seeds few-shot
exemplars; (3) overnight, launches the first 5k-pair Hindi synthetic generation so
the data pipeline is validated by day 2 either way.

**Why not the other paths, in one line each.** (c) alone: cheapest, but prompting
only has to work *occasionally* for path (a) — we rejection-sample and keep the
casual rewrites that pass review, then train them into the default single-pass
behavior — whereas shipping (c) needs the unfiltered first sample right on every
request in six languages; the day-1 baseline measures exactly that gap, so it
gates rather than being assumed away. (b): pays latency and serving cost forever
to avoid a 5-hour training job we can rerun ~65 times inside budget.
