"""Evaluator for service marketplace order allocation problems.

Compares agent-generated assignments against ground truth
across multiple dimensions: served orders, travel, regressions, feasibility.
"""

import json
import math
import os
import sys
import tempfile
import traceback


def haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def evaluate_service_marketplace(generated_code: str, problem_dir: str) -> dict:
    """Evaluate service marketplace allocation code against ground truth.

    Args:
        generated_code: Python source code with allocate_orders() function.
        problem_dir: Path to problem directory containing orders.json,
                     specialists.json, and ground_truth.json.

    Returns:
        Dict with holistic evaluation results.
    """
    # Load data
    with open(os.path.join(problem_dir, "orders.json"), "r") as f:
        orders = json.load(f)
    with open(os.path.join(problem_dir, "specialists.json"), "r") as f:
        specialists = json.load(f)
    with open(os.path.join(problem_dir, "ground_truth.json"), "r") as f:
        gt = json.load(f)

    orders_json = json.dumps(orders)
    specialists_json = json.dumps(specialists)

    # Build lookup dicts
    order_map = {o["order_id"]: o for o in orders}
    spec_map = {s["spec_id"]: s for s in specialists}
    baseline_served = {o["order_id"] for o in orders if o.get("baseline_specialist")}

    # Execute generated code
    tmp_dir = tempfile.mkdtemp()
    module_path = os.path.join(tmp_dir, "generated_code.py")
    with open(module_path, "w") as f:
        f.write(generated_code)

    sys.path.insert(0, tmp_dir)
    try:
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]

        try:
            import generated_code
        except Exception as e:
            return _error_result("COMPILE_ERROR", f"Import failed: {e}\n{traceback.format_exc()}", gt)

        func = getattr(generated_code, "allocate_orders", None)
        if func is None:
            return _error_result("COMPILE_ERROR", "Function 'allocate_orders' not found", gt)

        try:
            raw_output = func(orders_json, specialists_json)
        except Exception as e:
            return _error_result("RUNTIME_ERROR", f"Execution failed: {e}\n{traceback.format_exc()}", gt)

        # Parse output
        try:
            if isinstance(raw_output, str):
                output = json.loads(raw_output)
            elif isinstance(raw_output, dict):
                output = raw_output
            else:
                return _error_result("RUNTIME_ERROR", f"Unexpected return type: {type(raw_output)}", gt)
        except json.JSONDecodeError as e:
            return _error_result("RUNTIME_ERROR", f"Invalid JSON output: {e}", gt)

        assignments = output.get("assignments", [])
        method = output.get("method", "unknown")
        reported_metrics = output.get("metrics", {})

    finally:
        sys.path.remove(tmp_dir)
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]

    # --- Validate and compute metrics ---
    assignment_map = {}  # order_id -> specialist_id
    for a in assignments:
        oid = a.get("order_id")
        sid = a.get("specialist_id")
        if oid and sid:
            assignment_map[oid] = sid

    # Per-specialist schedule
    spec_schedule = {}  # spec_id -> list of order entries
    infeasible = []
    radius_violations = []

    for oid, sid in assignment_map.items():
        order = order_map.get(oid)
        spec = spec_map.get(sid)

        if not order:
            infeasible.append({"order_id": oid, "reason": "unknown order_id"})
            continue
        if not spec:
            infeasible.append({"order_id": oid, "reason": f"unknown specialist {sid}"})
            continue

        # Check certification
        if order["service"] not in spec["certs"]:
            infeasible.append({"order_id": oid, "reason": f"cert mismatch: {order['service']} not in {spec['certs'][:3]}..."})
            continue

        # Check radius constraint
        dist_to_order = haversine_km(spec["home_lat"], spec["home_lng"], order["lat"], order["lng"])
        radius_cap = spec.get("radius_cap_km") or 999
        if dist_to_order > radius_cap * 1.1:  # 10% tolerance
            radius_violations.append({
                "order_id": oid, "spec_id": sid,
                "dist_km": round(dist_to_order, 1), "cap_km": round(radius_cap, 1),
            })

        if sid not in spec_schedule:
            spec_schedule[sid] = []
        spec_schedule[sid].append({
            "order_id": oid,
            "start_min": order["start_min"],
            "end_min": order["end_min"],
            "duration": order["duration"],
            "lat": order["lat"],
            "lng": order["lng"],
            "travel_speed": order["travel_speed"],
        })

    # Check time feasibility and capacity per specialist
    capacity_violations = []
    time_violations = []
    total_km = 0.0

    for sid, schedule in spec_schedule.items():
        spec = spec_map[sid]
        schedule.sort(key=lambda x: x["start_min"])

        max_orders = spec.get("max_orders") or 3
        if len(schedule) > max_orders:
            capacity_violations.append({"spec_id": sid, "orders": len(schedule), "max": max_orders})

        # Check sequential feasibility
        prev_end = None
        prev_lat, prev_lng = spec["home_lat"], spec["home_lng"]

        for entry in schedule:
            dist = haversine_km(prev_lat, prev_lng, entry["lat"], entry["lng"])
            total_km += dist
            travel_min = (dist / max(entry["travel_speed"], 1)) * 60
            handover = 15 if prev_end is not None else 0

            earliest_arrival = (prev_end + handover + travel_min) if prev_end else travel_min
            if earliest_arrival > entry["start_min"] + 30:  # 30 min grace
                time_violations.append({
                    "spec_id": sid, "order_id": entry["order_id"],
                    "earliest": round(earliest_arrival), "needed_by": entry["start_min"],
                })

            prev_end = entry["start_min"] + entry["duration"]
            prev_lat, prev_lng = entry["lat"], entry["lng"]

    # Compute metrics
    feasible_served = set(assignment_map.keys()) - {i["order_id"] for i in infeasible}
    served = len(feasible_served)
    unserved = len(orders) - served

    recovered = len(feasible_served - baseline_served)
    lost = len(baseline_served - feasible_served)
    specs_used = len(spec_schedule)

    # Ground truth comparison
    gt_opt = gt["optimizer"]
    gt_bl = gt["baseline"]

    # Composite scoring (0-100)
    # Dimension 1: Served orders (40 pts) -- relative to optimizer
    served_ratio = served / max(1, gt_opt["served"])
    served_score = min(40, 40 * served_ratio)

    # Dimension 2: Feasibility (25 pts) -- penalize constraint violations
    total_violations = len(infeasible) + len(capacity_violations) + len(time_violations) + len(radius_violations)
    feasibility_score = max(0, 25 - total_violations * 2)

    # Dimension 3: Travel efficiency (20 pts) -- ratio to optimizer km
    if total_km > 0 and gt_opt["total_km"] > 0:
        km_ratio = gt_opt["total_km"] / total_km  # <1 means agent is worse
        travel_score = min(20, 20 * km_ratio)
    else:
        travel_score = 10  # default

    # Dimension 4: Regressions (15 pts) -- penalize lost orders
    regression_penalty = min(15, lost * 2.5)
    regression_score = max(0, 15 - regression_penalty)

    composite = round(served_score + feasibility_score + travel_score + regression_score, 1)

    eval_result = {
        "result": "EVALUATED",
        "method": method,
        "agent_metrics": {
            "served": served,
            "unserved": unserved,
            "recovered_from_dr": recovered,
            "lost_regressions": lost,
            "total_km": round(total_km, 1),
            "specialists_used": specs_used,
        },
        "ground_truth_metrics": {
            "baseline_served": gt_bl["served"],
            "baseline_dr": gt_bl["unserved_dr"],
            "optimizer_served": gt_opt["served"],
            "optimizer_recovered": gt_opt["recovered"],
            "optimizer_lost": gt_opt["lost"],
            "optimizer_km": gt_opt["total_km"],
            "optimizer_specs": gt_opt["specialists_used"],
        },
        "feasibility": {
            "infeasible_assignments": len(infeasible),
            "capacity_violations": len(capacity_violations),
            "time_violations": len(time_violations),
            "radius_violations": len(radius_violations),
            "infeasible_details": infeasible[:10],
            "capacity_details": capacity_violations[:5],
            "time_details": time_violations[:5],
            "radius_details": radius_violations[:10],
        },
        "scoring": {
            "composite": composite,
            "served_score": round(served_score, 1),
            "feasibility_score": round(feasibility_score, 1),
            "travel_score": round(travel_score, 1),
            "regression_score": round(regression_score, 1),
        },
        "comparison": {
            "vs_baseline_served": served - gt_bl["served"],
            "vs_optimizer_served": served - gt_opt["served"],
            "vs_baseline_km": round(total_km - gt_bl["total_km"], 1),
            "vs_optimizer_km": round(total_km - gt_opt["total_km"], 1),
        },
        "reported_metrics": reported_metrics,
        "error": None,
    }

    # Grade based on composite score
    if composite >= 85:
        eval_result["grade"] = "EXCELLENT"
    elif composite >= 65:
        eval_result["grade"] = "GOOD"
    elif composite >= 45:
        eval_result["grade"] = "ACCEPTABLE"
    else:
        eval_result["grade"] = "POOR"

    return eval_result


def _error_result(error_type, message, gt):
    """Return error result with ground truth for reference."""
    return {
        "result": error_type,
        "error": message,
        "agent_metrics": None,
        "ground_truth_metrics": {
            "baseline_served": gt["baseline"]["served"],
            "optimizer_served": gt["optimizer"]["served"],
        },
        "grade": "ERROR",
    }
