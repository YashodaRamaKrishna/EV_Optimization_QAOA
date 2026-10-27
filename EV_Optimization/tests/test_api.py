from server.app import app

def test_health_and_baseline():
    client = app.test_client()
    res = client.get('/api/health')
    assert res.status_code == 200
    assert "Simulated Annealing" in res.get_json().get("primary_solver", "")
    data = client.get('/api/results/baseline').get_json()
    assert data['objective'] == 10.1 and data['feasible'] is True

def test_custom_instance_is_stored_with_detour_matrix():
    client = app.test_client()
    payload = {"id": "test-custom", "name": "Custom Problem", "n_ev": 2, "n_st": 2, "n_t": 3,
               "demand": [1, 2], "window": [[0, 1], [1, 2]], "price": [1, 2, 1],
               "grid_cap": [2, 2, 2], "open_cost": [1, 1.5], "detour": [[0, 3], [2, 0]],
               "stress_w": 0.25, "n_qubits": None}
    created = client.post('/api/instances', json=payload)
    assert created.status_code == 201
    assert created.get_json()['detour'] == [[0, 3], [2, 0]]
    assert client.get('/api/instances/test-custom').get_json()['n_t'] == 3

def test_create_run_simulated_annealing():
    client = app.test_client()
    payload = {
        "solver": "classical",
        "params": {
            "n_iterations": 3000,
            "restarts": 4,
            "seed": 42
        }
    }
    res = client.post('/api/instances/baseline-3x2x4/runs', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['solver'] == "Simulated Annealing (SA)"
    assert data['status'] == "completed"
    assert data['resources']['qubits'] == 22
    assert 'cost_breakdown' in data['best']
    assert data['best']['feasible'] is True

def test_compare_endpoint():
    client = app.test_client()
    res = client.get('/api/instances/baseline-3x2x4/compare')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data['rows']) >= 2
    solvers = [r['solver'] for r in data['rows']]
    assert any("Simulated Annealing" in s for s in solvers)
    assert any("QAOA" in s for s in solvers)

def test_custom_2x2x2_api_workflow():
    client = app.test_client()
    test_b = {
        "id": "custom-test-b-api",
        "name": "Custom Test B API",
        "n_ev": 2, "n_st": 2, "n_t": 2,
        "demand": [1, 1],
        "window": [[0], [1]],
        "price": [2.0, 5.0],
        "grid_cap": [1, 1],
        "open_cost": [10.0, 0.5],
        "detour": [[0.0, 10.0], [10.0, 0.0]],
        "stress_w": 0.25,
        "seed": 42
    }
    create_res = client.post('/api/instances', json=test_b)
    assert create_res.status_code == 201
    assert create_res.get_json()['n_qubits'] == 6

    run_res = client.post('/api/instances/custom-test-b-api/runs', json={
        "solver": "classical",
        "params": {"n_iterations": 1000, "restarts": 4, "seed": 42}
    })
    assert run_res.status_code == 201
    run_data = run_res.get_json()
    assert run_data['best']['feasible'] is True
    assert run_data['best']['objective'] == 18.0
    assert run_data['provenance']['is_demo'] is False
    assert run_data['resources']['qubits'] == 6


def test_bounded_problem_limits_rejected():
    """Verifies that problem definition bounds (max 8 EVs, 5 stations, 8 slots) are enforced with 400."""
    client = app.test_client()

    # 1. > 8 EVs
    res_ev = client.post('/api/instances', json={
        "id": "too-many-evs", "name": "9 EVs", "n_ev": 9, "n_st": 2, "n_t": 2,
        "demand": [1]*9, "window": [[0, 1]]*9, "price": [1, 2], "grid_cap": [4, 4],
        "open_cost": [1, 1], "detour": [[0, 0], [0, 0]]
    })
    assert res_ev.status_code == 400
    assert "max 8 EVs (got 9)" in res_ev.get_json()["error"]

    # 2. > 5 Stations
    res_st = client.post('/api/instances', json={
        "id": "too-many-st", "name": "6 Stations", "n_ev": 2, "n_st": 6, "n_t": 2,
        "demand": [1, 1], "window": [[0, 1], [0, 1]], "price": [1, 2], "grid_cap": [4, 4],
        "open_cost": [1]*6, "detour": [[0]*6]*2
    })
    assert res_st.status_code == 400
    assert "max 5 stations (got 6)" in res_st.get_json()["error"]

    # 3. > 8 Slots
    res_t = client.post('/api/instances', json={
        "id": "too-many-t", "name": "9 Slots", "n_ev": 2, "n_st": 2, "n_t": 9,
        "demand": [1, 1], "window": [[0, 1], [0, 1]], "price": [1]*9, "grid_cap": [4]*9,
        "open_cost": [1, 1], "detour": [[0, 0], [0, 0]]
    })
    assert res_t.status_code == 400
    assert "max 8 time slots (got 9)" in res_t.get_json()["error"]


def test_multi_solver_api_execution():
    """Verifies POST /api/instances/<id>/runs with multi-solver array."""
    client = app.test_client()
    payload = {
        "solvers": ["sa", "qaoa"],
        "params": {
            "sa": {"n_iterations": 500, "restarts": 2, "seed": 42},
            "qaoa": {"p": 1, "shots": 128, "max_iterations": 10, "seed": 42}
        }
    }
    res = client.post('/api/instances/custom-test-b-api/runs', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["is_multi"] is True
    assert "sa" in data["results"]
    assert "qaoa" in data["results"]
    assert data["results"]["sa"]["status"] == "completed"
    assert data["results"]["qaoa"]["status"] == "completed"
    assert "schedule" in data["results"]["sa"]["best"]
    assert "schedule" in data["results"]["qaoa"]["best"]
    assert data["comparison"]["has_comparison"] is True
    assert len(data["comparison"]["rows"]) >= 2


def test_qaoa_only_api_execution():
    """Verifies POST /api/instances/<id>/runs with single QAOA solver."""
    client = app.test_client()
    payload = {
        "solvers": ["qaoa"],
        "params": {
            "qaoa": {"p": 1, "shots": 128, "max_iterations": 10, "seed": 42}
        }
    }
    res = client.post('/api/instances/custom-test-b-api/runs', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["solver_key"] == "qaoa"
    assert data["status"] == "completed"
    assert "schedule" in data["best"]
    assert "quantum_resources" in data["best"] or "resources" in data
    assert data["resources"]["qubits"] == 6
    assert data["resources"]["total_gates"] > 0
    assert data["resources"]["two_qubit_gates"] > 0


def test_unknown_instance_returns_404():
    """Verifies that unmapped instance IDs return 404 instead of silent fallback to baseline."""
    client = app.test_client()
    res_get = client.get('/api/instances/nonexistent-xyz')
    assert res_get.status_code == 404
    assert "not found" in res_get.get_json()["error"]

    res_run = client.post('/api/instances/nonexistent-xyz/runs', json={"solver": "classical"})
    assert res_run.status_code == 404
    assert "not found" in res_run.get_json()["error"]


def test_presets_registration_and_small_instance_isolation():
    """Verifies that preset instances (such as small-2x2x2) are registered and run without cross-instance leakage."""
    client = app.test_client()
    # Check that small-2x2x2 is retrievable
    res_inst = client.get('/api/instances/small-2x2x2')
    assert res_inst.status_code == 200
    inst_data = res_inst.get_json()
    assert inst_data['n_ev'] == 2
    assert inst_data['n_t'] == 2

    # Run classical optimization on small-2x2x2
    res_run = client.post('/api/instances/small-2x2x2/runs', json={
        "solver": "classical",
        "params": {"n_iterations": 2000, "restarts": 4, "seed": 42}
    })
    assert res_run.status_code == 201
    run_data = res_run.get_json()
    assert run_data['instance_id'] == 'small-2x2x2'
    assert run_data['best']['feasible'] is True

    # Validate that no assignments exceed EV 1 or slot 1 (strictly EV1, EV2, T1, T2)
    assignments = run_data['best']['assignments']
    assert len(assignments) > 0
    for a in assignments:
        assert 0 <= a['ev'] < 2, f"Leaked out-of-bounds EV index: {a['ev']}"
        assert 0 <= a['slot'] < 2, f"Leaked out-of-bounds slot index: {a['slot']}"
        assert 0 <= a['station'] < 2, f"Leaked out-of-bounds station index: {a['station']}"


def test_baseline_endpoint_has_instance_id():
    """Verifies baseline endpoint includes instance_id for frontend single-source-of-truth validation."""
    client = app.test_client()
    data = client.get('/api/results/baseline').get_json()
    assert data.get("instance_id") == "baseline-3x2x4"


def test_custom_instance_persistence_and_deletion():
    """Verifies that custom instances are saved to persistent JSON storage and deleted cleanly."""
    from server.app import STORAGE_FILE, load_persisted_instances
    client = app.test_client()

    inst_id = "test-persistent-problem"
    payload = {
        "id": inst_id,
        "name": "Persistent Test Problem",
        "n_ev": 2, "n_st": 2, "n_t": 2,
        "demand": [1, 1],
        "window": [[0, 1], [0, 1]],
        "price": [1.0, 2.0],
        "grid_cap": [2, 2],
        "open_cost": [1.0, 1.0],
        "detour": [[0.0, 0.5], [0.5, 0.0]],
        "stress_w": 0.25,
        "seed": 42
    }

    # 1. Create and verify persistence
    create_res = client.post('/api/instances', json=payload)
    assert create_res.status_code == 201
    created_data = create_res.get_json()
    assert created_data["is_custom"] is True
    assert created_data["n_qubits"] == 10

    # Verify present on disk
    persisted = load_persisted_instances()
    assert inst_id in persisted
    assert persisted[inst_id]["name"] == "Persistent Test Problem"

    # Verify in presets endpoint
    presets_res = client.get('/api/presets').get_json()
    assert any(c["id"] == inst_id for c in presets_res.get("custom", []))

    # Verify instances list endpoint
    inst_list_res = client.get('/api/instances').get_json()
    assert any(c["id"] == inst_id for c in inst_list_res.get("custom", []))

    # 2. Delete and verify removal
    del_res = client.delete(f'/api/instances/{inst_id}')
    assert del_res.status_code == 200
    assert del_res.get_json()["status"] == "deleted"

    # Verify removed from disk
    persisted_after = load_persisted_instances()
    assert inst_id not in persisted_after

    # Verify 404 on subsequent get
    assert client.get(f'/api/instances/{inst_id}').status_code == 404


def test_builtin_presets_cannot_be_deleted():
    """Verifies that built-in demo presets cannot be deleted via DELETE API."""
    client = app.test_client()
    for builtin_id in ["baseline-3x2x4", "small-2x2x2", "medium-4x2x4", "larger-4x3x4"]:
        res = client.delete(f'/api/instances/{builtin_id}')
        assert res.status_code == 403
        assert "cannot be deleted" in res.get_json()["error"]


def test_human_readable_violation_numbering():
    """Verifies that violation messages use 1-based human-readable labels (EV 1, Station S1, Slot T1)."""
    from evcore.decoder import decode_solution
    from evcore.mock import BASELINE

    # An all-zero bitstring for baseline (3 EVs, 2 stations, 4 slots)
    # Means stations are closed and demand is unmet for all 3 EVs
    all_zeros = "0" * BASELINE["n_qubits"]
    res = decode_solution(all_zeros, BASELINE)
    assert res["feasible"] is False
    violations = res["violations"]

    # Verify demand violations for first, second, and last EV
    assert any("Demand violation: EV 1" in v for v in violations), "Missing EV 1 demand violation"
    assert any("Demand violation: EV 2" in v for v in violations), "Missing EV 2 demand violation"
    assert any("Demand violation: EV 3" in v for v in violations), "Missing EV 3 demand violation"

    # Strict check: NO zero-indexed EV 0, Station 0, or Slot 0 anywhere in violation text
    for v in violations:
        assert "EV 0" not in v, f"Found 0-indexed EV 0 in: {v}"
        assert "Station 0" not in v, f"Found 0-indexed Station 0 in: {v}"
        assert "Slot 0" not in v, f"Found 0-indexed Slot 0 in: {v}"
        assert "station 0" not in v, f"Found 0-indexed station 0 in: {v}"
        assert "slot 0" not in v, f"Found 0-indexed slot 0 in: {v}"



