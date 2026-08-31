```
== 1. KV utilization & preemption: prediction vs log (all 13 rows) ==
  n  p_len   gen | util_log util_pred | pre_log pre_pred
  1    512   256 |     0.01    0.0073 |       0        0
  2    512   256 |     0.01    0.0146 |       0        0
  4    512   256 |     0.03    0.0292 |       0        0
  8    512   256 |     0.06    0.0583 |       0        0
 16    512   256 |     0.12    0.1167 |       0        0
 32    512   256 |     0.23    0.2333 |       0        0
 64    512   256 |     0.47    0.4667 |       0        0
  4   3584   512 |     0.16    0.1556 |       0        0
  8   3584   512 |     0.31    0.3111 |       0        0
 16   3584   512 |     0.62    0.6222 |       0        0
 24   3584   512 |     0.93    0.9333 |       0        0
 32   3584   512 |     0.97    0.9722 |       7        7
 48   3584   512 |     0.97    0.9722 |      23       23
capacity at 4096 tok/seq: 25 seqs (exact: 25.72)
max |util_pred - util_log| = 0.0046 (log has 2 decimals -> perfect within rounding)
preempted_seqs predicted exactly on every row: True

== 2. What reported_tok_s actually counts (all 13 rows) ==
  n  p_len |  reported  (p+g)*n/wall  gen*n/wall
  1    512 |      70.2          70.2        23.4
  2    512 |     132.3         132.3        44.1
  4    512 |     261.0         261.0        87.0
  8    512 |     495.4         495.5       165.2
 16    512 |     883.2         883.4       294.5
 32    512 |    1489.6        1489.5       496.5
 64    512 |    2267.3        2267.2       755.7
  4   3584 |     565.4         565.4        70.7
  8   3584 |     902.6         902.7       112.8
 16   3584 |    1311.4        1311.5       163.9
 24   3584 |    1607.4        1607.3       200.9
 32   3584 |    1384.0        1383.9       173.0
 48   3584 |    1298.5        1298.5       162.3
max relative gap between reported_tok_s and (prompt+gen)*n/wall: 0.022%
-> reported_tok_s counts PREFILL tokens as throughput; goodput (gen only) is the honest column

== 3. B3: honest goodput of the batch-24 long-prompt row ==
by definition:  gen*n/wall = 512*24/61.16 = 200.9 tok/s
counter decomposition (an IDENTITY given section 2, not independent evidence): reported/((p+g)/g) = 1607.4/8 = 200.9 tok/s
independent latency-side corroboration: steady-state decode rate n/itl = 24/0.09607 = 249.8 tok/s over a decode phase of (gen-1)*itl = 49.1 s of the 61.16 s wall -> consistent with ~201 tok/s full-run goodput; the roofline (section 6) ties the same ITL column to the hardware independently

== 4. B2: the long-context sweep anomaly ==
  n |  wall_s  reported  goodput ttft_p50 itl_p50 preempt kv_util
  4 |   28.98     565.4     70.7    483.2   51.33       0    0.16
  8 |   36.30     902.6    112.8    519.0   62.26       0    0.31
 16 |   49.97    1311.4    163.9    498.3   77.20       0    0.62
 24 |   61.16    1607.4    200.9    500.5   96.07       0    0.93
 32 |   94.71    1384.0    173.0    636.9  101.79       7    0.97
 48 |  151.41    1298.5    162.3    955.4  100.00      23    0.97
naive scaling from n=24: wall(32) ~ 61.16 * 32/24 = 81.5s; measured 94.71s (excess 13.2s, +16%)
recompute accounting in SECONDS: batch-24 prefill phase ~ wall - (gen-1)*itl = 12.1s for 24 prompts -> ~0.50s per 3584-token prefill; 7 re-prefills ~ 3.5s — the TRIGGER and a lower bound, ~27% of the 13.2s excess. The bulk is the 7 evicted sequences rejoining past the 25-slot KV ceiling: waiting for blocks, re-prefilling, then finishing decode as a serialized tail (ttft p50 500 -> 637 ms corroborates queueing)

== 5. B2 fix prediction: admission control max_num_seqs=24 ==
batch 48 as two full waves of 24: 2 * 61.16s = 122.3s vs measured 151.41s (-19% wall)
goodput: 24576/122.3 = 200.9 tok/s vs measured 162.3 (+24%), predicted preemptions: 0

== 6. Roofline: one bandwidth model explains every ITL in the log ==
model: itl = (weights + resident_seqs * avg_ctx * kv_bytes) / (eff * 300 GB/s)
       avg_ctx = prompt + gen/2 (KV grows during decode); resident = min(n, capacity)
  n  p_len | itl_log_ms  ideal_ms implied_eff
  1    512 |      43.48     28.24       0.650
  2    512 |      43.10     28.49       0.661
  4    512 |      45.34     28.98       0.639
  8    512 |      46.83     29.96       0.640
 16    512 |      48.33     31.91       0.660
 32    512 |      56.17     35.83       0.638
 64    512 |      67.91     43.66       0.643
  4   3584 |      51.33     33.87       0.660
  8   3584 |      62.26     39.74       0.638
 16   3584 |      77.20     51.49       0.667
 24   3584 |      96.07     63.23       0.658
 32   3584 |     101.79     64.70       0.636
 48   3584 |     100.00     64.70       0.647
implied memory-bandwidth efficiency: mean 0.649, max deviation 2.8% -> a single ~65% MBU explains all 13 rows
compute check at n=24: 2*4.2e9 FLOPs/token * 24 / 121 TFLOPS = 1.7 ms per step vs 63.2 ms of memory traffic -> decode is memory-bound ~38x over

== 7. fp8 KV-cache prediction (from the same bandwidth model) ==
capacity: 51 concurrent 4096-tok seqs (2.0x, arithmetic-certain); predicted itl at n=24: 70 ms (vs 96.1 today, -27%); n=48 fits with itl 97 ms ~= today's n=24 -> steady decode ~493 tok/s vs 250 today (~2x), 0 preemptions. Caveats: (a) quality impact of fp8 KV must be evaluated; (b) the ITL prediction assumes the 65% MBU transfers to fp8-KV attention kernels — dequant overhead can make realized gains sub-proportional; the capacity doubling does NOT depend on that assumption.
```
