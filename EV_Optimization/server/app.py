import json
import time
from flask import Flask, jsonify, request
from pathlib import Path
from evcore.mock import BASELINE, PRESETS, SOLUTION, LADDER, result
from evcore.pipeline import (
    run_optimization_pipeline,
    run_multi_solver_pipeline,
    compare_solvers_for_instance,
)
from evcore.qubo import QUBOModel
from evcore.qaoa_solver import QAOA_DEFAULT_SIMULATION_LIMIT

MAX_CUSTOM_EVS = 8
MAX_CUSTOM_STATIONS = 5
MAX_CUSTOM_SLOTS = 8
EXACT_MAX_SIMULATION_QUBITS = 20

DATA_DIR = Path(__file__).resolve().parent / "data"
STORAGE_FILE = DATA_DIR / "custom_instances.json"
BUILTIN_IDS = {p["id"] for p in PRESETS}


def load_persisted_instances():
    """Loads saved custom problem instances from disk."""
    candidates = [
        STORAGE_FILE,
        Path(r"c:\Users\LOQ\Desktop\Quantum_2k26\project_1-10-2026\server\data\custom_instances.json"),
        Path(r"C:\Users\LOQ\Desktop\Quantum_2k26\Quantique_RGUKTN\project_1-10-2026\server\data\custom_instances.json")
    ]
    for c in candidates:
        if c.exists():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and len(data) > 0:
                        return data
            except Exception:
                pass
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_persisted_instances(custom_insts):
    """Saves custom problem instances dictionary to disk atomically across workspaces."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_DIR / "custom_instances.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(custom_insts, f, indent=2)
    temp_file.replace(STORAGE_FILE)

    # Sync to both workspace locations if present
    alt_dirs = [
        Path(r"C:\Users\LOQ\Desktop\Quantum_2k26\Quantique_RGUKTN\project_1-10-2026\server\data"),
        Path(r"c:\Users\LOQ\Desktop\Quantum_2k26\project_1-10-2026\server\data")
    ]
    for ad in alt_dirs:
        if ad.exists():
            af = ad / "custom_instances.json"
            if af.resolve() != STORAGE_FILE.resolve():
                try:
                    atmp = ad / "custom_instances.tmp"
                    with open(atmp, "w", encoding="utf-8") as f:
                        json.dump(custom_insts, f, indent=2)
                    atmp.replace(af)
                except Exception:
                    pass


from evcore.ibm_hardware import (
    PROBLEM_A_CANONICAL,
    PROBLEM_B_CANONICAL,
    is_supported_live_instance,
    normalize_supported_id,
    get_supported_instance,
    run_live_ibm_experiment,
)

app = Flask(__name__, static_folder="static", static_url_path="")
instances = {p["id"]: dict(p) for p in PRESETS}
instances["instance-a-2x2x2"] = dict(PROBLEM_A_CANONICAL)


def sync_instances_from_disk():
    """Synchronizes in-memory instances with disk storage while protecting builtins."""
    persisted = load_persisted_instances()
    # Remove custom instances that were deleted from disk
    stale_keys = [k for k in list(instances.keys()) if k not in BUILTIN_IDS and k not in persisted and k != "instance-a-2x2x2"]
    for k in stale_keys:
        instances.pop(k, None)
    # Add/update custom instances from disk
    for cid, cdata in persisted.items():
        if cid not in BUILTIN_IDS:
            instances[cid] = cdata
    instances["instance-a-2x2x2"] = dict(PROBLEM_A_CANONICAL)


# Load persisted custom problems on startup
sync_instances_from_disk()

runs = {}

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.get("/api/health")
def health():
    return jsonify(
        status="ok",
        mode="prototype-local",
        primary_solver="Simulated Annealing (SA)",
        limits={
            "max_evs": MAX_CUSTOM_EVS,
            "max_stations": MAX_CUSTOM_STATIONS,
            "max_slots": MAX_CUSTOM_SLOTS,
            "qaoa_max_qubits": QAOA_DEFAULT_SIMULATION_LIMIT,
            "exact_max_qubits": EXACT_MAX_SIMULATION_QUBITS,
        },
    )

@app.get("/api/presets")
def presets():
    sync_instances_from_disk()
    custom_list = [inst for cid, inst in instances.items() if cid not in BUILTIN_IDS]
    return jsonify(
        presets=PRESETS,
        custom=custom_list,
        all=list(instances.values()),
        provenance="fixed demo presets and persisted custom instances",
    )

@app.get("/api/instances")
def list_instances():
    sync_instances_from_disk()
    custom_list = [inst for cid, inst in instances.items() if cid not in BUILTIN_IDS]
    return jsonify(
        presets=PRESETS,
        custom=custom_list,
        instances=list(instances.values()),
    )

@app.post("/api/instances")
def create_instance():
    data = request.get_json(silent=True) or BASELINE
    if not data.get("id") or data.get("id") == "custom-local":
        data["id"] = f"custom-{int(time.time() * 1000)}"
    data.setdefault("name", f"Custom Problem ({data.get('n_ev', 3)} EV x {data.get('n_st', 2)} Station x {data.get('n_t', 4)} Slot)")

    try:
        n_ev = int(data.get("n_ev", 3))
        n_st = int(data.get("n_st", 2))
        n_t = int(data.get("n_t", 4))
    except (ValueError, TypeError):
        return jsonify(error="Invalid dimension parameters."), 400

    # Strict backend validation of bounded custom problem limits
    if n_ev > MAX_CUSTOM_EVS or n_st > MAX_CUSTOM_STATIONS or n_t > MAX_CUSTOM_SLOTS:
        return jsonify(
            error=(
                f"Problem size exceeds maximum allowed limits: "
                f"max {MAX_CUSTOM_EVS} EVs (got {n_ev}), "
                f"max {MAX_CUSTOM_STATIONS} stations (got {n_st}), "
                f"max {MAX_CUSTOM_SLOTS} time slots (got {n_t})."
            )
        ), 400

    if n_ev < 1 or n_st < 1 or n_t < 1:
        return jsonify(error="Dimensions must be positive integers."), 400

    # Compute actual exact QUBO size
    try:
        model = QUBOModel(data)
        data["n_qubits"] = model.n_vars
    except Exception as exc:
        return jsonify(error=f"Invalid instance configuration: {exc}"), 400

    if data["id"] not in BUILTIN_IDS:
        data["is_custom"] = True

    instances[data["id"]] = data

    # Persist custom instances to disk
    if data["id"] not in BUILTIN_IDS:
        persisted = load_persisted_instances()
        persisted[data["id"]] = data
        save_persisted_instances(persisted)
        sync_instances_from_disk()

    return jsonify(data), 201

@app.delete("/api/instances/<instance_id>")
def delete_instance(instance_id):
    if instance_id in BUILTIN_IDS:
        return jsonify(error="Built-in preset instances cannot be deleted."), 403

    sync_instances_from_disk()
    if instance_id not in instances:
        return jsonify(error=f"Instance '{instance_id}' not found."), 404

    instances.pop(instance_id, None)
    persisted = load_persisted_instances()
    if instance_id in persisted:
        del persisted[instance_id]
        save_persisted_instances(persisted)
    sync_instances_from_disk()

    return jsonify(status="deleted", id=instance_id), 200

@app.get("/api/instances/<instance_id>")
def get_instance(instance_id):
    sync_instances_from_disk()
    if instance_id not in instances:
        return jsonify(error=f"Instance '{instance_id}' not found."), 404
    return jsonify(instances[instance_id])

@app.post("/api/instances/<instance_id>/runs")
def create_run(instance_id):
    sync_instances_from_disk()
    body = request.get_json(silent=True) or {}
    if instance_id not in instances:
        return jsonify(error=f"Instance '{instance_id}' not found. Please create or select a valid problem instance first."), 404
    inst = instances[instance_id]
    solvers = body.get("solvers")

    try:
        if isinstance(solvers, list) and len(solvers) > 0:
            params = body.get("params", {})
            run = run_multi_solver_pipeline(inst, solvers=solvers, params=params)
        else:
            solver = body.get("solver", "classical")
            params = body.get("params", body)
            run = run_optimization_pipeline(inst, solver=solver, params=params)
    except Exception as exc:
        return jsonify(error=str(exc)), 400

    runs[run["run_id"]] = run
    return jsonify(run), 201

@app.get("/api/runs/<run_id>")
def get_run(run_id):
    return jsonify(runs.get(run_id, result()))

@app.get("/api/results/baseline")
def baseline():
    return jsonify({**SOLUTION, "provenance": "precomputed baseline reference", "instance_id": BASELINE["id"]})

@app.get("/api/instances/<instance_id>/compare")
def compare(instance_id):
    sync_instances_from_disk()
    if instance_id not in instances:
        return jsonify(error=f"Instance '{instance_id}' not found."), 404
    inst = instances[instance_id]
    res = compare_solvers_for_instance(inst)
    for r in res.get("rows", []):
        if isinstance(r, dict) and "run_id" in r:
            runs[r["run_id"]] = r
    return jsonify(res)

@app.get("/api/results/ladder")
def ladder():
    return jsonify(rows=LADDER, provenance="demonstration/precomputed data")

@app.get("/api/scaling/ibm-demo")
def ibm_scaling_demo():
    from evcore.ibm_demo_data import get_ibm_scaling_data
    return jsonify(get_ibm_scaling_data())

@app.post("/api/estimate-resources")
def estimate_resources_endpoint():
    sync_instances_from_disk()
    from evcore.qaoa_resources import estimate_qaoa_resources
    payload = request.get_json() or {}
    inst = payload.get("instance")
    inst_id = payload.get("instance_id")
    if not inst and inst_id:
        if inst_id not in instances:
            return jsonify(error=f"Instance '{inst_id}' not found."), 404
        inst = instances[inst_id]
    if not inst:
        return jsonify(error="No problem instance provided for estimation."), 400

    p = payload.get("p", 1)
    backend_name = payload.get("backend", "ibm_brisbane")

    try:
        res = estimate_qaoa_resources(inst, p=p, backend_name=backend_name)
        return jsonify(res), 200
    except Exception as exc:
        return jsonify(error=str(exc)), 400

@app.get("/api/ibm/stored-result/<instance_id>")
def ibm_stored_result_endpoint(instance_id):
    canon_id = normalize_supported_id(instance_id)
    if not is_supported_live_instance(canon_id):
        return jsonify(status="demo_only", supported_live=False, instance_id=instance_id)

    p = request.args.get("p", "2")
    shots = request.args.get("shots", "2048")
    res_path = Path("results/ibm_hardware") / f"{canon_id}_p{p}_{shots}.json"
    if not res_path.exists():
        res_path = Path("results/ibm_hardware") / f"{canon_id}_p2_2048.json"

    if res_path.exists():
        try:
            with open(res_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data), 200
        except Exception as exc:
            return jsonify(status="read_error", error=str(exc)), 500
    return jsonify(status="not_executed", supported_live=True, instance_id=canon_id), 200


@app.post("/api/ibm/execute")
def ibm_execute_endpoint():
    payload = request.get_json() or {}
    inst_id = payload.get("instance_id", "demo-inst-1")

    # If explicitly one of the dedicated live instances and stored result exists
    if inst_id in ("instance-a-2x2x2", "custom-1791428968536"):
        canon_id = inst_id
        res_path = Path("results/ibm_hardware") / f"{canon_id}_p2_2048.json"
        if res_path.exists():
            try:
                with open(res_path, "r", encoding="utf-8") as f:
                    hw_res = json.load(f)
                inst_def = get_supported_instance(canon_id) or instances.get(canon_id)
                best_sol = hw_res.get("best_observed") or hw_res.get("best_solution") or {}
                best_feas = hw_res.get("best_feasible")
                return jsonify({
                    "status": "ok",
                    "instance_id": canon_id,
                    "source": "live" if hw_res.get("live_hardware") else "precomputed",
                    "source_label": "LIVE IBM HARDWARE RESULT" if hw_res.get("live_hardware") else "PRECOMPUTED IBM HARDWARE RESULT",
                    "is_live": bool(hw_res.get("live_hardware")),
                    "is_demo": not bool(hw_res.get("live_hardware")),
                    "problem": inst_def,
                    "metadata": {
                        "name": inst_def.get("name") if inst_def else canon_id,
                        "evs": inst_def.get("n_ev") if inst_def else 2,
                        "stations": inst_def.get("n_st") if inst_def else 2,
                        "time_slots": inst_def.get("n_t") if inst_def else 2,
                        "logical_qubits": hw_res.get("logical_qubits", 10),
                        "shots": hw_res.get("shots", 2048),
                        "qaoa_p": hw_res.get("p", 2),
                        "backend": hw_res.get("backend"),
                        "job_id": hw_res.get("job_id"),
                        "transpiled_depth": hw_res.get("transpiled_depth"),
                        "two_qubit_gates": hw_res.get("two_qubit_gates"),
                        "best_feasible_obj": best_feas.get("objective") if best_feas else "None (Infeasible)",
                        "feasible_prob": hw_res.get("feasible_sample_probability", 0.0),
                    },
                    "result": best_sol,
                    "aer_resources": hw_res.get("comparison_with_aer", {}).get("aer_qaoa"),
                    "ibm_resources": hw_res.get("resources"),
                    "aer_solution": hw_res.get("aer_solution"),
                    "hardware_report": hw_res,
                })
            except Exception:
                pass

    from evcore.ibm_demo_data import execute_ibm_hardware_problem
    return jsonify(execute_ibm_hardware_problem(inst_id))


@app.post("/api/ibm/hardware-run")
def ibm_hardware_run_endpoint():
    sync_instances_from_disk()
    payload = request.get_json() or {}
    inst_id = payload.get("instance_id") or "instance-a-2x2x2"
    canon_id = normalize_supported_id(inst_id)

    if not is_supported_live_instance(canon_id):
        return jsonify(
            status="hardware_failed",
            live_hardware=False,
            error_type="ScopeError",
            message="Live IBM Quantum hardware execution is strictly supported only for Problem A (2x2x2) and Problem B (3x2x4).",
        ), 400

    inst = get_supported_instance(canon_id) or instances.get(canon_id) or instances.get(inst_id)
    if not inst:
        return jsonify(status="hardware_failed", error=f"Instance '{inst_id}' not found."), 404

    p = int(payload.get("p", 2))
    shots = int(payload.get("shots", 2048))
    backend_name = payload.get("backend")
    api_key = payload.get("token")
    instance_crn = payload.get("instance_crn")
    mock = bool(payload.get("mock", False))

    res = run_live_ibm_experiment(
        instance=inst,
        p=p,
        shots=shots,
        backend_name=backend_name,
        api_key=api_key,
        instance_crn=instance_crn,
        mock_simulator=mock,
    )
    status_code = 200 if res.get("status") == "completed" else 400
    return jsonify(res), status_code

