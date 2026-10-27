"""Solution decoder and feasibility validator.

Takes a binary bitstring / state vector from a QUBO solver, decodes it into
station siting and EV charging decisions, validates constraints, and
computes the true physical objective and cost breakdown.

Pipeline stage:
    Best Binary Solution -> Decoder -> Feasibility Validation -> Objective + Cost Breakdown
"""

from typing import Any, Dict, List, Tuple, Union
import numpy as np
from evcore.qubo import QUBOModel, normalize_instance


def decode_solution(
    z: Union[str, np.ndarray, List[int]],
    model_or_instance: Union[QUBOModel, Dict[str, Any]],
) -> Dict[str, Any]:
    """Decodes a binary state into domain decisions, validates feasibility,

    and computes objective and cost breakdown.
    """
    if isinstance(model_or_instance, QUBOModel):
        model = model_or_instance
        instance = model.instance
    else:
        model = QUBOModel(model_or_instance)
        instance = model.instance

    # Normalize z to a bit array and bitstring
    if isinstance(z, str):
        z_bits = np.array([int(b) for b in z.strip()], dtype=int)
        bitstring = z.strip()
    else:
        z_bits = np.asarray(z, dtype=int)
        bitstring = "".join(str(int(b)) for b in z_bits)

    if len(z_bits) != model.n_vars:
        raise ValueError(f"Bitstring length {len(z_bits)} does not match model variables {model.n_vars}")

    n_ev = instance["n_ev"]
    n_st = instance["n_st"]
    n_t = instance["n_t"]
    demand = instance["demand"]
    window = instance["window"]
    price = instance["price"]
    grid_cap = instance["grid_cap"]
    open_cost = instance["open_cost"]
    detour = instance["detour"]
    stress_w = instance["stress_w"]

    stations_open = [False] * n_st
    assignments: List[Dict[str, int]] = []

    # Parse active variables
    for idx, bit in enumerate(z_bits):
        if bit != 1:
            continue
        meta = model.var_meta[idx]
        if meta["type"] == "station":
            stations_open[meta["station"]] = True
        elif meta["type"] == "assignment":
            e_idx = meta["ev"]
            s_idx = meta["station"]
            t_idx = meta["slot"]
            assignments.append({
                "ev": e_idx,
                "station": s_idx,
                "slot": t_idx,
                "demand": demand[e_idx] if e_idx < len(demand) else 1,
                "detour_cost": round(float(detour[e_idx][s_idx]), 3) if e_idx < len(detour) and s_idx < len(detour[e_idx]) else 0.0,
                "electricity_price": round(float(price[t_idx]), 3) if t_idx < len(price) else 0.0,
            })

    # Sort assignments deterministically
    assignments.sort(key=lambda a: (a["ev"], a["slot"], a["station"]))

    # -------------------------------------------------------------
    # Feasibility validation
    # -------------------------------------------------------------
    violations: List[str] = []

    # 1. EV charging demand
    ev_slots = [0] * n_ev
    for a in assignments:
        ev_slots[a["ev"]] += 1

    for e in range(n_ev):
        if ev_slots[e] != demand[e]:
            violations.append(
                f"Demand violation: EV {e + 1} received {ev_slots[e]} slots (requires {demand[e]})"
            )

    # 2. Allowed charging time windows
    for a in assignments:
        if a["slot"] not in window[a["ev"]]:
            allowed_slots_str = ", ".join(f"T{w + 1}" for w in sorted(window[a["ev"]]))
            violations.append(
                f"Window violation: EV {a['ev'] + 1} scheduled at slot T{a['slot'] + 1} outside allowed window [{allowed_slots_str}]"
            )

    # 3. Simultaneous charging (at most 1 station per EV per slot)
    ev_slot_usage: Dict[Tuple[int, int], int] = {}
    for a in assignments:
        key = (a["ev"], a["slot"])
        ev_slot_usage[key] = ev_slot_usage.get(key, 0) + 1
        if ev_slot_usage[key] == 2:
            violations.append(
                f"Simultaneous charging violation: EV {a['ev'] + 1} scheduled at multiple stations at slot T{a['slot'] + 1}"
            )

    # 4. Station charger capacity (at most 1 EV per station per slot)
    st_slot_usage: Dict[Tuple[int, int], int] = {}
    for a in assignments:
        key = (a["station"], a["slot"])
        st_slot_usage[key] = st_slot_usage.get(key, 0) + 1
        if st_slot_usage[key] == 2:
            violations.append(
                f"Station capacity violation: Station S{a['station'] + 1} serves multiple EVs at slot T{a['slot'] + 1}"
            )

    # 5. Station coupling (cannot charge at closed station)
    for a in assignments:
        if not stations_open[a["station"]]:
            violations.append(
                f"Coupling violation: EV {a['ev'] + 1} assigned to closed station S{a['station'] + 1} at slot T{a['slot'] + 1}"
            )

    # 6. Grid load and grid capacity
    load = [0] * n_t
    for a in assignments:
        if 0 <= a["slot"] < n_t:
            load[a["slot"]] += 1

    for t in range(n_t):
        if load[t] > grid_cap[t]:
            violations.append(
                f"Grid capacity violation: Slot T{t + 1} load {load[t]} exceeds grid limit {grid_cap[t]}"
            )

    feasible = len(violations) == 0

    # -------------------------------------------------------------
    # Objective & Cost Breakdown
    # -------------------------------------------------------------
    electricity = sum(price[a["slot"]] for a in assignments)
    detour_cost = sum(detour[a["ev"]][a["station"]] for a in assignments)
    infrastructure = sum(
        open_cost[s] for s, opened in enumerate(stations_open) if opened
    )
    grid_stress = stress_w * sum(l ** 2 for l in load)

    total_objective = electricity + detour_cost + infrastructure + grid_stress

    return {
        "bitstring": bitstring,
        "stations_open": stations_open,
        "assignments": assignments,
        "schedule": assignments,
        "load": load,
        "feasible": feasible,
        "violations": violations,
        "objective": round(float(total_objective), 4),
        "cost_breakdown": {
            "electricity": round(float(electricity), 4),
            "detour": round(float(detour_cost), 4),
            "infrastructure": round(float(infrastructure), 4),
            "grid_stress": round(float(grid_stress), 4),
        },
    }
