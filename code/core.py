"""Shared data, geometry, route evaluation and independent validation utilities."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import copy
import json
import math
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "A 题"
SCALE_KM = 0.1
SPEED_KMH = 55.0
SERVICE_H = 5.0 / 60.0
HORIZON_H = 9.0
BASE = (0.0, 0.0)
EPS = 1e-9


@dataclass(frozen=True)
class Point:
    point_id: str
    x: float
    y: float
    level: str
    required_visits: int


@dataclass(frozen=True)
class Task:
    task_id: str
    point_id: str
    visit_no: int
    x: float
    y: float
    service_h: float = SERVICE_H


@dataclass(frozen=True)
class Zone:
    zone_id: str
    x: float
    y: float
    radius: float
    start_h: float
    end_h: float
    start_clock: str
    end_clock: str

    @property
    def active(self) -> bool:
        return self.end_h > self.start_h + EPS


def _parse_clock(value: Any) -> Tuple[float, str]:
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        raise ValueError(f"Invalid clock value: {value!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    return (hour * 60 + minute - 8 * 60) / 60.0, f"{hour:02d}:{minute:02d}"


def clock_from_rel(hours: float) -> str:
    minutes = int(round(8 * 60 + hours * 60))
    minutes = max(0, minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def load_case(case_id: str, data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    points_df = pd.read_excel(data_dir / "附件1.xlsx", sheet_name=case_id)
    zones_df = pd.read_excel(data_dir / "附件2.xlsx", sheet_name=case_id)
    required_cols = {"Point_ID", "X_Coordinate", "Y_Coordinate", "Inspection_Level"}
    if set(points_df.columns) != required_cols:
        raise ValueError(f"{case_id}: unexpected point columns {list(points_df.columns)}")
    zone_cols = {"Zone_ID", "Center_X", "Center_Y", "Radius", "Start_Time", "End_Time"}
    if set(zones_df.columns) != zone_cols:
        raise ValueError(f"{case_id}: unexpected zone columns {list(zones_df.columns)}")
    levels = {"I": 3, "II": 2, "III": 1}
    points: List[Point] = []
    seen = set()
    for row in points_df.itertuples(index=False):
        pid = str(row.Point_ID)
        if pid in seen:
            raise ValueError(f"{case_id}: duplicate Point_ID {pid}")
        seen.add(pid)
        level = str(row.Inspection_Level).strip()
        if level not in levels:
            raise ValueError(f"{case_id}: unknown inspection level {level}")
        points.append(Point(pid, float(row.X_Coordinate) * SCALE_KM,
                            float(row.Y_Coordinate) * SCALE_KM, level, levels[level]))
    zones: List[Zone] = []
    for row in zones_df.itertuples(index=False):
        start_h, start_clock = _parse_clock(row.Start_Time)
        end_h, end_clock = _parse_clock(row.End_Time)
        if end_h < start_h - EPS:
            raise ValueError(f"{case_id}: zone {row.Zone_ID} ends before it starts")
        zones.append(Zone(str(row.Zone_ID), float(row.Center_X) * SCALE_KM,
                          float(row.Center_Y) * SCALE_KM, float(row.Radius) * SCALE_KM,
                          start_h, end_h, start_clock, end_clock))
    tasks = expand_tasks(case_id, points)
    return {
        "case_id": case_id,
        "base": {"x": BASE[0], "y": BASE[1]},
        "coordinate_scale_km": SCALE_KM,
        "speed_kmh": SPEED_KMH,
        "service_hours": SERVICE_H,
        "max_work_hours": HORIZON_H,
        "start_clock": "08:00",
        "points": [asdict(p) for p in points],
        "tasks": [asdict(t) for t in tasks],
        "nofly_zones": [asdict(z) for z in zones],
        "_points": {p.point_id: p for p in points},
        "_tasks": {t.task_id: t for t in tasks},
        "_zones": zones,
    }


def expand_tasks(case_id: str, points: Sequence[Point]) -> List[Task]:
    tasks: List[Task] = []
    for point in points:
        for visit in range(1, point.required_visits + 1):
            tasks.append(Task(f"{case_id}-P{int(float(point.point_id)):03d}-V{visit:02d}",
                              point.point_id, visit, point.x, point.y))
    return tasks


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))


def point_xy(case_data: Dict[str, Any], point_id: str) -> Tuple[float, float]:
    p = case_data["_points"][str(point_id)]
    return p.x, p.y


def task_xy(case_data: Dict[str, Any], task_id: str) -> Tuple[float, float]:
    t = case_data["_tasks"][str(task_id)]
    return t.x, t.y


def route_point_ids(case_data: Dict[str, Any], task_ids: Sequence[str]) -> List[str]:
    return [case_data["_tasks"][str(t)].point_id for t in task_ids]


def effective_arrivals(point_ids: Sequence[str]) -> List[str]:
    """Merge adjacent equal physical points; each remaining block is one arrival."""
    blocks: List[str] = []
    for pid in point_ids:
        pid = str(pid)
        if not blocks or blocks[-1] != pid:
            blocks.append(pid)
    return blocks


def theoretical_lower_bounds(case_data: Dict[str, Any]) -> Dict[str, int]:
    service = sum(t.service_h for t in case_data["_tasks"].values())
    max_roundtrip = max(2 * distance(BASE, (p.x, p.y)) / SPEED_KMH for p in case_data["_points"].values())
    return {
        "service": int(math.ceil(service / HORIZON_H - EPS)),
        "work": int(math.ceil((service + max_roundtrip) / HORIZON_H - EPS)),
        "max": int(max(math.ceil(service / HORIZON_H - EPS), math.ceil((service + max_roundtrip) / HORIZON_H - EPS))),
    }


def evaluate_static_route(case_data: Dict[str, Any], task_ids: Sequence[str]) -> Dict[str, Any]:
    current = BASE
    total_distance = 0.0
    legs: List[Dict[str, Any]] = []
    for task_id in task_ids:
        target = task_xy(case_data, task_id)
        leg_d = distance(current, target)
        legs.append({"from": [current[0], current[1]], "to": [target[0], target[1]],
                     "distance_km": leg_d, "task_id": task_id})
        total_distance += leg_d
        current = target
    back_d = distance(current, BASE)
    legs.append({"from": [current[0], current[1]], "to": [BASE[0], BASE[1]],
                 "distance_km": back_d, "task_id": "BASE_RETURN"})
    total_distance += back_d
    service_h = len(task_ids) * SERVICE_H
    flight_h = total_distance / SPEED_KMH
    return {"distance_km": total_distance, "flight_h": flight_h,
            "service_h": service_h, "wait_h": 0.0,
            "work_h": flight_h + service_h, "legs": legs,
            "finish_clock": clock_from_rel(flight_h + service_h)}


def static_solution_metrics(case_data: Dict[str, Any], routes: Sequence[Sequence[str]]) -> Dict[str, Any]:
    route_metrics = [evaluate_static_route(case_data, route) for route in routes]
    times = [m["work_h"] for m in route_metrics]
    return {"route_metrics": route_metrics, "Tmax_h": max(times) if times else 0.0,
            "Tmin_h": min(times) if times else 0.0,
            "delta_h": (max(times) - min(times)) if times else 0.0,
            "total_distance_km": sum(m["distance_km"] for m in route_metrics),
            "total_wait_h": 0.0, "total_detour_km": 0.0}


def validate_solution(case_data: Dict[str, Any], routes: Sequence[Sequence[str]], question: str = "q1",
                      fleet_expected: Optional[int] = None, horizon: float = HORIZON_H,
                      dynamic_details: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    errors: List[str] = []
    expected = set(case_data["_tasks"])
    flat = [str(t) for route in routes for t in route]
    counts = {t: flat.count(t) for t in set(flat)}
    if set(flat) != expected or len(flat) != len(expected) or any(v != 1 for v in counts.values()):
        errors.append("task_coverage")
    if fleet_expected is not None and len(routes) != fleet_expected:
        errors.append(f"fleet_count:{len(routes)}!={fleet_expected}")
    route_closed = True
    consecutive = True
    multiplicity: Dict[str, int] = {p.point_id: 0 for p in case_data["_points"].values()}
    route_metrics: List[Dict[str, Any]] = []
    for idx, route in enumerate(routes, 1):
        pids = route_point_ids(case_data, route)
        if any(a == b for a, b in zip(pids, pids[1:])):
            consecutive = False
            errors.append(f"route_{idx}:consecutive_point")
        blocks = effective_arrivals(pids)
        for pid in blocks:
            multiplicity[pid] = multiplicity.get(pid, 0) + 1
        m = evaluate_static_route(case_data, route)
        route_metrics.append(m)
        if not route or m["legs"][0]["from"] != [0.0, 0.0] or m["legs"][-1]["to"] != [0.0, 0.0]:
            route_closed = False
            errors.append(f"route_{idx}:not_closed")
        if m["work_h"] > horizon + 1e-7:
            errors.append(f"route_{idx}:over_horizon")
    for pid, point in case_data["_points"].items():
        if multiplicity.get(pid, 0) != point.required_visits:
            errors.append(f"multiplicity:{pid}:{multiplicity.get(pid, 0)}!={point.required_visits}")
    metrics = {"route_metrics": route_metrics,
               "Tmax_h": max((m["work_h"] for m in route_metrics), default=0.0),
               "Tmin_h": min((m["work_h"] for m in route_metrics), default=0.0)}
    metrics["delta_h"] = metrics["Tmax_h"] - metrics["Tmin_h"]
    metrics["total_distance_km"] = sum(m["distance_km"] for m in route_metrics)
    return {"valid": not errors, "errors": errors,
            "task_coverage": "task_coverage" not in errors,
            "consecutive_point": consecutive,
            "multiplicity_valid": not any(e.startswith("multiplicity:") for e in errors),
            "routes_closed": route_closed,
            "within_9h": all(m["work_h"] <= horizon + 1e-7 for m in route_metrics),
            "metrics": metrics}


def circle_segment_interval(a: Tuple[float, float], b: Tuple[float, float],
                            center: Tuple[float, float], radius: float,
                            eps: float = 1e-9) -> Optional[Tuple[float, float]]:
    """Return the lambda interval where a segment is inside/on a circle."""
    ax, ay = a[0] - center[0], a[1] - center[1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    aa = dx * dx + dy * dy
    if aa <= eps:
        return (0.0, 1.0) if ax * ax + ay * ay <= (radius + eps) ** 2 else None
    bb = 2 * (ax * dx + ay * dy)
    cc = ax * ax + ay * ay - (radius + eps) ** 2
    disc = bb * bb - 4 * aa * cc
    if disc < -eps:
        return None
    if disc < 0:
        disc = 0.0
    root = math.sqrt(disc)
    lo = max(0.0, min(1.0, (-bb - root) / (2 * aa)))
    hi = max(0.0, min(1.0, (-bb + root) / (2 * aa)))
    if hi < -eps or lo > 1 + eps or hi < lo - eps:
        return None
    return (min(lo, hi), max(lo, hi))


def point_in_zone(point: Tuple[float, float], zone: Zone, eps: float = 1e-8) -> bool:
    return distance(point, (zone.x, zone.y)) <= zone.radius + eps


def zone_active_overlap(start: float, end: float, zone: Zone) -> bool:
    return zone.active and max(start, zone.start_h) < min(end, zone.end_h) - 1e-9


def _segment_conflicts(a: Tuple[float, float], b: Tuple[float, float], depart: float,
                      zone: Zone) -> Optional[Dict[str, float]]:
    interval = circle_segment_interval(a, b, (zone.x, zone.y), zone.radius)
    if interval is None:
        return None
    length = distance(a, b)
    t0 = depart + interval[0] * length / SPEED_KMH
    t1 = depart + interval[1] * length / SPEED_KMH
    if zone_active_overlap(t0, t1, zone):
        return {"lambda_in": interval[0], "lambda_out": interval[1],
                "enter_h": t0, "exit_h": t1}
    return None


def _tangent_detour(a: Tuple[float, float], b: Tuple[float, float], zone: Zone) -> Optional[Dict[str, Any]]:
    """Shortest tangent-arc polyline around one circle, represented by sampled points."""
    c = (zone.x, zone.y)
    r = zone.radius * (1.0 + 1e-7)
    ra, rb = distance(a, c), distance(b, c)
    if ra <= r or rb <= r:
        return None
    pa, pb = math.atan2(a[1] - c[1], a[0] - c[0]), math.atan2(b[1] - c[1], b[0] - c[0])
    da, db = math.acos(min(1.0, r / ra)), math.acos(min(1.0, r / rb))
    candidates: List[Tuple[float, List[Tuple[float, float]], float]] = []
    for sa in (-1.0, 1.0):
        for sb in (-1.0, 1.0):
            ta, tb = pa + sa * da, pb + sb * db
            qa = (c[0] + r * math.cos(ta), c[1] + r * math.sin(ta))
            qb = (c[0] + r * math.cos(tb), c[1] + r * math.sin(tb))
            best_arc = None
            for direction in (-1.0, 1.0):
                delta = (tb - ta) % (2 * math.pi) if direction > 0 else (ta - tb) % (2 * math.pi)
                if delta > math.pi * 2 - 1e-9:
                    delta = 0.0
                arc_len = r * delta
                n = max(2, int(math.ceil(delta / (math.pi / 18))))
                arc = []
                for j in range(n + 1):
                    frac = j / n
                    angle = ta + direction * delta * frac
                    arc.append((c[0] + r * math.cos(angle), c[1] + r * math.sin(angle)))
                length = distance(a, qa) + arc_len + distance(qb, b)
                cand = (length, [a, qa] + arc[1:-1] + [qb, b], arc_len)
                if best_arc is None or cand[0] < best_arc[0]:
                    best_arc = cand
            if best_arc is not None:
                candidates.append(best_arc)
    if not candidates:
        return None
    length, points, arc_len = min(candidates, key=lambda x: x[0])
    return {"points": points, "distance_km": length, "detour_km": max(0.0, length - distance(a, b)), "arc_km": arc_len}


def _path_zone_conflict(points: Sequence[Tuple[float, float]], depart: float,
                        zone: Zone) -> Optional[Dict[str, Any]]:
    t = depart
    for a, b in zip(points, points[1:]):
        seg_d = distance(a, b)
        conflict = _segment_conflicts(a, b, t, zone)
        if conflict is not None:
            return conflict
        t += seg_d / SPEED_KMH
    return None


def plan_dynamic_edge(a: Tuple[float, float], b: Tuple[float, float], depart: float,
                      zones: Sequence[Zone], allow_wait: bool = True) -> Dict[str, Any]:
    """Earliest safe edge among direct, safe waiting, and tangent detours."""
    direct_d = distance(a, b)
    candidates: List[Dict[str, Any]] = []
    direct_end = depart + direct_d / SPEED_KMH
    conflicts = []
    for z in zones:
        c = _segment_conflicts(a, b, depart, z)
        if c is not None:
            conflicts.append((z, c))
    if not conflicts:
        candidates.append({"path": [a, b], "distance_km": direct_d, "wait_h": 0.0,
                           "depart_h": depart, "arrive_h": direct_end, "action": "direct",
                           "detour_km": 0.0, "conflicts": []})
    if allow_wait and conflicts:
        # Waiting at an endpoint is legal only while the endpoint stays outside
        # every active zone.  Re-evaluate the direct edge after each proposed
        # delay because a later window can become the new blocking interval.
        wait_to = depart
        feasible_wait = True
        for _ in range(len(zones) + 2):
            current_conflicts = [(z, _segment_conflicts(a, b, wait_to, z))
                                 for z in zones]
            current_conflicts = [(z, c) for z, c in current_conflicts if c is not None]
            if not current_conflicts:
                break
            next_wait = max(wait_to + 1e-8, max(z.end_h for z, _ in current_conflicts))
            if any(z.active and point_in_zone(a, z) and zone_active_overlap(depart, next_wait, z)
                   for z in zones):
                feasible_wait = False
                break
            wait_to = next_wait
        else:
            feasible_wait = False
        if feasible_wait and wait_to > depart + 1e-8:
            new_depart = wait_to
            new_end = new_depart + direct_d / SPEED_KMH
            if not any(_segment_conflicts(a, b, new_depart, z) for z in zones):
                candidates.append({"path": [a, b], "distance_km": direct_d,
                                   "wait_h": new_depart - depart, "depart_h": new_depart,
                                   "arrive_h": new_end, "action": "wait",
                                   "detour_km": 0.0, "conflicts": [z.zone_id for z, _ in conflicts]})
    for z, _ in conflicts:
        detour = _tangent_detour(a, b, z)
        if detour is None:
            continue
        end = depart + detour["distance_km"] / SPEED_KMH
        if not any(_path_zone_conflict(detour["points"], depart, other) for other in zones):
            candidates.append({"path": detour["points"], "distance_km": detour["distance_km"],
                               "wait_h": 0.0, "depart_h": depart, "arrive_h": end,
                               "action": "detour", "detour_km": detour["detour_km"],
                               "conflicts": [z.zone_id]})
    if not candidates:
        return {"path": [a, b], "distance_km": direct_d, "wait_h": 0.0,
                "depart_h": depart, "arrive_h": direct_end, "action": "infeasible",
                "detour_km": 0.0, "conflicts": [z.zone_id for z, _ in conflicts]}
    return min(candidates, key=lambda x: (x["arrive_h"], x["distance_km"], x["wait_h"]))


def evaluate_dynamic_route(case_data: Dict[str, Any], task_ids: Sequence[str],
                           start_h: float = 0.0) -> Dict[str, Any]:
    zones: Sequence[Zone] = case_data["_zones"]
    current = BASE
    t = start_h
    total_d = total_wait = total_detour = 0.0
    legs: List[Dict[str, Any]] = []
    errors: List[str] = []
    # Base departure/service safety is checked at every node.  A route is invalid if it has to wait inside an active zone.
    if any(z.active and point_in_zone(BASE, z) and zone_active_overlap(t, t + 1e-6, z) for z in zones):
        errors.append("base_active_at_start")
    for task_id in list(task_ids) + ["BASE_RETURN"]:
        target = BASE if task_id == "BASE_RETURN" else task_xy(case_data, task_id)
        plan = plan_dynamic_edge(current, target, t, zones)
        if plan["action"] == "infeasible":
            errors.append(f"edge_infeasible:{task_id}")
        depart_h = plan["depart_h"]
        arrive_h = plan["arrive_h"]
        # Waiting may only occur at a safe endpoint.
        if plan["wait_h"] > 0 and any(z.active and point_in_zone(current, z) and
                                      zone_active_overlap(t, depart_h, z) for z in zones):
            errors.append(f"unsafe_wait:{task_id}")
        service_h = 0.0 if task_id == "BASE_RETURN" else SERVICE_H
        if task_id != "BASE_RETURN":
            for z in zones:
                if z.active and point_in_zone(target, z) and zone_active_overlap(arrive_h, arrive_h + service_h, z):
                    errors.append(f"service_in_zone:{task_id}:{z.zone_id}")
        total_d += plan["distance_km"]
        total_wait += plan["wait_h"]
        total_detour += plan["detour_km"]
        legs.append({"task_id": task_id, "path": [[float(x), float(y)] for x, y in plan["path"]],
                     "distance_km": plan["distance_km"], "wait_h": plan["wait_h"],
                     "action": plan["action"], "depart_h": depart_h, "arrive_h": arrive_h,
                     "arrive_clock": clock_from_rel(arrive_h), "conflicts": plan["conflicts"]})
        t = arrive_h + service_h
        current = target
    service_total = len(task_ids) * SERVICE_H
    work_h = t - start_h
    return {"distance_km": total_d, "flight_h": total_d / SPEED_KMH,
            "service_h": service_total, "wait_h": total_wait, "detour_km": total_detour,
            "work_h": work_h, "finish_clock": clock_from_rel(t), "legs": legs,
            "errors": errors, "valid": not errors}


def validate_dynamic_solution(case_data: Dict[str, Any], routes: Sequence[Sequence[str]],
                              horizon: float = HORIZON_H) -> Dict[str, Any]:
    base = validate_solution(case_data, routes, question="q3", horizon=horizon)
    dynamic_metrics = [evaluate_dynamic_route(case_data, route) for route in routes]
    errors = list(base["errors"])
    for idx, metric in enumerate(dynamic_metrics, 1):
        for error in metric["errors"]:
            errors.append(f"route_{idx}:{error}")
        if metric["work_h"] > horizon + 1e-7:
            errors.append(f"route_{idx}:over_horizon_dynamic")
    times = [m["work_h"] for m in dynamic_metrics]
    return {"valid": not errors, "errors": errors,
            "task_coverage": base["task_coverage"],
            "consecutive_point": base["consecutive_point"],
            "multiplicity_valid": base["multiplicity_valid"],
            "routes_closed": base["routes_closed"],
            "within_9h": all(t <= horizon + 1e-7 for t in times),
            "nofly_valid": all(m["valid"] for m in dynamic_metrics),
            "metrics": {"route_metrics": dynamic_metrics,
                        "Tmax_h": max(times, default=0.0),
                        "Tmin_h": min(times, default=0.0),
                        "delta_h": max(times, default=0.0) - min(times, default=0.0),
                        "total_distance_km": sum(m["distance_km"] for m in dynamic_metrics),
                        "total_wait_h": sum(m["wait_h"] for m in dynamic_metrics),
                        "total_detour_km": sum(m["detour_km"] for m in dynamic_metrics)}}


def serializable_case(case_data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in case_data.items() if not k.startswith("_")}


def dump_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
