"""Feasible-first heuristic solvers for the three A-question subproblems.

The optimizer is deliberately independent from the validators in core.py.  Every
candidate written to results is rechecked from the raw task and point data.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import copy
import math
import random

from core import (
    BASE, HORIZON_H, SERVICE_H, Task, Zone, clock_from_rel, distance,
    effective_arrivals, evaluate_dynamic_route, evaluate_static_route,
    load_case, plan_dynamic_edge, point_xy, static_solution_metrics,
    theoretical_lower_bounds, validate_dynamic_solution, validate_solution,
)


def _route_signature(case_data: Dict[str, Any], route: Sequence[str]) -> Tuple[str, ...]:
    return tuple(case_data["_tasks"][t].point_id for t in route)


def _valid_order(case_data: Dict[str, Any], route: Sequence[str]) -> bool:
    if not route:
        return False
    pids = _route_signature(case_data, route)
    return all(a != b for a, b in zip(pids, pids[1:]))


def _order_route(case_data: Dict[str, Any], task_ids: Sequence[str], rng: random.Random) -> List[str]:
    """Nearest-neighbour ordering with a hard adjacent-physical-point rule."""
    remaining = list(task_ids)
    if not remaining:
        return []
    rng.shuffle(remaining)
    current = BASE
    previous_pid: Optional[str] = None
    ordered: List[str] = []
    while remaining:
        candidates = [t for t in remaining if case_data["_tasks"][t].point_id != previous_pid]
        if not candidates:
            # This can only happen when an assignment put all remaining copies of
            # one point at the tail.  Swap with the last compatible item.
            if ordered:
                swap_idx = next((i for i in range(len(ordered) - 1, -1, -1)
                                 if case_data["_tasks"][ordered[i]].point_id != previous_pid), None)
                if swap_idx is not None:
                    ordered[-1], ordered[swap_idx] = ordered[swap_idx], ordered[-1]
                    previous_pid = case_data["_tasks"][ordered[-1]].point_id
                    continue
            # Leave the invalid order for the repair pass; the solution will not
            # be exported unless the independent validator accepts it.
            ordered.extend(remaining)
            break
        candidates.sort(key=lambda t: (distance(current, (case_data["_tasks"][t].x,
                                                            case_data["_tasks"][t].y))
                                       + 0.015 * distance(BASE, (case_data["_tasks"][t].x,
                                                                  case_data["_tasks"][t].y))
                                       + rng.random() * 0.02))
        chosen = candidates[0]
        ordered.append(chosen)
        remaining.remove(chosen)
        current = (case_data["_tasks"][chosen].x, case_data["_tasks"][chosen].y)
        previous_pid = case_data["_tasks"][chosen].point_id
    return _repair_consecutive(case_data, ordered)


def _repair_consecutive(case_data: Dict[str, Any], route: List[str]) -> List[str]:
    """Repair adjacent duplicates with deterministic swaps."""
    route = list(route)
    for _ in range(max(1, len(route) * 2)):
        bad = next((i for i, (a, b) in enumerate(zip(route, route[1:]))
                    if case_data["_tasks"][a].point_id == case_data["_tasks"][b].point_id), None)
        if bad is None:
            return route
        swapped = False
        for j in range(bad + 2, len(route)):
            candidate = route.copy()
            candidate[bad + 1], candidate[j] = candidate[j], candidate[bad + 1]
            if _valid_order(case_data, candidate):
                route = candidate
                swapped = True
                break
        if not swapped:
            for j in range(0, bad):
                candidate = route.copy()
                candidate[bad], candidate[j] = candidate[j], candidate[bad]
                if _valid_order(case_data, candidate):
                    route = candidate
                    swapped = True
                    break
        if not swapped:
            return route
    return route


def assign_tasks(case_data: Dict[str, Any], fleet: int, rng: random.Random) -> List[List[str]]:
    """Cluster physical points first, then spread repeated visits across routes."""
    routes: List[List[str]] = [[] for _ in range(fleet)]
    point_counts = [dict() for _ in range(fleet)]
    route_load = [0.0] * fleet
    groups: Dict[str, List[str]] = {}
    for t in case_data["tasks"]:
        groups.setdefault(t["point_id"], []).append(t["task_id"])
    point_items = [(pid, case_data["_points"][pid].x, case_data["_points"][pid].y, len(tids))
                   for pid, tids in groups.items()]
    # Farthest-point seeded weighted k-means gives compact routes on all four
    # spatial patterns, while random tie-breaking supplies independent restarts.
    seeds_xy: List[Tuple[float, float]] = []
    first = max(point_items, key=lambda q: distance(BASE, (q[1], q[2])))
    seeds_xy.append((first[1], first[2]))
    while len(seeds_xy) < min(fleet, len(point_items)):
        nxt = max(point_items, key=lambda q: min(distance((q[1], q[2]), c) for c in seeds_xy) + rng.random() * 0.01)
        seeds_xy.append((nxt[1], nxt[2]))
    while len(seeds_xy) < fleet:
        q = rng.choice(point_items)
        seeds_xy.append((q[1], q[2]))
    assignment: Dict[str, int] = {}
    for _ in range(8):
        buckets: List[List[Tuple[str, float, float, int]]] = [[] for _ in range(fleet)]
        for q in point_items:
            k = min(range(fleet), key=lambda i: distance((q[1], q[2]), seeds_xy[i]) + rng.random() * 0.003)
            assignment[q[0]] = k
            buckets[k].append(q)
        for k, bucket in enumerate(buckets):
            if bucket:
                w = sum(q[3] for q in bucket)
                seeds_xy[k] = (sum(q[1] * q[3] for q in bucket) / w,
                               sum(q[2] * q[3] for q in bucket) / w)
    # Empty clusters receive the farthest point from the largest cluster.
    for k in range(fleet):
        if not any(v == k for v in assignment.values()):
            source = max(point_items, key=lambda q: distance((q[1], q[2]), seeds_xy[assignment[q[0]]]))
            assignment[source[0]] = k
    # First visit each physical point exactly once on a compact route.
    extras: List[str] = []
    for pid, tids in groups.items():
        tids = list(tids)
        rng.shuffle(tids)
        routes[assignment[pid]].append(tids[0])
        extras.extend(tids[1:])
    for k in range(fleet):
        routes[k] = _order_route(case_data, routes[k], rng)
    # Extra required visits are real re-arrivals.  Insert each one only between
    # different physical points and minimize the resulting fleet makespan.
    extras.sort(key=lambda tid: (-distance(BASE, (case_data["_tasks"][tid].x,
                                                   case_data["_tasks"][tid].y)), rng.random()))
    for tid in extras:
        pid = case_data["_tasks"][tid].point_id
        best = None
        current_times = [evaluate_static_route(case_data, r)["work_h"] for r in routes]
        for k, route in enumerate(routes):
            for pos in range(len(route) + 1):
                left_pid = case_data["_tasks"][route[pos - 1]].point_id if pos > 0 else None
                right_pid = case_data["_tasks"][route[pos]].point_id if pos < len(route) else None
                if left_pid == pid or right_pid == pid:
                    continue
                trial = route[:pos] + [tid] + route[pos:]
                metric = evaluate_static_route(case_data, trial)
                fleet_max = max(metric["work_h"], *(current_times[j] for j in range(fleet) if j != k))
                delta_distance = metric["distance_km"] - evaluate_static_route(case_data, route)["distance_km"]
                score = (fleet_max, metric["work_h"], delta_distance, rng.random())
                if best is None or score < best[0]:
                    best = (score, k, pos)
        if best is None:
            # A point can always be inserted into another nonempty route in the
            # official instances; retain a detectable invalid candidate otherwise.
            routes[0].append(tid)
        else:
            _, k, pos = best
            routes[k].insert(pos, tid)
    return routes


def _static_objective(case_data: Dict[str, Any], routes: Sequence[Sequence[str]]) -> Tuple[float, float]:
    metrics = static_solution_metrics(case_data, routes)
    return metrics["Tmax_h"], metrics["total_distance_km"]


def _is_static_feasible(case_data: Dict[str, Any], routes: Sequence[Sequence[str]]) -> bool:
    if any(not _valid_order(case_data, r) for r in routes):
        return False
    check = validate_solution(case_data, routes, fleet_expected=len(routes))
    return check["task_coverage"] and check["consecutive_point"] and check["multiplicity_valid"]


def improve_static(case_data: Dict[str, Any], routes: List[List[str]], rng: random.Random,
                   iterations: int = 300, max_h: float = HORIZON_H,
                   objective: str = "q1") -> List[List[str]]:
    """Relocate/swap local search; feasibility is always checked before acceptance."""
    routes = [list(r) for r in routes]
    best = copy.deepcopy(routes)
    best_metrics = static_solution_metrics(case_data, best)
    def key_of(metrics: Dict[str, Any]) -> Tuple[float, ...]:
        overload = sum(max(0.0, m["work_h"] - max_h) for m in metrics["route_metrics"])
        if objective == "q1":
            return (overload, metrics["Tmax_h"], metrics["total_distance_km"])
        return (overload, metrics["Tmax_h"], metrics["delta_h"], metrics["total_distance_km"])

    best_key = key_of(best_metrics)
    for _ in range(iterations):
        candidate = copy.deepcopy(best)
        if rng.random() < 0.75:
            src = rng.randrange(len(candidate))
            if len(candidate[src]) <= 1:
                continue
            pos = rng.randrange(len(candidate[src]))
            task = candidate[src].pop(pos)
            dst = rng.randrange(len(candidate))
            ins = rng.randrange(len(candidate[dst]) + 1)
            candidate[dst].insert(ins, task)
        else:
            a, b = rng.sample(range(len(candidate)), 2)
            if not candidate[a] or not candidate[b]:
                continue
            ia, ib = rng.randrange(len(candidate[a])), rng.randrange(len(candidate[b]))
            candidate[a][ia], candidate[b][ib] = candidate[b][ib], candidate[a][ia]
        candidate = [_repair_consecutive(case_data, r) for r in candidate]
        if not _is_static_feasible(case_data, candidate):
            continue
        metrics = static_solution_metrics(case_data, candidate)
        key = key_of(metrics)
        if key < best_key:
            best, best_key = candidate, key
            best_metrics = metrics
    return best


def solve_problem1(case_data: Dict[str, Any], seeds: Sequence[int] = range(12),
                   max_fleet_extra: int = 5) -> Dict[str, Any]:
    bounds = theoretical_lower_bounds(case_data)
    start = bounds["max"]
    attempted: List[Dict[str, Any]] = []
    selected: Optional[Tuple[int, List[List[str]], Dict[str, Any], int]] = None
    for fleet in range(start, start + max_fleet_extra + 1):
        best_routes = None
        best_metrics = None
        best_seed = None
        seed_runs: List[Dict[str, Any]] = []
        for seed in seeds:
            rng = random.Random(seed + fleet * 10007)
            routes = assign_tasks(case_data, fleet, rng)
            if not _is_static_feasible(case_data, routes):
                continue
            routes = improve_static(case_data, routes, rng, iterations=240,
                                    max_h=HORIZON_H, objective="q1")
            check = validate_solution(case_data, routes, fleet_expected=fleet)
            if not check["task_coverage"] or not check["consecutive_point"] or not check["multiplicity_valid"]:
                seed_runs.append({"seed": int(seed), "feasible": False, "reason": "coverage_or_arrival"})
                continue
            metrics = static_solution_metrics(case_data, routes)
            within = not any(m["work_h"] > HORIZON_H + 1e-8 for m in metrics["route_metrics"])
            seed_runs.append({"seed": int(seed), "feasible": within,
                              "Tmax_h": metrics["Tmax_h"], "delta_h": metrics["delta_h"],
                              "total_distance_km": metrics["total_distance_km"]})
            if not within:
                continue
            if best_metrics is None or (metrics["Tmax_h"], metrics["total_distance_km"]) < (best_metrics["Tmax_h"], best_metrics["total_distance_km"]):
                best_routes, best_metrics, best_seed = routes, metrics, seed
        attempted.append({"fleet": fleet, "feasible": best_routes is not None,
                          "best_Tmax_h": best_metrics["Tmax_h"] if best_metrics else None,
                          "seed_runs": seed_runs})
        if best_routes is not None:
            selected = (fleet, best_routes, best_metrics, int(best_seed))
            break
    if selected is None:
        raise RuntimeError(f"No static feasible solution found for {case_data['case_id']}: {attempted}")
    fleet, routes, metrics, seed = selected
    validation = validate_solution(case_data, routes, fleet_expected=fleet)
    return {"question": "q1", "case_id": case_data["case_id"], "status": "best_verified",
            "seed": seed, "fleet_count": fleet, "theoretical_lb_service": bounds["service"],
            "theoretical_lb_work": bounds["work"], "minimum_certified": False,
            "certificate_status": "heuristic_first_feasible; lower counts not exactly certified",
            "fleet_search": attempted, "routes": routes, "metrics": metrics,
            "validation": validation}


def solve_problem2(case_data: Dict[str, Any], q1: Dict[str, Any],
                   seeds: Sequence[int] = range(12)) -> Dict[str, Any]:
    fleet = int(q1["fleet_count"])
    baseline = q1["routes"]
    best_routes = copy.deepcopy(baseline)
    best_metrics = static_solution_metrics(case_data, best_routes)
    best_key = (best_metrics["Tmax_h"], best_metrics["delta_h"], best_metrics["total_distance_km"])
    for seed in seeds:
        rng = random.Random(seed + 530001)
        candidate = assign_tasks(case_data, fleet, rng)
        if not _is_static_feasible(case_data, candidate):
            continue
        candidate = improve_static(case_data, candidate, rng, iterations=360,
                                   max_h=HORIZON_H, objective="q2")
        check = validate_solution(case_data, candidate, fleet_expected=fleet)
        if not check["valid"]:
            continue
        metrics = static_solution_metrics(case_data, candidate)
        # Problem 2 inherits problem 1's best makespan; only numerical tolerance is allowed.
        if metrics["Tmax_h"] > best_metrics["Tmax_h"] + 1e-7:
            continue
        key = (metrics["Tmax_h"], metrics["delta_h"], metrics["total_distance_km"])
        if key < best_key:
            best_routes, best_metrics, best_key = candidate, metrics, key
    validation = validate_solution(case_data, best_routes, fleet_expected=fleet)
    return {"question": "q2", "case_id": case_data["case_id"], "status": "best_verified",
            "seed": 530001, "fleet_count": fleet, "inherited_Tmax_h": q1["metrics"]["Tmax_h"],
            "routes": best_routes, "metrics": best_metrics, "validation": validation}


def _dynamic_order_for_tasks(case_data: Dict[str, Any], task_ids: Sequence[str], rng: random.Random,
                             start_h: float = 0.0) -> List[str]:
    """Randomized greedy search over time-dependent feasible next tasks."""
    def one_attempt(local_rng: random.Random) -> List[str]:
        remaining = list(task_ids)
        preferred_rank = {tid: i for i, tid in enumerate(remaining)}
        current = BASE
        t = start_h
        previous_pid: Optional[str] = None
        ordered: List[str] = []
        while remaining:
            choices: List[Tuple[float, float, str, Dict[str, Any]]] = []
            for tid in remaining:
                task = case_data["_tasks"][tid]
                if task.point_id == previous_pid:
                    continue
                target = (task.x, task.y)
                edge = plan_dynamic_edge(current, target, t, case_data["_zones"])
                if edge["action"] == "infeasible":
                    continue
                arrival = edge["arrive_h"]
                if any(z.active and distance(target, (z.x, z.y)) <= z.radius + 1e-8 and
                       max(arrival, z.start_h) < min(arrival + SERVICE_H, z.end_h) - 1e-9
                       for z in case_data["_zones"]):
                    continue
                # Visit points with an upcoming activation window early.  This
                # prevents a route from reaching an otherwise safe point only
                # after its zone has become active and then paying a full-window
                # wait at that point.
                future_deadlines = [z.start_h for z in case_data["_zones"]
                                    if z.active and distance(target, (z.x, z.y)) <= z.radius + 1e-8
                                    and arrival + SERVICE_H <= z.start_h + 1e-9]
                urgency_bonus = -4.0 if future_deadlines else 0.0
                # Waiting is allowed, but a short safe edge is preferred; a tiny
                # random perturbation explores alternative zone orderings.
                choices.append((arrival + urgency_bonus + 0.001 * distance(BASE, target)
                                + 0.0005 * preferred_rank[tid] + local_rng.random() * 0.003,
                                edge["distance_km"], tid, edge))
            if not choices:
                return []
            choices.sort(key=lambda x: (x[0], x[1]))
            pick = min(len(choices) - 1, int(local_rng.random() ** 2 * min(8, len(choices))))
            _, _, chosen, edge = choices[pick]
            ordered.append(chosen)
            remaining.remove(chosen)
            current = (case_data["_tasks"][chosen].x, case_data["_tasks"][chosen].y)
            t = edge["arrive_h"] + SERVICE_H
            previous_pid = case_data["_tasks"][chosen].point_id
        return ordered

    completed: List[Tuple[Tuple[float, float, float, float], List[str]]] = []
    for attempt in range(80):
        result = one_attempt(random.Random(rng.randrange(1_000_000_000)))
        if result:
            metric = evaluate_dynamic_route(case_data, result)
            if metric["valid"]:
                overload = max(0.0, metric["work_h"] - HORIZON_H)
                completed.append(((overload, metric["work_h"], metric["wait_h"], metric["distance_km"]), result))
    if completed:
        return min(completed, key=lambda x: x[0])[1]
    return []


def improve_dynamic_routes(case_data: Dict[str, Any], routes: Sequence[Sequence[str]],
                           rng: random.Random, passes: int = 2) -> List[List[str]]:
    """Repair time-window waits by relocating only affected tasks.

    Starting from a good spatial route is important: a full random reorder can
    satisfy time windows while destroying the distance objective.  This local
    search therefore evaluates all insertion positions for tasks in a no-fly
    disk or on a currently waiting edge, then keeps lexicographic improvements.
    """
    current = [list(r) for r in routes]

    def route_key(metric: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
        return (float(len(metric["errors"])), max(0.0, metric["work_h"] - HORIZON_H),
                metric["work_h"], metric["wait_h"], metric["distance_km"])

    for _ in range(passes):
        changed = False
        for k in range(len(current)):
            route = current[k]
            base_metric = evaluate_dynamic_route(case_data, route)
            candidate_ids = set()
            for tid in route:
                task = case_data["_tasks"][tid]
                p = (task.x, task.y)
                if any(z.active and distance(p, (z.x, z.y)) <= z.radius + 1e-8 for z in case_data["_zones"]):
                    candidate_ids.add(tid)
            for leg in base_metric["legs"]:
                if leg["action"] == "wait" and leg["task_id"] != "BASE_RETURN":
                    candidate_ids.add(leg["task_id"])
            if not candidate_ids:
                continue
            best_route = route
            best_metric = base_metric
            best_key = route_key(base_metric)
            for tid in list(candidate_ids):
                old_pos = route.index(tid)
                reduced = route[:old_pos] + route[old_pos + 1:]
                for pos in range(len(reduced) + 1):
                    if pos > 0 and case_data["_tasks"][reduced[pos - 1]].point_id == case_data["_tasks"][tid].point_id:
                        continue
                    if pos < len(reduced) and case_data["_tasks"][reduced[pos]].point_id == case_data["_tasks"][tid].point_id:
                        continue
                    trial = reduced[:pos] + [tid] + reduced[pos:]
                    if not _valid_order(case_data, trial):
                        continue
                    metric = evaluate_dynamic_route(case_data, trial)
                    key = route_key(metric)
                    if key < best_key:
                        best_route, best_metric, best_key = trial, metric, key
            if best_route != route:
                current[k] = best_route
                changed = True
        if not changed:
            break
    return current


def balance_dynamic_routes(case_data: Dict[str, Any], routes: Sequence[Sequence[str]],
                           rng: random.Random, iterations: int = 500) -> List[List[str]]:
    """Move tasks from dynamically overloaded routes to shorter routes."""
    current = [list(r) for r in routes]

    def metrics_of(rs: Sequence[Sequence[str]]) -> List[Dict[str, Any]]:
        return [evaluate_dynamic_route(case_data, r) for r in rs]

    def fleet_key(ms: Sequence[Dict[str, Any]]) -> Tuple[float, float, float, float, float]:
        times = [m["work_h"] for m in ms]
        return (float(sum(len(m["errors"]) for m in ms)),
                sum(max(0.0, t - HORIZON_H) for t in times),
                max(times), max(times) - min(times), sum(m["distance_km"] for m in ms))

    metrics = metrics_of(current)
    best_key = fleet_key(metrics)
    for _ in range(iterations):
        times = [m["work_h"] for m in metrics]
        longest = sorted(range(len(current)), key=lambda k: times[k], reverse=True)
        src = longest[0] if rng.random() < 0.8 else rng.choice(longest[:min(3, len(longest))])
        if len(current[src]) <= 1:
            continue
        shortest = sorted(range(len(current)), key=lambda k: times[k])
        dst_choices = [k for k in shortest[:min(3, len(shortest))] if k != src]
        if not dst_choices:
            continue
        dst = rng.choice(dst_choices)
        pos_src = rng.randrange(len(current[src]))
        tid = current[src][pos_src]
        reduced = current[src][:pos_src] + current[src][pos_src + 1:]
        if not _valid_order(case_data, reduced):
            continue
        insertion_options = []
        for pos in range(len(current[dst]) + 1):
            trial_dst = current[dst][:pos] + [tid] + current[dst][pos:]
            if not _valid_order(case_data, trial_dst):
                continue
            m_dst = evaluate_dynamic_route(case_data, trial_dst)
            insertion_options.append((len(m_dst["errors"]), m_dst["work_h"], m_dst["distance_km"], pos, m_dst))
        if not insertion_options:
            continue
        _, _, _, pos, m_dst = min(insertion_options)
        m_src = evaluate_dynamic_route(case_data, reduced)
        candidate_metrics = list(metrics)
        candidate_metrics[src] = m_src
        candidate_metrics[dst] = m_dst
        key = fleet_key(candidate_metrics)
        if key < best_key:
            current[src] = reduced
            current[dst] = current[dst][:pos] + [tid] + current[dst][pos:]
            metrics = candidate_metrics
            best_key = key
    return current


def solve_problem3(case_data: Dict[str, Any], q2: Dict[str, Any], q1: Dict[str, Any],
                   seeds: Sequence[int] = range(10), max_extra: int = 4) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base_fleet = int(q2["fleet_count"])
    fixed_routes = []
    inherited_check = validate_dynamic_solution(case_data, q2["routes"])
    if inherited_check["valid"]:
        fixed_routes.append((inherited_check["metrics"]["Tmax_h"], inherited_check["metrics"]["delta_h"],
                             -1, copy.deepcopy(q2["routes"]), inherited_check))
    improved_inherited = improve_dynamic_routes(case_data, q2["routes"], random.Random(710003), passes=3)
    improved_inherited = balance_dynamic_routes(case_data, improved_inherited, random.Random(710004), iterations=300)
    improved_check = validate_dynamic_solution(case_data, improved_inherited)
    if improved_check["valid"]:
        fixed_routes.append((improved_check["metrics"]["Tmax_h"], improved_check["metrics"]["delta_h"],
                             -2, improved_inherited, improved_check))
    for seed in seeds:
        rng = random.Random(seed + 710003)
        trial = []
        ok = True
        for route in q2["routes"]:
            ordered = _dynamic_order_for_tasks(case_data, route, rng)
            if not ordered:
                ok = False
                break
            trial.append(ordered)
        if not ok:
            continue
        trial = improve_dynamic_routes(case_data, trial, rng, passes=2)
        trial = balance_dynamic_routes(case_data, trial, rng, iterations=250)
        check = validate_dynamic_solution(case_data, trial)
        if check["valid"]:
            fixed_routes.append((check["metrics"]["Tmax_h"], check["metrics"]["delta_h"], seed, trial, check))
    fixed_routes.sort(key=lambda x: (x[0], x[1]))
    fixed = fixed_routes[0] if fixed_routes else None
    fixed_result = _dynamic_result(case_data, "q3_fixed_fleet", base_fleet, q2, fixed, q1)
    if fixed is not None:
        return _dynamic_result(case_data, "q3", base_fleet, q2, fixed, q1)[0], fixed_result
    # Dynamic constraints can require more UAVs.  Rebuild assignments one UAV at a time.
    selected = None
    attempts = []
    for fleet in range(base_fleet + 1, base_fleet + max_extra + 1):
        best = None
        for seed in seeds:
            rng = random.Random(seed + fleet * 17011)
            static_routes = assign_tasks(case_data, fleet, rng)
            if not _is_static_feasible(case_data, static_routes):
                continue
            dynamic_routes = []
            ok = True
            for route in static_routes:
                ordered = _dynamic_order_for_tasks(case_data, route, rng)
                if not ordered:
                    ok = False
                    break
                dynamic_routes.append(ordered)
            if not ok:
                continue
            dynamic_routes = improve_dynamic_routes(case_data, dynamic_routes, rng, passes=1)
            dynamic_routes = balance_dynamic_routes(case_data, dynamic_routes, rng, iterations=150)
            check = validate_dynamic_solution(case_data, dynamic_routes)
            if not check["valid"]:
                continue
            key = (check["metrics"]["Tmax_h"], check["metrics"]["delta_h"], check["metrics"]["total_distance_km"])
            if best is None or key < best[0]:
                best = (key, seed, dynamic_routes, check)
        attempts.append({"fleet": fleet, "feasible": best is not None,
                         "Tmax_h": best[3]["metrics"]["Tmax_h"] if best else None})
        if best is not None:
            selected = (fleet, best)
            break
    if selected is None:
        # This is a hard failure rather than an invented result.
        raise RuntimeError(f"No dynamic feasible solution for {case_data['case_id']}; attempts={attempts}")
    fleet, best = selected
    dynamic_q = _dynamic_result(case_data, "q3", fleet, q2, (best[3]["metrics"]["Tmax_h"], best[3]["metrics"]["delta_h"], best[1], best[2], best[3]), q1)[0]
    dynamic_q["fleet_search"] = attempts
    return dynamic_q, fixed_result


def _dynamic_result(case_data: Dict[str, Any], question: str, fleet: int, inherited: Dict[str, Any],
                    selected: Optional[Tuple[float, float, int, List[List[str]], Dict[str, Any]]],
                    q1: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if selected is None:
        result = {"question": question, "case_id": case_data["case_id"],
                  "status": "infeasible_under_9h", "fleet_count": fleet,
                  "routes": inherited["routes"], "metrics": validate_dynamic_solution(case_data, inherited["routes"])["metrics"],
                  "validation": validate_dynamic_solution(case_data, inherited["routes"]),
                  "inherited_static_Tmax_h": inherited["metrics"]["Tmax_h"]}
        return (result, result) if question == "q3" else result
    _, _, seed, routes, validation = selected
    result = {"question": question, "case_id": case_data["case_id"],
              "status": "best_verified" if validation["valid"] else "infeasible_under_9h",
              "seed": int(seed), "fleet_count": fleet, "minimum_certified": False,
              "routes": routes, "metrics": validation["metrics"], "validation": validation,
              "inherited_static_Tmax_h": inherited["metrics"]["Tmax_h"],
              "dynamic_rule": "segment/time/service/base checks; zero-duration windows inactive"}
    return (result, result) if question == "q3" else result


def solve_all_cases(cases: Sequence[str] = ("Case1", "Case2", "Case3", "Case4")) -> Dict[str, Dict[str, Any]]:
    output: Dict[str, Dict[str, Any]] = {}
    for case_id in cases:
        case_data = load_case(case_id)
        q1 = solve_problem1(case_data)
        q2 = solve_problem2(case_data, q1)
        q3, fixed = solve_problem3(case_data, q2, q1)
        output[case_id] = {"case_data": case_data, "q1": q1, "q2": q2, "q3": q3,
                           "q3_fixed_fleet": fixed}
    return output
