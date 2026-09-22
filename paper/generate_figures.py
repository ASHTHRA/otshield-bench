#!/usr/bin/env python3
"""Generate deterministic manuscript figures from the committed v0.6 aggregate."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/v06/20260922T021855Z/aggregate.json"
OUT = Path(__file__).resolve().parent / "figures"
CONDITIONS = ["clean", "delay20", "delay20_jitter5_loss5", "delay40_jitter10", "delay60_jitter10"]
LABELS = ["Clean", "+20 ms", "+20 ms /\n5 ms / 5%", "+40 ms /\n10 ms", "+60 ms /\n10 ms"]


def load() -> dict:
    with SOURCE.open(encoding="utf-8") as stream:
        return json.load(stream)


def style(ax: plt.Axes, ylabel: str) -> None:
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def grouped_metric(data: dict, metric: str, filename: str, ylabel: str) -> None:
    x = np.arange(len(CONDITIONS))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
    for offset, detector, color in [(-width / 2, "polling-burst-v1", "#315b7d"),
                                     (width / 2, "robust-polling-burst-v1", "#c46b2d")]:
        values = [data["conditions"][c]["detectors"][detector][metric]["mean"] for c in CONDITIONS]
        ax.bar(x + offset, values, width, label=detector, color=color)
    ax.set_xticks(x, LABELS)
    ax.set_ylim(0, 1.08)
    style(ax, ylabel)
    ax.legend(frameon=False, loc="lower left")
    fig.savefig(OUT / filename, dpi=220)
    plt.close(fig)


def paired_recall(data: dict) -> None:
    x = np.arange(len(CONDITIONS))
    values, lows, highs = [], [], []
    for condition in CONDITIONS:
        metric = data["conditions"][condition]["paired_robust_minus_baseline"]["recall"]
        values.append(metric["mean"])
        lows.append(metric["mean"] - metric["ci95_unbounded_low"])
        highs.append(metric["ci95_unbounded_high"] - metric["mean"])
    fig, ax = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
    ax.errorbar(x, values, yerr=[lows, highs], fmt="o", capsize=4, color="#4b6f44", lw=1.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, LABELS)
    ax.set_ylim(-0.08, 1.08)
    style(ax, "Robust minus baseline recall")
    ax.set_title("Run-level paired differences (95% unbounded Student-t intervals)", fontsize=9)
    fig.savefig(OUT / "paired_recall_difference.png", dpi=220)
    plt.close(fig)


def resource_cost(data: dict) -> None:
    metrics = [("cpu_time_ms", "CPU time (ms)"), ("wall_time_ms", "Wall time (ms)"),
               ("peak_memory_mb", "Peak traced memory (MB)")]
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.5), constrained_layout=True)
    x = np.arange(len(CONDITIONS))
    for ax, (metric, label) in zip(axes, metrics):
        for detector, color in [("polling-burst-v1", "#315b7d"), ("robust-polling-burst-v1", "#c46b2d")]:
            values = [data["conditions"][c]["detectors"][detector][metric]["mean"] for c in CONDITIONS]
            ax.plot(x, values, marker="o", label=detector, color=color)
        ax.set_xticks(x, ["C", "20", "20/J/L", "40/J", "60/J"])
        style(ax, label)
    axes[0].legend(frameon=False, fontsize=7)
    fig.savefig(OUT / "resource_cost.png", dpi=220)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load()
    grouped_metric(data, "recall", "recall_by_condition.png", "Mean recall")
    grouped_metric(data, "f1", "f1_by_condition.png", "Mean F1")
    paired_recall(data)
    resource_cost(data)
    print(f"Generated four figures from {SOURCE}")


if __name__ == "__main__":
    main()
