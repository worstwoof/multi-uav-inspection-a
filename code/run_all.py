"""Run the complete reproducible Phase-3 pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import csv
import json
import platform
import sys
import time

import numpy as np
import pandas as pd

from core import dump_json, load_case, serializable_case
from solver import solve_problem1, solve_problem2, solve_problem3
import plot_results


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
CASES = ["Case1", "Case2", "Case3", "Case4"]


def public_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return result


def write_results(all_results: Dict[str, Dict[str, Any]]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for case, bundle in all_results.items():
        dump_json(RESULTS / f"input_{case.lower()}.json", serializable_case(bundle["case_data"]))
        for question in ("q1", "q2", "q3", "q3_fixed_fleet"):
            dump_json(RESULTS / f"{question}_{case.lower()}.json", public_result(bundle[question]))
            result = bundle[question]
            validation = result["validation"]
            rows.append({"case_id": case, "question": question, "status": result["status"],
                         "fleet_count": result["fleet_count"],
                         "Tmax_h": result["metrics"]["Tmax_h"], "Tmin_h": result["metrics"]["Tmin_h"],
                         "delta_h": result["metrics"]["delta_h"],
                         "total_distance_km": result["metrics"].get("total_distance_km", 0.0),
                         "total_wait_h": result["metrics"].get("total_wait_h", 0.0),
                         "total_detour_km": result["metrics"].get("total_detour_km", 0.0),
                         "valid": validation["valid"], "task_coverage": validation["task_coverage"],
                         "multiplicity_valid": validation["multiplicity_valid"],
                         "consecutive_point": validation["consecutive_point"],
                         "routes_closed": validation["routes_closed"],
                         "within_9h": validation["within_9h"],
                         "nofly_valid": validation.get("nofly_valid", True)})
    with (RESULTS / "summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # A compact run manifest makes seed/config provenance explicit.
    manifest = {"python": sys.version, "platform": platform.platform(),
                "numpy": np.__version__, "pandas": pd.__version__,
                "q1_q2_seeds": list(range(6)), "q3_seeds": list(range(2)),
                "horizon_h": 9.0, "speed_kmh": 55.0, "service_h": 1 / 12,
                "effective_arrival_rule": "adjacent equal Point_ID blocks merge; A-A-A=1, A-B-A=2",
                "generated_unix": time.time()}
    dump_json(RESULTS / "run_manifest.json", manifest)


def write_report(all_results: Dict[str, Dict[str, Any]]) -> None:
    lines: List[str] = []
    lines.append("# 计算结果\n")
    lines.append("本报告由 `code/run_all.py` 根据 `results/*.json` 自动生成；所有数值均来自本轮真实运行。\n")
    lines.append("## 运行环境\n")
    lines.append(f"- Python: `{sys.version.split()[0]}`；平台：`{platform.platform()}`。")
    lines.append("- 问题一、问题二使用固定种子 0--5 的独立重启；问题三使用固定种子 0--1 并保留动态路线局部搜索。")
    lines.append("- 单位：坐标转为 km，速度 55 km/h，服务 5 min，工作上限 9 h；禁飞窗采用 `[start,end)`。\n")
    lines.append("## 数据读取与预处理\n")
    lines.append("| Case | 物理点 | 展开任务 | 禁飞区 | 理论服务下界 | 理论工作下界 |\n|---|---:|---:|---:|---:|---:|")
    for case, bundle in all_results.items():
        data = bundle["case_data"]
        q1 = bundle["q1"]
        lines.append(f"| {case} | {len(data['points'])} | {len(data['tasks'])} | {len(data['nofly_zones'])} | {q1['theoretical_lb_service']} | {q1['theoretical_lb_work']} |")
    lines.append("\n任务覆盖校验按有效到达段统计：同一路线相邻相同 `Point_ID` 合并，不能用 Excel 原始单元格数量替代。\n")
    for question, title in (("q1", "问题一结果"), ("q2", "问题二结果"), ("q3", "问题三结果"), ("q3_fixed_fleet", "问题三固定原机队对照")):
        lines.append(f"## {title}\n")
        lines.append("| Case | 状态 | UAV 数 | Tmax/h | Tmin/h | 极差/h | 距离/km | 等待/h | 绕行/km | 校验 |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for case, bundle in all_results.items():
            r = bundle[question]
            m, v = r["metrics"], r["validation"]
            lines.append(f"| {case} | {r['status']} | {r['fleet_count']} | {m['Tmax_h']:.4f} | {m['Tmin_h']:.4f} | {m['delta_h']:.4f} | {m.get('total_distance_km', 0):.3f} | {m.get('total_wait_h', 0):.3f} | {m.get('total_detour_km', 0):.3f} | {'通过' if v['valid'] else '未通过'} |")
        lines.append("")
        if question == "q1":
            lines.append("问题一的 `fleet_count` 是从理论下界起逐一搜索后得到的首个固定种子可行解，并已由独立验证器复核；由于本阶段未调用精确 MIP 不可行性证书，`minimum_certified=false`，不能将启发式首个可行数量表述为已证明全局最低。问题三同理只报告最小已验证机队。\n")
    lines.append("## 约束与一致性校验\n")
    lines.append("所有正式 `q1/q2/q3` JSON 都经过独立验证器重算距离、服务时间、任务覆盖、有效到达段、路线闭环和 9 h；`q3` 另外重算线段-圆几何、时间重叠、服务点、基地和等待。固定原机队对照若超时，状态保留为 `infeasible_under_9h`，不进入正式 q3 可行表。\n")
    lines.append("## 图表\n")
    lines.append("由真实结果生成：`q1_routes`、`q3_dynamic_routes`、`work_hours`、`case_comparison`、`multistart_convergence`，每张同时输出 PDF、SVG 和 PNG。\n")
    lines.append("## 可复现运行方式\n")
    lines.append("```powershell\npython code/run_all.py\n```")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "RESULTS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    all_results: Dict[str, Dict[str, Any]] = {}
    for case in CASES:
        print(f"[{case}] loading and solving", flush=True)
        case_data = load_case(case)
        q1 = solve_problem1(case_data, seeds=range(6), max_fleet_extra=6)
        q2 = solve_problem2(case_data, q1, seeds=range(6))
        q3, fixed = solve_problem3(case_data, q2, q1, seeds=range(2), max_extra=10)
        all_results[case] = {"case_data": case_data, "q1": q1, "q2": q2, "q3": q3,
                             "q3_fixed_fleet": fixed}
        print(f"[{case}] q1 N={q1['fleet_count']} q2 N={q2['fleet_count']} q3 N={q3['fleet_count']}", flush=True)
    write_results(all_results)
    plot_results.generate_all()
    write_report(all_results)
    print("Results, figures and report written.", flush=True)


if __name__ == "__main__":
    main()
