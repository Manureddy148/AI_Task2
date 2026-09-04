# Part B — Capacity reconciliation

All numbers regenerate with `python kv_math.py` (spec-only arithmetic) and
`python reconcile.py` (per-row replay of `bench_log.csv`; full output in
`reconcile_output.md`), and are asserted by `../verify.py`.

## B1. KV-cache arithmetic, and the check against the log

**(a) KV bytes per token, exactly.** Per token, per layer, the cache stores K and V
for each KV head (GQA: 8, not the 24 query heads):

```text
2 (K,V) × 28 layers × 8 KV heads × 128 head_dim × 2 bytes (fp16)
  = 114,688 bytes/token = 112 KiB exactly
```

(Without GQA it would be 344,064 B/token — the 8-vs-24 head spec line is worth 3×.)

**(b) Max concurrent 4096-token sequences.**

```text
usable VRAM   = 0.92 × 24 GB                   = 22.08 GB
weights       = 4.2e9 params × 2 B (fp16)      =  8.40 GB
runtime overhead (per spec)                    =  1.60 GB
KV budget     = 22.08 − 8.40 − 1.60            = 12.08 GB
per sequence  = 4096 tok × 114,688 B           = 0.46976 GB  (= 448 MiB exactly)
max concurrent = 12.08 / 0.46976               = 25.7  →  ~25 sequences
```

**Check against the log — the prediction nails all 13 rows** (`reconcile.py` §1):

* `kv_cache_util`: predicted = n·(prompt+gen)·114,688 B / 12.08 GB matches the
  logged column on **every row** within 2-decimal rounding (max error 0.0046), e.g.
  batch 24 long: predicted 0.9333, logged 0.93; batch 64 short: 0.4667 vs 0.47.
* `preempted_seqs`: predicted = max(0, n − 25) is **exact on every row**: 0
  everywhere except long-prompt batch 32 → 7 (= 32−25) and batch 48 → 23 (= 48−25).
* Sensitivity: reading "24 GB" as GiB would give ~29 concurrent seqs, predicting 3
  preemptions at batch 32 and util 0.82 at batch 24 — the log (7, 0.93) rejects
  that reading; the stack's budget matches decimal GB.

## B2. The long-context throughput anomaly

Naively, throughput grows with batch. The long-prompt sweep instead **peaks at
batch 24 and collapses**:

```text
  n |  wall_s  reported  goodput  ttft_p50  itl_p50  preempt  kv_util
 16 |   49.97    1311.4    163.9     498.3    77.20        0     0.62
 24 |   61.16    1607.4    200.9     500.5    96.07        0     0.93
 32 |   94.71    1384.0    173.0     636.9   101.79        7     0.97
 48 |  151.41    1298.5    162.3     955.4   100.00       23     0.97
```

**Mechanism (columns: `kv_cache_util`, `preempted_seqs`, `wall_clock_s`).** A
4096-token sequence needs 448 MiB of KV; the budget holds 25 (B1). At batch 32 the
scheduler cannot keep all sequences resident as they grow toward 4096, evicts 7
(= 32−25) at least once, and must **recompute their prefill** on re-admission.
Accounting in seconds (`reconcile.py` §4): the batch-24 row implies a prefill
phase of ~12 s for 24 prompts (~0.50 s per 3584-token prefill), so 7 re-prefills
cost ~3.5 s — the **trigger and a lower bound**, about a quarter of the 13.2 s
excess over linear scaling (94.7 s measured vs 81.5 s naive). The bulk of the
excess is the 7 evicted sequences rejoining past the 25-slot ceiling: waiting
for free KV blocks, re-prefilling, then finishing decode as a serialized tail —
the same wave effect §5 models for batch 48. `kv_cache_util` pinning at 0.97
(= 25 full seqs / budget) while ttft p50 rises 500→637→955 ms corroborates that
sequences queue for cache, not for compute. Throughput falls *because* batch
grew past cache capacity.

**Proposed change with predicted effect** (`reconcile.py` §5): set admission control
to capacity — `max_num_seqs = 24` (one below the 25.7 knee). Batch-48 offered load
then runs as two clean waves of 24: predicted wall ≈ 2×61.16 = **122.3 s vs
measured 151.4 s (−19%)**, goodput 24,576/122.3 ≈ **201 tok/s vs 162 (+24%)**,
predicted `preempted_seqs = 0`. Honest cost: the second wave's requests see ~61 s
ttft — that is queueing made visible instead of paid as cluster-wide recompute.

## B2a. Roofline: why the decode numbers are what they are

One bandwidth model closes the mechanism (`reconcile.py` §6). Each decode step
must read the weights (8.4 GB) plus every resident sequence's KV cache
(avg_ctx × 112 KiB), through 300 GB/s:

```text
itl_predicted = (8.4e9 + resident_seqs × avg_ctx × 114,688 B) / (eff × 300 GB/s)
```

A single fitted efficiency **eff ≈ 0.65** reproduces the measured ITL of **all 13
rows within ±2.8%** — short sweep and long sweep, before and after the preemption
knee. The compute side is negligible: 2·4.2 GFLOPs/token × 24 seqs ≈ 1.7 ms/step
against ~63 ms of memory traffic — **decode is memory-bound ~38× over**. This
explains, quantitatively, why ITL grows with batch and with context (more KV
bytes per step), why batching helps goodput anyway (the 8.4 GB weight read is
amortized over more sequences), and why "GPU utilization" intuitions from
compute-bound workloads misled REPORT_v0.

**Second lever, quantified by the same model** (`reconcile.py` §7): **fp8 KV
cache** halves KV bytes/token → capacity ≈ **51** concurrent 4k sequences (2×,
arithmetic-certain), predicted ITL at batch 24 drops to ~70 ms (−27%), and batch
48 fits outright at ~97 ms ITL (≈ today's batch 24) → steady decode ≈ **493
tok/s vs ~250 today (~2×)** with zero preemptions. Both levers' predictions are
falsifiable on one rerun; the admission-control one needs no accuracy sign-off,
while the fp8 one carries two stated assumptions: a KV-quantization quality eval
must pass, and the ITL half assumes the fitted 65% MBU transfers to fp8-KV
attention kernels (dequantization overhead can make realized latency gains
sub-proportional to the byte reduction — the capacity doubling does not depend
on this).

## B3. The misread column behind Section 2

`reported_tok_s` is **(prompt + generated) tokens ÷ wall clock** — it counts
prefill tokens as "throughput". Proof: (prompt+gen)·n/wall reproduces the logged
value on **all 13 rows within 0.022%** (`reconcile.py` §2), e.g. batch 16 long:
(3584+512)·16/49.97 = 1311.5 ≈ 1311.4.

Both Section-2 conclusions are this one misreading:

* *"Longer prompts give better throughput"* — longer prompts merely add more
  counted prefill tokens. Generation goodput says the opposite: short-prompt
  batch 16 delivers 294.5 tok/s vs long-prompt batch 16's 163.9 — long prompts are
  **~45% worse**, not 48% better.
* *"~1600 tok/s per L4, so batch 48 → ~3200"* — 1607 was 7/8 prefill by token mix;
  and the log itself already shows batch 48 *measured*: reported 1298 (lower than
  batch 24) and goodput 162 tok/s, because of B2's preemption collapse. Linear
  extrapolation past the cache knee had already failed inside the intern's own data.

**Honest goodput of the batch-24 long-prompt row, two derivations plus a
consistency identity** (the first draft called these "three independent ways";
that was wrong by this audit's own C2 logic — the counter decomposition is
algebraically implied by the §2 identity, so it confirms bookkeeping, not
measurement):

1. **By definition**: gen·n/wall = 512×24/61.16 = **200.9 tok/s**.
2. **Independently, from the latency columns**: steady-state decode rate n/itl =
   24/0.09607 = **249.8 tok/s**, sustained over a decode phase of (gen−1)·itl =
   49.1 s of the 61.16 s wall — consistent with ~201 tok/s full-run goodput, and
   tied to the hardware by the §B2a roofline, which fits this same ITL column
   at 65% MBU. This route uses columns (itl, ttft) that the definition never
   touches.
3. *(Identity, not evidence)*: reported ÷ (total/gen mix) = 1607.4/8 = 200.9 —
   given §2's proof that reported ≡ (p+g)·n/wall, this must equal derivation 1
   and serves only as an arithmetic cross-foot.

**What the report should have said:** "The harness counter includes prefill. For
capacity, plan on *generation* goodput: ≈200 tok/s per L4 for 3.5k-prompt traffic
(peak, at concurrency 24 — the KV capacity limit), ≈750 tok/s for short prompts at
batch 64. Do not exceed ~24 concurrent 4k-token sequences per L4; beyond that,
preemption reduces absolute throughput. Batch 48 delivers 162 tok/s today, not 3200."

## B4. The confirming counter

Pull **`vllm:num_preemptions_total`** (the scheduler's preemption counter; per-run
delta) for reruns of the batch 16/24/32/48 long-prompt configs. Prediction: ~0 for
batches ≤24, then **≥7** at batch 32 and **≥23** at batch 48 — the counter counts
preemption *events* while the log's `preempted_seqs` counts sequences preempted
at least once (model_spec.md's definition), so events ≥ unique sequences, with
equality only if no sequence is evicted twice near the 0.97-full cache. Each
preemption in recompute mode re-runs a full prefill, so
`vllm:prompt_tokens_total` should exceed submitted prompt tokens (n×3584) by
roughly preempted×3584+ tokens (≈25k extra at batch 32, ≈22% inflation). If that
counter stays at 0 while batch-32 throughput still collapses, my mechanism is wrong
and something else (e.g. swap-out bandwidth or fragmentation) is eating the time.
