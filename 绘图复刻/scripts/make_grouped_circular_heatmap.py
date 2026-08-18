from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


CASES = ["Case1", "Case2", "Case3", "Case4"]
QUESTIONS = ["Q1", "Q2", "Q3"]
CASE_COLORS = {
    "Case1": "#3B6EA8",
    "Case2": "#2E8B57",
    "Case3": "#C97924",
    "Case4": "#A34A5E",
}


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    cmap: str


METRICS = [
    Metric("fleet_count", "UAV number", "", "Blues"),
    Metric("Tmax_h", "Maximum work time", "h", "Greens"),
    Metric("delta_h", "Work-time range", "h", "Oranges"),
    Metric("distance_per_task_km", "Distance per arrival", "km", "Purples"),
    Metric("total_wait_h", "Total waiting", "h", "Reds"),
    Metric("total_detour_km", "Total detour", "km", "Greys"),
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 9,
        }
    )


def load_real_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for case in CASES:
        input_data = json.loads((WORKSPACE / "results" / f"input_{case.lower()}.json").read_text(encoding="utf-8"))
        task_count = len(input_data["tasks"])
        for question in QUESTIONS:
            result = json.loads(
                (WORKSPACE / "results" / f"{question.lower()}_{case.lower()}.json").read_text(encoding="utf-8")
            )
            metrics = result["metrics"]
            rows.append(
                {
                    "case_id": case,
                    "question": question,
                    "fleet_count": float(result["fleet_count"]),
                    "Tmax_h": float(metrics["Tmax_h"]),
                    "delta_h": float(metrics["delta_h"]),
                    "distance_per_task_km": float(metrics["total_distance_km"]) / task_count,
                    "total_wait_h": float(metrics.get("total_wait_h", 0.0)),
                    "total_detour_km": float(metrics.get("total_detour_km", 0.0)),
                }
            )
    return rows


def normalize_columns(rows: list[dict[str, float | str]]) -> dict[str, np.ndarray]:
    normalized: dict[str, np.ndarray] = {}
    for metric in METRICS:
        values = np.asarray([float(row[metric.key]) for row in rows], dtype=float)
        low, high = float(values.min()), float(values.max())
        normalized[metric.key] = np.zeros_like(values) if high - low < 1e-12 else (values - low) / (high - low)
    return normalized


def write_source_csv(rows: list[dict[str, float | str]], normalized: dict[str, np.ndarray]) -> None:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "grouped_circular_heatmap.csv"
    fieldnames = ["case_id", "question"] + [m.key for m in METRICS] + [f"normalized_{m.key}" for m in METRICS]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows):
            out = dict(row)
            out.update({f"normalized_{m.key}": float(normalized[m.key][idx]) for m in METRICS})
            writer.writerow(out)


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    rows = load_real_rows()
    normalized = normalize_columns(rows)
    write_source_csv(rows, normalized)

    n_items = len(rows)
    theta = np.linspace(0, 2 * np.pi, n_items, endpoint=False)
    width = 2 * np.pi / n_items * 0.90
    group_radius, group_height = 1.08, 0.13
    ring_radius, ring_height, ring_gap = 1.34, 0.18, 0.025

    fig = plt.figure(figsize=(11.6, 10.4), facecolor="white")
    ax = fig.add_axes([0.03, 0.03, 0.76, 0.94], projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_axis_off()

    for angle, row in zip(theta, rows, strict=True):
        ax.bar(angle, group_height, width=width, bottom=group_radius,
               color=CASE_COLORS[str(row["case_id"])], edgecolor="white", linewidth=0.8)

    for metric_idx, metric in enumerate(METRICS):
        radius = ring_radius + metric_idx * (ring_height + ring_gap)
        cmap = mpl.colormaps[metric.cmap]
        colors = cmap(0.16 + 0.80 * normalized[metric.key])
        ax.bar(theta, ring_height, width=width, bottom=radius, color=colors,
               edgecolor="white", linewidth=0.75)

    outer_radius = ring_radius + len(METRICS) * (ring_height + ring_gap)
    ax.set_ylim(0, outer_radius + 0.42)
    for angle, row in zip(theta, rows, strict=True):
        degrees = np.degrees(angle)
        rotation = -degrees
        if 90 < degrees < 270:
            rotation += 180
        ha = "left" if degrees < 180 else "right"
        ax.text(angle, outer_radius + 0.13, f"{row['case_id']}–{row['question']}",
                rotation=rotation, rotation_mode="anchor", ha=ha, va="center", fontsize=8)

    ax.text(0.5, 0.53, "4 Cases × 3 Questions", transform=ax.transAxes,
            ha="center", va="center", fontsize=12, fontweight="bold")
    ax.text(0.5, 0.48, "Each ring is normalized independently", transform=ax.transAxes,
            ha="center", va="center", fontsize=8, color="#555555")

    legend_ax = fig.add_axes([0.79, 0.17, 0.20, 0.66])
    legend_ax.axis("off")
    legend_ax.text(0, 1.02, "Rings: inner → outer", fontsize=10, fontweight="bold")
    for idx, metric in enumerate(METRICS):
        values = np.asarray([float(r[metric.key]) for r in rows])
        legend_ax.add_patch(
            plt.Rectangle((0.0, 0.90 - idx * 0.105), 0.10, 0.045,
                          facecolor=mpl.colormaps[metric.cmap](0.72), edgecolor="none")
        )
        suffix = f" {metric.unit}" if metric.unit else ""
        legend_ax.text(0.13, 0.925 - idx * 0.105, metric.label, va="center", fontsize=8.5)
        legend_ax.text(0.13, 0.895 - idx * 0.105,
                       f"range {values.min():.3g}–{values.max():.3g}{suffix}",
                       va="center", fontsize=7.2, color="#666666")
    handles = [Patch(facecolor=color, label=case) for case, color in CASE_COLORS.items()]
    legend_ax.legend(handles=handles, title="Case groups", frameon=False,
                     loc="lower left", bbox_to_anchor=(-0.02, 0.02), fontsize=8)

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    make_figure(ROOT / "outputs" / "grouped_circular_heatmap_real")


if __name__ == "__main__":
    main()
