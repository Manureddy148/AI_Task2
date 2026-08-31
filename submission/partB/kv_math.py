#!/usr/bin/env python3
"""B1: KV-cache arithmetic from bench/model_spec.md ALONE (no log peeking).

Every constant below is copied from model_spec.md; run this to re-derive the
numbers quoted in capacity.md.
"""

import math

# --- model spec ---
LAYERS = 28
KV_HEADS = 8          # GQA
HEAD_DIM = 128
BYTES_FP16 = 2
PARAMS = 4.2e9
Q_HEADS = 24          # only used to show the GQA-vs-MHA contrast

# --- serving config ---
GPU_BYTES = 24e9      # L4 "24 GB" read as decimal GB; sensitivity check below
GPU_MEM_UTIL = 0.92
OVERHEAD_BYTES = 1.6e9
MAX_MODEL_LEN = 4096

# --- derived ---
KV_BYTES_PER_TOKEN = 2 * LAYERS * KV_HEADS * HEAD_DIM * BYTES_FP16   # K and V
WEIGHT_BYTES = PARAMS * BYTES_FP16
KV_BUDGET = GPU_MEM_UTIL * GPU_BYTES - WEIGHT_BYTES - OVERHEAD_BYTES
BYTES_PER_4096_SEQ = MAX_MODEL_LEN * KV_BYTES_PER_TOKEN
MAX_CONCURRENT = KV_BUDGET / BYTES_PER_4096_SEQ


def report():
    print("B1(a) KV-cache bytes per token")
    print(f"  2 (K,V) x {LAYERS} layers x {KV_HEADS} KV heads x {HEAD_DIM} head_dim x {BYTES_FP16} B (fp16)")
    print(f"  = {KV_BYTES_PER_TOKEN:,} bytes/token  (= {KV_BYTES_PER_TOKEN/1024:.0f} KiB exactly)")
    mha = 2 * LAYERS * Q_HEADS * HEAD_DIM * BYTES_FP16
    print(f"  (contrast: without GQA, {Q_HEADS} KV heads would need {mha:,} B/token — GQA saves {mha/KV_BYTES_PER_TOKEN:.0f}x)")
    print()
    print("B1(b) max concurrent 4096-token sequences")
    print(f"  usable VRAM     = {GPU_MEM_UTIL} x {GPU_BYTES/1e9:.0f} GB          = {GPU_MEM_UTIL*GPU_BYTES/1e9:.2f} GB")
    print(f"  weights (fp16)  = {PARAMS/1e9} B params x 2 B      = {WEIGHT_BYTES/1e9:.2f} GB")
    print(f"  overhead        =                          {OVERHEAD_BYTES/1e9:.2f} GB")
    print(f"  KV budget       = {GPU_MEM_UTIL*GPU_BYTES/1e9:.2f} - {WEIGHT_BYTES/1e9:.2f} - "
          f"{OVERHEAD_BYTES/1e9:.2f}      = {KV_BUDGET/1e9:.2f} GB")
    print(f"  per 4096-seq    = {MAX_MODEL_LEN} x {KV_BYTES_PER_TOKEN:,} B      = "
          f"{BYTES_PER_4096_SEQ/1e9:.4f} GB (= {BYTES_PER_4096_SEQ/2**20:.0f} MiB)")
    print(f"  max concurrent  = {KV_BUDGET/1e9:.2f} / {BYTES_PER_4096_SEQ/1e9:.4f}    = "
          f"{MAX_CONCURRENT:.2f}  ->  ~{math.floor(MAX_CONCURRENT)} sequences")
    print()
    print("Sensitivity: if '24 GB' meant 24 GiB (25.77e9 B):")
    alt_budget = GPU_MEM_UTIL * 24 * 2**30 - WEIGHT_BYTES - OVERHEAD_BYTES
    print(f"  KV budget {alt_budget/1e9:.2f} GB -> {alt_budget/BYTES_PER_4096_SEQ:.1f} concurrent seqs")
    print("  (reconcile.py shows the log matches the decimal-GB reading, not this one)")


if __name__ == "__main__":
    report()
