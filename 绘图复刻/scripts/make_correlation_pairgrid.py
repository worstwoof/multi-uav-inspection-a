from __future__ import annotations

import csv
import json
import math
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
from matplotlib.lines import Line2D


CASES = ["Case1", "Case2", "Case3", "Case4"]
QUESTIONS = ["Q1", "Q2", "Q3"]
QUESTION_COLORS = {"Q1": "#3B6EA8", "Q2": "#2E8B57", "Q3": "#C44E52"}


@dataclass(frozen=True)
class Variable:
    key: str
    label: str


VARIABLES = [
    Variable("task_count", "Tasks"),
    Variable("distance_km", "Distance (km)"),
    Variable("service_h", "Service (h)"),
    Variable("wait_h", "Waiting (h)"),
    Variable("detour_km", "Detour (km)"),
    Variable("work_h", "Work time (h)"),
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.45,
            "ytick.major.width": 0.45,
            "xtick.major.size": 2.0,
            "ytick.major.size": 2.0,
        }
    )


def load_route_rows() -> list[dict[str, float | str | int]]:
    rows: list[dict[str, float | str | int]] = []
    for case in CASES:
        for question in QUESTIONS:
            result = json.loads(
                (WORKSPACE / "results" / f"{question.lower()}_{case.lower()}.json").read_text(encoding="utf-8")
            )
            for idx, (route, metric) in enumerate(zip(result["routes"], result["metrics"]["route_metrics"], strict=True), 1):
                rows.append(
                    {
                        "case_id": case,
                        "question": question,
                        "uav_id": idx,
                        "task_count": len(route),
                        "distance_km": float(metric["distance_km"]),
                        "service_h": float(metric["service_h"]),
                        "wait_h": float(metric.get("wait_h", 0.0)),
                        "detour_km": float(metric.get("detour_km", 0.0)),
                        "work_h": float(metric["work_h"]),
                    }
                )
    return rows


def write_source_csv(rows: list[dict[str, float | str | int]]) -> None:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "correlation_pairgrid_routes.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fit_line_with_ci(x: np.ndarray, y: np.ndarray, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return None
    slope, intercept = np.polyfit(x, y, deg=1)
    fitted_grid = slope * grid + intercept
    residuals = y - (slope * x + intercept)
    n = x.size
    s_err = math.sqrt(np.sum(residuals ** 2) / max(n - 2, 1))
    ssx = np.sum((x - x.mean()) ** 2)
    se = s_err * np.sqrt(1.0 / n + (grid - x.mean()) ** 2 / max(ssx, 1e-12))
    ci = 1.96 * se
    return fitted_grid, fitted_grid - ci, fitted_grid + ci


def fisher_p_value(r: float, n: int) -> float:
    if not np.isfinite(r):
        return 1.0
    clipped = float(np.clip(r, -0.999999, 0.999999))
    z = 0.5 * math.log((1 + clipped) / (1 - clipped)) * math.sqrt(max(n - 3, 1))
    return math.erfc(abs(z) / math.sqrt(2.0))


def stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def padded_limits(values: np.ndarray) -> tuple[float, float]:
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-12:
        return low - 0.5, high + 0.5
    pad = (high - low) * 0.08
    return low - pad, high + pad


def draw_scatter(ax: plt.Axes, x: np.ndarray, y: np.ndarray, groups: list[str]) -> None:
    for question in QUESTIONS:
        mask = np.asarray([g == question for g in groups])
        ax.scatter(x[mask], y[mask], s=15, color=QUESTION_COLORS[question], alpha=0.72,
                   edgecolors="white", linewidths=0.25)
    grid = np.linspace(x.min(), x.max(), 100)
    fit = fit_line_with_ci(x, y, grid)
    if fit is not None:
        y_fit, y_low, y_high = fit
        ax.fill_between(grid, y_low, y_high, color="#A9A9A9", alpha=0.20, linewidth=0)
        ax.plot(grid, y_fit, color="#333333", lw=0.85)
    ax.set_xlim(*padded_limits(x))
    ax.set_ylim(*padded_limits(y))


def draw_hist(ax: plt.Axes, values: np.ndarray) -> None:
    bins = min(10, max(5, int(math.sqrt(values.size))))
    ax.hist(values, bins=bins, color="#9ECAE1", edgecolor="#2B5D73", linewidth=0.5, alpha=0.9)


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    rows = load_route_rows()
    write_source_csv(rows)
    data = np.column_stack([[float(row[var.key]) for row in rows] for var in VARIABLES])
    groups = [str(row["question"]) for row in rows]
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(data, rowvar=False)

    n_vars = len(VARIABLES)
    cmap = mpl.colormaps["RdBu_r"]
    norm = mpl.colors.Normalize(vmin=-1.0, vmax=1.0)
    fig = plt.figure(figsize=(10.0, 9.0))
    grid_spec = fig.add_gridspec(n_vars, n_vars, left=0.07, right=0.91, bottom=0.07,
                                 top=0.93, wspace=0.09, hspace=0.09)

    for row_idx in range(n_vars):
        for col_idx in range(n_vars):
            ax = fig.add_subplot(grid_spec[row_idx, col_idx])
            x, y = data[:, col_idx], data[:, row_idx]
            if row_idx > col_idx:
                draw_scatter(ax, x, y, groups)
            elif row_idx == col_idx:
                draw_hist(ax, x)
            else:
                r = corr[row_idx, col_idx]
                value = 0.0 if not np.isfinite(r) else float(r)
                ax.set_facecolor(cmap(norm(value)))
                ax.set_xticks([])
                ax.set_yticks([])
                color = "white" if abs(value) >= 0.55 else "#222222"
                ax.text(0.5, 0.46, f"{value:.2f}", transform=ax.transAxes,
                        ha="center", va="center", fontsize=8, color=color)
                ax.text(0.5, 0.68, stars(fisher_p_value(value, len(rows))), transform=ax.transAxes,
                        ha="center", va="center", fontsize=7, fontweight="bold", color=color)
            for spine in ax.spines.values():
                spine.set_color("#777777")
                spine.set_linewidth(0.45)
            ax.tick_params(labelsize=5, pad=0.8)
            if row_idx < n_vars - 1:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel(VARIABLES[col_idx].label, fontsize=7, labelpad=2)
            if col_idx > 0:
                ax.set_yticklabels([])
            else:
                ax.set_ylabel(VARIABLES[row_idx].label, fontsize=7, labelpad=2)

    cax = fig.add_axes([0.93, 0.23, 0.022, 0.62])
    colorbar = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    colorbar.set_label("Pearson correlation", fontsize=8)
    colorbar.ax.tick_params(labelsize=6)
    legend = [Line2D([0], [0], marker="o", linestyle="", color=QUESTION_COLORS[q], label=q, markersize=5)
              for q in QUESTIONS]
    fig.legend(handles=legend, loc="upper right", bbox_to_anchor=(0.985, 0.975),
               frameon=False, fontsize=7, title="Question", title_fontsize=8)

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    make_figure(ROOT / "outputs" / "correlation_pairgrid_real")


if __name__ == "__main__":
    main()
