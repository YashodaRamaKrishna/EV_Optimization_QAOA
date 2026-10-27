from copy import deepcopy
from datetime import datetime, timezone

BASELINE = {
    "id": "baseline-3x2x4", "name": "Baseline — 3 EV × 2 Stations × 4 Slots",
    "n_ev": 3, "n_st": 2, "n_t": 4, "demand": [1, 2, 1],
    "window": [[0, 1, 2], [1, 2, 3], [0, 1, 2, 3]],
    "price": [1.0, 3.0, 3.2, 1.0], "grid_cap": [2, 1, 1, 2],
    "open_cost": [1.0, 1.5], "detour": [[0.0, 0.3], [0.2, 0.0], [0.1, 0.4]],
    "stress_w": 0.25, "n_qubits": 22, "seed": 42,
}

PRESETS = [
    BASELINE,
    {
        "id": "small-2x2x2", "name": "Small — 2 EV × 2 Stations × 2 Slots",
        "n_ev": 2, "n_st": 2, "n_t": 2, "demand": [1, 1],
        "window": [[0, 1], [0, 1]],
        "price": [1.0, 2.0], "grid_cap": [2, 2],
        "open_cost": [1.0, 1.5], "detour": [[0.0, 0.3], [0.2, 0.0]],
        "stress_w": 0.25, "n_qubits": 10, "seed": 42,
    },
    {
        "id": "medium-4x2x4", "name": "Medium — 4 EV × 2 Stations × 4 Slots",
        "n_ev": 4, "n_st": 2, "n_t": 4, "demand": [1, 2, 1, 1],
        "window": [[0, 1, 2], [1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]],
        "price": [1.0, 3.0, 3.2, 1.0], "grid_cap": [2, 2, 2, 2],
        "open_cost": [1.0, 1.5], "detour": [[0.0, 0.3], [0.2, 0.0], [0.1, 0.4], [0.3, 0.1]],
        "stress_w": 0.25, "n_qubits": 30, "seed": 42,
    },
    {
        "id": "larger-4x3x4", "name": "Larger — 4 EV × 3 Stations × 4 Slots",
        "n_ev": 4, "n_st": 3, "n_t": 4, "demand": [1, 2, 1, 1],
        "window": [[0, 1, 2], [1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]],
        "price": [1.0, 3.0, 3.2, 1.0], "grid_cap": [3, 2, 2, 3],
        "open_cost": [1.0, 1.5, 1.2], "detour": [[0.0, 0.3, 0.5], [0.2, 0.0, 0.4], [0.1, 0.4, 0.1], [0.3, 0.1, 0.2]],
        "stress_w": 0.25, "n_qubits": 45, "seed": 42,
    },
]

SOLUTION = {
    "bitstring": "1010010010100011001010", "stations_open": [True, True],
    "assignments": [{"ev": 0, "station": 0, "slot": 0}, {"ev": 1, "station": 1, "slot": 1}, {"ev": 1, "station": 1, "slot": 3}, {"ev": 2, "station": 0, "slot": 3}],
    "load": [1, 1, 0, 2], "feasible": True, "violations": [], "objective": 10.1,
    "cost_breakdown": {"electricity": 6.0, "detour": 0.1, "infrastructure": 2.5, "grid_stress": 1.5},
}

LADDER = [
    ["2×2×2",2,2,2,10,10,"0.04 s",5.8,"Yes"], ["3×2×4",3,2,4,22,22,"0.11 s",10.1,"Yes"],
    ["4×2×4",4,2,4,30,30,"0.28 s",13.7,"Yes"], ["4×3×4",4,3,4,43,43,"0.71 s",14.4,"Yes"], ["6×4×3",6,4,3,76,76,"2.10 s",20.2,"Yes"],
]

def result(solver="classical"):
    qaoa = solver == "qaoa"
    return {"run_id": f"demo-{solver}-001", "instance_id": BASELINE["id"], "solver": "Quantum / Hybrid QAOA" if qaoa else "Classical QUBO", "backend": "Demo backend", "seed": 42, "status": "completed", "runtime_s": 1.84 if qaoa else 0.11, "best": deepcopy(SOLUTION), "metrics": {"optimality_gap": "Placeholder / awaiting solver integration" if qaoa else "0.0% (reference demo)", "evaluations": 512 if qaoa else 24}, "resources": {"qubits": 22, "depth": 18 if qaoa else "N/A", "two_qubit_gates": 96 if qaoa else "N/A"}, "provenance": {"source": "precomputed demo", "timestamp": datetime.now(timezone.utc).isoformat()}}
