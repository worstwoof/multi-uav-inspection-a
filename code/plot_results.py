"""Generate all data-driven figures from results/*.json only."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
CASES = ["Case1", "Case2", "Case3", "Case4"]


plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
})


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        kwargs = {"dpi": 240} if ext == "png" else {}
        fig.savefig(FIGURES / f"{stem}.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


def plot_static_routes(inputs: Dict[str, Any], q1: Dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 9.0), constrained_layout=True)
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    for ax, case in zip(axes.flat, CASES):
        data, result = inputs[case], q1[case]
        tasks = {t["task_id"]: t for t in data["tasks"]}
        for k, route in enumerate(result["routes"]):
            xy = [(0.0, 0.0)] + [(tasks[t]["x"], tasks[t]["y"]) for t in route] + [(0.0, 0.0)]
            ax.plot([p[0] for p in xy], [p[1] for p in xy], lw=0.8, alpha=0.8,
                    color=colors[k % len(colors)], label=f"UAV {k + 1}")
        for level, marker, color in (("I", "^", "#c0392b"), ("II", "s", "#e67e22"), ("III", "o", "#2c3e50")):
            pts = [p for p in data["points"] if p["level"] == level]
            ax.scatter([p["x"] for p in pts], [p["y"] for p in pts], s=16, marker=marker,
                       color=color, edgecolors="white", linewidths=0.3, zorder=3, label=f"{level}级")
        ax.scatter([0], [0], marker="*", s=80, color="black", zorder=4, label="基地")
        ax.set_title(f"{case}: N={result['fleet_count']}, $T_{{max}}$={result['metrics']['Tmax_h']:.2f} h")
        ax.set_xlabel("X / km")
        ax.set_ylabel("Y / km")
        ax.set_aspect("equal", adjustable="datalim")
        ax.legend(fontsize=6, ncol=3, frameon=False)
    _save(fig, "q1_routes")


def plot_dynamic_routes(inputs: Dict[str, Any], q3: Dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 9.0), constrained_layout=True)
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    for ax, case in zip(axes.flat, CASES):
        data, result = inputs[case], q3[case]
        metrics = result["metrics"]["route_metrics"]
        for k, route in enumerate(metrics):
            for leg in route["legs"]:
                path = leg["path"]
                ax.plot([p[0] for p in path], [p[1] for p in path], lw=0.8,
                        color=colors[k % len(colors)], alpha=0.8)
        for z in data["nofly_zones"]:
            circle = Circle((z["x"], z["y"]), z["radius"], facecolor="#e74c3c",
                            edgecolor="#922b21", alpha=0.12 if z["end_h"] > z["start_h"] else 0.03,
                            linestyle="--", linewidth=0.8)
            ax.add_patch(circle)
            ax.text(z["x"], z["y"], z["zone_id"], ha="center", va="center", fontsize=6)
        ax.scatter([p["x"] for p in data["points"]], [p["y"] for p in data["points"]],
                   s=9, color="#34495e", zorder=3)
        ax.scatter([0], [0], marker="*", s=80, color="black", zorder=4)
        ax.set_title(f"{case}: N={result['fleet_count']}, $T_{{max}}$={result['metrics']['Tmax_h']:.2f} h")
        ax.set_xlabel("X / km")
        ax.set_ylabel("Y / km")
        ax.set_aspect("equal", adjustable="datalim")
    _save(fig, "q3_dynamic_routes")


def plot_work_hours(q1: Dict[str, Any], q2: Dict[str, Any], q3: Dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.5), constrained_layout=True)
    palette = {"q1": "#4c78a8", "q2": "#59a14f", "q3": "#e15759"}
    for ax, case in zip(axes.flat, CASES):
        offset = 0
        ticks, labels = [], []
        for key, result in (("q1", q1[case]), ("q2", q2[case]), ("q3", q3[case])):
            times = [r["work_h"] for r in result["metrics"]["route_metrics"]]
            xs = np.arange(len(times)) + offset
            ax.bar(xs, times, width=0.8, color=palette[key], alpha=0.85, label=key.upper())
            ticks.extend(xs.tolist())
            labels.extend([str(i + 1) for i in range(len(times))])
            offset += len(times) + 1
        ax.axhline(9.0, color="black", linestyle="--", linewidth=0.9, label="9 h 上限")
        ax.set_title(case)
        ax.set_ylabel("工作时间 / h")
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=6)
        ax.set_xlabel("各阶段 UAV 编号（分组排列）")
        ax.legend(frameon=False, ncol=4, fontsize=7)
    _save(fig, "work_hours")


def plot_case_comparison(q1: Dict[str, Any], q2: Dict[str, Any], q3: Dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
    x = np.arange(len(CASES))
    width = 0.24
    for j, (name, data, color) in enumerate((("Q1", q1, "#4c78a8"), ("Q2", q2, "#59a14f"), ("Q3", q3, "#e15759"))):
        axes[0].bar(x + (j - 1) * width, [data[c]["metrics"]["Tmax_h"] for c in CASES], width,
                    label=name, color=color)
        axes[1].bar(x + (j - 1) * width, [data[c]["metrics"]["delta_h"] for c in CASES], width,
                    label=name, color=color)
        axes[2].bar(x + (j - 1) * width, [data[c]["fleet_count"] for c in CASES], width,
                    label=name, color=color)
    for ax, ylabel in zip(axes, ("最大工作时间 / h", "工作时间极差 / h", "无人机数量")):
        ax.set_xticks(x)
        ax.set_xticklabels(CASES)
        ax.set_ylabel(ylabel)
        ax.legend(frameon=False)
    _save(fig, "case_comparison")


def plot_convergence(q1: Dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), constrained_layout=True)
    for ax, case in zip(axes.flat, CASES):
        result = q1[case]
        selected = next(item for item in result["fleet_search"] if item["fleet"] == result["fleet_count"])
        runs = selected.get("seed_runs", [])
        seeds, values, cumulative = [], [], []
        best = math.inf
        for run in runs:
            if run.get("feasible") and run.get("Tmax_h") is not None:
                seeds.append(run["seed"])
                values.append(run["Tmax_h"])
                best = min(best, run["Tmax_h"])
                cumulative.append(best)
        if seeds:
            ax.plot(seeds, values, marker="o", lw=0.8, color="#9ecae1", label="单次结果")
            ax.plot(seeds, cumulative, marker="s", lw=1.5, color="#08519c", label="累计最好")
        ax.axhline(9.0, color="black", linestyle="--", linewidth=0.8)
        ax.set_title(f"{case}: N={result['fleet_count']}")
        ax.set_xlabel("随机种子")
        ax.set_ylabel("$T_{max}$ / h")
        ax.legend(frameon=False, fontsize=7)
    _save(fig, "multistart_convergence")


def generate_all() -> None:
    inputs = {case: _load(RESULTS / f"input_{case.lower()}.json") for case in CASES}
    q1 = {case: _load(RESULTS / f"q1_{case.lower()}.json") for case in CASES}
    q2 = {case: _load(RESULTS / f"q2_{case.lower()}.json") for case in CASES}
    q3 = {case: _load(RESULTS / f"q3_{case.lower()}.json") for case in CASES}
    plot_static_routes(inputs, q1)
    plot_dynamic_routes(inputs, q3)
    plot_work_hours(q1, q2, q3)
    plot_case_comparison(q1, q2, q3)
    plot_convergence(q1)


if __name__ == "__main__":
    generate_all()
