#!/usr/bin/env python3
"""Generate the two figures for REPORT_v1.md from the measured data.

Fig 1: token parity vs English by tokenizer x language (from partA results.csv)
Fig 2: reported counter vs generation goodput on the long-prompt sweep (bench log)

Palette: dataviz reference categorical slots 1-6, fixed order, validated
(adjacent-pair CVD gates pass; sub-3:1 slots relieved by direct labels here and
by full tables in REPORT_v1).
"""

import csv
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # submission/ -> _paths
sys.path.insert(0, str(HERE.parent / "partB"))  # -> kv_math
from _paths import find_starter_kit
from kv_math import KV_BUDGET, KV_BYTES_PER_TOKEN

RESULTS = HERE.parent / "partA" / "results" / "results.csv"
BENCH = find_starter_kit() / "bench" / "bench_log.csv"
CAPACITY = math.floor(KV_BUDGET / (4096 * KV_BYTES_PER_TOKEN))

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
LANGS = ["hin", "kan", "tam", "tel", "ben", "mar"]
LANG_NAMES = {"hin": "Hindi", "kan": "Kannada", "tam": "Tamil",
              "tel": "Telugu", "ben": "Bengali", "mar": "Marathi"}
TOKS = ["gpt2", "cl100k_base", "o200k_base", "hf:xlm-roberta-base",
        "hf:google/muril-base-cased"]
TOK_NAMES = ["gpt2\n(v0's tokenizer)", "cl100k_base", "o200k_base",
             "xlm-roberta\n(multilingual)", "MuRIL\n(Indic-focused)"]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": INK, "axes.edgecolor": BASELINE,
    "xtick.color": MUTED, "ytick.color": MUTED,
})


def style_axes(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(length=0)


def fig1():
    with open(RESULTS, newline="", encoding="utf-8") as f:
        rows = {(r["tokenizer"], r["lang"]): float(r["parity_vs_eng"])
                for r in csv.DictReader(f)}
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    style_axes(ax)
    n, width = len(LANGS), 0.13
    for i, lang in enumerate(LANGS):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(TOKS))]
        ys = [rows[(t, lang)] for t in TOKS]
        ax.bar(xs, ys, width=width * 0.92, color=SERIES[i], zorder=3,
               label=LANG_NAMES[lang], edgecolor=SURFACE, linewidth=0.5)
    for g, t in enumerate(TOKS):  # selective labels: worst language per group
        worst = max(LANGS, key=lambda l: rows[(t, l)])
        i = LANGS.index(worst)
        ax.annotate(f"{rows[(t, worst)]:.1f}×",
                    (g + (i - (n - 1) / 2) * width, rows[(t, worst)]),
                    textcoords="offset points", xytext=(0, 3),
                    ha="center", fontsize=9, color=INK2)
    ax.axhline(1.0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
    ax.set_xticks(range(len(TOKS)), TOK_NAMES, color=INK2)
    ax.set_ylabel("tokens for identical content, ÷ English", color=INK2)
    ax.set_ylim(0, 17)
    ax.legend(ncols=6, frameon=False, loc="upper right", bbox_to_anchor=(1, 1.02),
              fontsize=9, columnspacing=1.1, handlelength=1.1)
    ax.set_title("The 'Indic premium' is a tokenizer property, not a script property",
                 loc="left", fontsize=13, fontweight="bold", pad=28)
    ax.text(0, 1.045, "Tokens needed for the same 1012 parallel sentences, relative to "
            "English — FLORES-200 devtest; dashed line = English (1.0)",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    fig.tight_layout()
    fig.savefig(HERE / "fig1_parity.png", facecolor=SURFACE, bbox_inches="tight")


def fig2():
    with open(BENCH, newline="", encoding="utf-8") as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)
                if float(r["prompt_len"]) == 3584]
    xs = [r["batch_size"] for r in rows]
    reported = [r["reported_tok_s"] for r in rows]
    goodput = [r["gen_len"] * r["batch_size"] / r["wall_clock_s"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=200)
    style_axes(ax)
    ax.axvspan(CAPACITY, max(xs) + 2, color=GRID, alpha=0.45, zorder=0)
    ax.axvline(CAPACITY, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
    ax.annotate(f"KV capacity: {CAPACITY} sequences\n(preemption beyond this)",
                (CAPACITY + 0.6, 1660), fontsize=8.5, color=INK2)
    ax.plot(xs, reported, color=SERIES[0], linewidth=2, marker="o", markersize=5,
            zorder=3, label="reported_tok_s (counts prefill)")
    ax.plot(xs, goodput, color=SERIES[1], linewidth=2, marker="o", markersize=5,
            zorder=3, label="generation goodput (what users get)")
    labeled = {x for x in xs if x in (24, max(xs))}  # peak row + last row
    for series in (reported, goodput):
        for x, y in zip(xs, series):
            if x in labeled:
                ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                            xytext=(0, 7), ha="center", fontsize=9, color=INK2)
    ax.annotate("×8 gap:\nthe counter is 7/8 prefill", (16.2, 830), fontsize=9,
                color=INK2)
    ax.set_xlabel("offered batch size (prompt 3584, gen 512)", color=INK2)
    ax.set_ylabel("tokens / second", color=INK2)
    ax.set_xticks(xs, [f"{int(x)}" for x in xs])
    ax.set_ylim(0, 1850)
    ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.01, 0.16), fontsize=9)
    ax.set_title("REPORT_v0 planned capacity on the wrong curve",
                 loc="left", fontsize=13, fontweight="bold", pad=26)
    ax.text(0, 1.06, "Long-prompt sweep from bench_log.csv — the counter peaks at "
            "1607 tok/s while users receive 201; both fall past the KV knee",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    fig.tight_layout()
    fig.savefig(HERE / "fig2_throughput.png", facecolor=SURFACE, bbox_inches="tight")


if __name__ == "__main__":
    fig1()
    fig2()
    print(f"figures written to {HERE}")
