"""End-to-end verification script for the 5 mandatory acceptance test scenarios:

Test A: Small custom instance -> SA only -> verifies single SA schedule and no comparison.
Test B: Same small instance -> QAOA only -> verifies single QAOA schedule, quantum metrics, no comparison.
Test C: Same small instance -> SA + QAOA -> verifies both schedules, comparative load, comparison table.
Test D: Allowed large instance (8 EVs, 5 stations, 8 slots = 325 QUBO vars) -> SA runs, QAOA blocked.
Test E: Invalid custom problem (>8 EVs) -> rejected before solver with HTTP 400.
"""

import json
import sys
from server.app import app


def verify_all_scenarios():
    print("=" * 70)
    print("MANDATORY END-TO-END ACCEPTANCE VERIFICATION SCENARIOS")
    print("=" * 70)
    client = app.test_client()

    # Small problem instance: 2 EVs, 2 stations, 2 time slots (QUBO vars = 2 + 2*2*1 = 6)
    small_instance = {
        "id": "e2e-small-2x2x2",
        "name": "E2E Small 2x2x2 Instance",
        "n_ev": 2,
        "n_st": 2,
        "n_t": 2,
        "demand": [1, 1],
        "window": [[0], [1]],
        "price": [2.0, 5.0],
        "grid_cap": [1, 1],
        "open_cost": [10.0, 0.5],
        "detour": [[0.0, 10.0], [10.0, 0.0]],
        "stress_w": 0.25,
        "seed": 42,
    }

    # Register instance
    res = client.post("/api/instances", json=small_instance)
    assert res.status_code == 201, f"Failed to create instance: {res.data}"
    inst_data = res.get_json()
    print(f"\n[SETUP] Created test instance '{inst_data['id']}' with {inst_data['n_qubits']} QUBO variables.")

    # -------------------------------------------------------------
    # TEST A: SA Only
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST A: Small Custom Instance -> SA Only")
    print("-" * 70)
    res_a = client.post(
        "/api/instances/e2e-small-2x2x2/runs",
        json={
            "solvers": ["sa"],
            "params": {"sa": {"n_iterations": 1000, "restarts": 4, "seed": 42}},
        },
    )
    assert res_a.status_code == 201, f"Test A failed: {res_a.data}"
    data_a = res_a.get_json()

    print(f"  Solver: {data_a.get('solver')}")
    print(f"  Status: {data_a.get('status')}")
    print(f"  Objective: {data_a['best']['objective']}")
    print(f"  Feasible: {data_a['best']['feasible']}")
    print(f"  Schedule items: {len(data_a['best']['schedule'])}")
    print(f"  Grid load profile: {data_a['best']['load']}")
    print(f"  Multi-solver mode: {data_a.get('is_multi')}")
    print(f"  Comparison table present: {data_a.get('comparison', {}).get('has_comparison')}")

    assert data_a["status"] == "completed"
    assert data_a["solver_key"] == "sa"
    assert data_a["best"]["feasible"] is True
    assert len(data_a["best"]["schedule"]) == 2
    assert data_a.get("is_multi") is False
    assert data_a.get("comparison", {}).get("has_comparison") is False
    print("  >>> TEST A PASSED: SA solved instance, schedule rendered, no empty comparison blocks.")

    # -------------------------------------------------------------
    # TEST B: QAOA Only
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST B: Small Custom Instance -> QAOA Only")
    print("-" * 70)
    res_b = client.post(
        "/api/instances/e2e-small-2x2x2/runs",
        json={
            "solvers": ["qaoa"],
            "params": {"qaoa": {"p": 1, "shots": 128, "max_iterations": 10, "seed": 42}},
        },
    )
    assert res_b.status_code == 201, f"Test B failed: {res_b.data}"
    data_b = res_b.get_json()

    print(f"  Solver: {data_b.get('solver')}")
    print(f"  Status: {data_b.get('status')}")
    print(f"  Objective: {data_b['best']['objective']}")
    print(f"  Feasible: {data_b['best']['feasible']}")
    print(f"  Schedule items: {len(data_b['best']['schedule'])}")
    print(f"  Grid load profile: {data_b['best']['load']}")
    print(f"  Multi-solver mode: {data_b.get('is_multi')}")
    print(f"  Comparison table present: {data_b.get('comparison', {}).get('has_comparison')}")

    # Circuit resource verification
    res_b_metrics = data_b.get("resources", {})
    print(f"  Quantum Resources Measured:")
    print(f"    - Logical Qubits: {res_b_metrics.get('qubits')}")
    print(f"    - Circuit Depth: {res_b_metrics.get('depth')}")
    print(f"    - Transpiled Depth: {res_b_metrics.get('transpiled_depth')}")
    print(f"    - Two-Qubit Gates: {res_b_metrics.get('two_qubit_gates')}")
    print(f"    - Total Gates: {res_b_metrics.get('total_gates')}")
    print(f"    - Shots: {data_b.get('metrics', {}).get('shots')}")

    assert data_b["status"] == "completed"
    assert data_b["solver_key"] == "qaoa"
    assert len(data_b["best"]["schedule"]) == 2
    assert res_b_metrics.get("qubits") == 6
    assert res_b_metrics.get("depth") > 0
    assert res_b_metrics.get("two_qubit_gates") > 0
    assert data_b.get("is_multi") is False
    assert data_b.get("comparison", {}).get("has_comparison") is False
    print("  >>> TEST B PASSED: QAOA solved instance on Aer, circuit metrics measured, no empty comparison blocks.")

    # -------------------------------------------------------------
    # TEST C: SA + QAOA Multi-Solver Execution
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST C: Small Custom Instance -> SA + QAOA Concurrent")
    print("-" * 70)
    res_c = client.post(
        "/api/instances/e2e-small-2x2x2/runs",
        json={
            "solvers": ["sa", "qaoa"],
            "params": {
                "sa": {"n_iterations": 1000, "restarts": 4, "seed": 42},
                "qaoa": {"p": 1, "shots": 128, "max_iterations": 10, "seed": 42},
            },
        },
    )
    assert res_c.status_code == 201, f"Test C failed: {res_c.data}"
    data_c = res_c.get_json()

    print(f"  Multi-solver mode: {data_c.get('is_multi')}")
    print(f"  Solvers run: {list(data_c.get('results', {}).keys())}")
    sa_res = data_c["results"]["sa"]
    qaoa_res = data_c["results"]["qaoa"]
    print(f"  SA Result: Obj={sa_res['best']['objective']}, Feasible={sa_res['best']['feasible']}, Runtime={sa_res['runtime_s']}s")
    print(f"  QAOA Result: Obj={qaoa_res['best']['objective']}, Feasible={qaoa_res['best']['feasible']}, Runtime={qaoa_res['runtime_s']}s")
    print(f"  Comparison table rows count: {len(data_c.get('comparison', {}).get('rows', []))}")
    for row in data_c.get("comparison", {}).get("rows", []):
        print(f"    * Solver: {row['solver']}, Obj: {row['objective']}, Qubits: {row['qubits']}, Runtime: {row['runtime_s']}s")

    assert data_c.get("is_multi") is True
    assert data_c.get("comparison", {}).get("has_comparison") is True
    assert len(data_c["comparison"]["rows"]) >= 2
    assert "schedule" in sa_res["best"]
    assert "schedule" in qaoa_res["best"]
    print("  >>> TEST C PASSED: Multi-solver returned both schedules, load comparisons, and comparative table.")

    # -------------------------------------------------------------
    # TEST D: Allowed Large Instance (8 EVs x 5 Stations x 8 Slots = 325 vars)
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST D: Allowed Instance (8 EVs x 5 Stations x 8 Slots) -> SA Works, QAOA Cleanly Blocked")
    print("-" * 70)
    max_instance = {
        "id": "e2e-max-allowed-8x5x8",
        "name": "Max Allowed Instance (8 EVs, 5 Stations, 8 Slots)",
        "n_ev": 8,
        "n_st": 5,
        "n_t": 8,
        "demand": [1] * 8,
        "window": [list(range(8))] * 8,
        "price": [1.0, 1.2, 1.5, 2.0, 2.5, 1.8, 1.3, 1.0],
        "grid_cap": [4] * 8,
        "open_cost": [10.0, 12.0, 8.0, 15.0, 9.0],
        "detour": [[float(abs(e - s)) for s in range(5)] for e in range(8)],
        "stress_w": 0.25,
        "seed": 42,
    }
    res_d_create = client.post("/api/instances", json=max_instance)
    assert res_d_create.status_code == 201, f"Failed to create max allowed instance: {res_d_create.data}"
    d_data = res_d_create.get_json()
    print(f"  Registered allowed instance with {d_data['n_qubits']} binary variables (5 stations + 8*5*8 = 325).")
    assert d_data["n_qubits"] == 325

    # Run SA + QAOA on this 325-variable instance
    res_d_run = client.post(
        f"/api/instances/{max_instance['id']}/runs",
        json={
            "solvers": ["sa", "qaoa"],
            "params": {
                "sa": {"n_iterations": 500, "restarts": 1, "seed": 42},
                "qaoa": {"p": 1, "shots": 128},
            },
        },
    )
    assert res_d_run.status_code == 201, f"Run request failed: {res_d_run.data}"
    d_run_data = res_d_run.get_json()

    sa_d = d_run_data["results"]["sa"]
    qaoa_d = d_run_data["results"]["qaoa"]
    print(f"  SA status: {sa_d.get('status')} (Objective: {sa_d.get('best', {}).get('objective')})")
    print(f"  QAOA status: {qaoa_d.get('status')}")
    print(f"  QAOA reason: {qaoa_d.get('reason')}")
    print(f"  QAOA error message: {qaoa_d.get('error')}")

    assert sa_d["status"] == "completed"
    assert qaoa_d["status"] == "unsupported_size"
    assert qaoa_d["reason"] == "QAOA Aer simulation limit exceeded"
    assert "exceeding the configured Qiskit Aer simulation limit" in qaoa_d["error"]
    assert qaoa_d["actual_qubits"] == 325
    assert qaoa_d["maximum_simulation_qubits"] == 24
    print("  >>> TEST D PASSED: SA executed successfully, QAOA cleanly blocked at simulation guard without crashes.")

    # -------------------------------------------------------------
    # TEST E: Invalid Custom Problem (>8 EVs)
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST E: Invalid Custom Problem (>8 EVs) -> Rejected with HTTP 400")
    print("-" * 70)
    invalid_instance = {
        "id": "e2e-invalid-9evs",
        "name": "Invalid Instance (9 EVs)",
        "n_ev": 9,
        "n_st": 2,
        "n_t": 2,
        "demand": [1] * 9,
        "window": [[0, 1]] * 9,
        "price": [1.0, 2.0],
        "grid_cap": [4, 4],
        "open_cost": [1.0, 1.0],
        "detour": [[0.0, 0.0]] * 9,
        "stress_w": 0.25,
    }
    res_e = client.post("/api/instances", json=invalid_instance)
    print(f"  HTTP Status: {res_e.status_code}")
    print(f"  Response Body: {res_e.get_json()}")
    assert res_e.status_code == 400
    assert "max 8 EVs (got 9)" in res_e.get_json()["error"]
    print("  >>> TEST E PASSED: Rejected at API validation boundary before reaching QUBO or solver.")

    print("\n" + "=" * 70)
    print("ALL 5 END-TO-END ACCEPTANCE TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(verify_all_scenarios())
