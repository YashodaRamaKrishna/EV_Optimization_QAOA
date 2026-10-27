"""Dedicated Live IBM Quantum Hardware Execution Module.

Provides genuine hardware-targeted transpilation, IBM Quantum Runtime submission,
raw measurement extraction, and solution decoding for EV charging QAOA circuits.
Operates on the EXACT SAME binary QUBO and Ising formulation as classical solvers.

Scope is STRICTLY locked to two validated problem instances:
- Problem A: 2 EV × 2 Stations × 2 Slots (instance-a-2x2x2, 10 qubits)
- Problem B: 3 EV × 2 Stations × 4 Slots (custom-1791428968536, 20 qubits)
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import os
import json
import time
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

from evcore.qubo import QUBOModel, normalize_instance
from evcore.decoder import decode_solution
from evcore.qaoa_solver import QAOASolver

# Import credentials and default backend from ibm_config if present
try:
    import ibm_config
    DEFAULT_API_KEY = getattr(ibm_config, "IBM_QUANTUM_API_KEY", "xxxxxx")
    DEFAULT_BACKEND = getattr(ibm_config, "IBM_QUANTUM_BACKEND", None)
    DEFAULT_INSTANCE = getattr(ibm_config, "IBM_QUANTUM_INSTANCE", "xxxxxx")
except ImportError:
    DEFAULT_API_KEY = "xxxxxx"
    DEFAULT_BACKEND = None
    DEFAULT_INSTANCE = "xxxxxx"


# Scope lock: strictly two supported live problems
LIVE_IBM_INSTANCES = {
    "instance-a-2x2x2",
    "small-2x2x2",
    "custom-1791428968536",
}

# Canonical instance definitions
PROBLEM_A_CANONICAL = {
    "id": "instance-a-2x2x2",
    "name": "Problem A — 2 EV × 2 Stations × 2 Slots",
    "n_ev": 2,
    "n_st": 2,
    "n_t": 2,
    "demand": [1, 1],
    "window": [[0, 1], [0, 1]],
    "price": [1.0, 2.0],
    "grid_cap": [2, 2],
    "open_cost": [1.0, 1.5],
    "detour": [[0.0, 0.3], [0.2, 0.0]],
    "stress_w": 0.25,
    "n_qubits": 10,
    "seed": 42,
}

PROBLEM_B_CANONICAL = {
    "id": "custom-1791428968536",
    "name": "Problem B — 3 EV × 2 Stations × 4 Slots",
    "n_ev": 3,
    "n_st": 2,
    "n_t": 4,
    "demand": [2, 2, 1],
    "window": [[1, 2, 3], [0, 1, 2], [1, 2, 3]],
    "price": [1.2, 1.3, 1.1, 1.1],
    "grid_cap": [2, 2, 2, 2],
    "open_cost": [1.7, 1.0],
    "detour": [[0.2, 0.2], [0.2, 0.3], [0.2, 0.1]],
    "stress_w": 0.45,
    "n_qubits": 20,
    "seed": 42,
}


def normalize_supported_id(instance_id: str) -> str:
    """Normalizes alias identifiers to canonical supported problem IDs."""
    if instance_id in ("instance-a-2x2x2", "small-2x2x2", "demo-inst-1"):
        return "instance-a-2x2x2"
    if instance_id in ("custom-1791428968536", "3x2x4_final"):
        return "custom-1791428968536"
    return instance_id


def is_supported_live_instance(instance_id: str) -> bool:
    """Checks whether an instance ID belongs to the two supported hardware problems."""
    norm = normalize_supported_id(instance_id)
    return norm in ("instance-a-2x2x2", "custom-1791428968536")


def get_supported_instance(instance_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the canonical definition for a supported live instance."""
    norm = normalize_supported_id(instance_id)
    if norm == "instance-a-2x2x2":
        return dict(PROBLEM_A_CANONICAL)
    if norm == "custom-1791428968536":
        return dict(PROBLEM_B_CANONICAL)
    return None


def get_ibm_credentials(
    api_key: Optional[str] = None,
    backend_name: Optional[str] = None,
    instance_crn: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolves IBM Quantum credentials from arguments, environment variables, or config."""
    token = (
        api_key
        or os.environ.get("IBM_QUANTUM_API_KEY")
        or os.environ.get("QISKIT_IBM_TOKEN")
        or os.environ.get("IBMQ_TOKEN")
        or DEFAULT_API_KEY
    )
    if token == "xxxxxx" or not token or not token.strip():
        token = None

    backend = (
        backend_name
        or os.environ.get("IBM_QUANTUM_BACKEND")
        or DEFAULT_BACKEND
    )

    inst = (
        instance_crn
        or os.environ.get("IBM_QUANTUM_INSTANCE")
        or DEFAULT_INSTANCE
    )
    if inst == "xxxxxx" or not inst or not inst.strip():
        inst = None

    return token, backend, inst


def mask_crn(crn: Optional[str]) -> str:
    """Returns a safe, masked representation of an instance CRN."""
    if not crn or crn == "xxxxxx":
        return "<not configured>"
    if len(crn) <= 16:
        return crn[:4] + "..."
    return crn[:12] + "..." + crn[-8:]


def select_ibm_backend(
    service: Any,
    target_backend_name: Optional[str] = None,
    min_qubits: int = 10,
) -> Any:
    """Selects an operational, real IBM Quantum hardware backend.

    Never selects simulators, fake backends, or mock backends.
    """
    if target_backend_name:
        backend = service.backend(target_backend_name)
        if getattr(backend, "simulator", False):
            raise ValueError(
                f"Selected backend '{target_backend_name}' is a simulator, not real IBM Quantum hardware."
            )
        status = backend.status()
        if not getattr(status, "operational", True):
            raise RuntimeError(
                f"Backend '{target_backend_name}' is currently not operational."
            )
        if backend.num_qubits < min_qubits:
            raise ValueError(
                f"Backend '{target_backend_name}' has {backend.num_qubits} physical qubits; "
                f"{min_qubits} are required for this problem."
            )
        return backend

    # Safe automated selection: filter real hardware backends with sufficient qubits
    backends = service.backends(
        simulator=False,
        operational=True,
        min_num_qubits=min_qubits,
    )
    if not backends:
        raise RuntimeError(
            f"No operational IBM Quantum hardware backend found with >= {min_qubits} physical qubits."
        )

    # Pick least busy if possible, otherwise first available
    try:
        from qiskit_ibm_runtime import least_busy
        return least_busy(backends)
    except Exception:
        return backends[0]


def test_ibm_connection(
    api_key: Optional[str] = None,
    instance_crn: Optional[str] = None,
    backend_name: Optional[str] = None,
    min_qubits: int = 10,
) -> Dict[str, Any]:
    """Tests connection to IBM Quantum Platform using IBM_QUANTUM_API_KEY and CRN.

    Does NOT submit a quantum job.
    """
    # Protect against Windows Application Control blocking sspilib/requests_ntlm
    import sys
    if "requests_ntlm" not in sys.modules:
        from unittest.mock import MagicMock
        sys.modules["requests_ntlm"] = MagicMock()

    token, bname, inst = get_ibm_credentials(api_key, backend_name, instance_crn)

    if not token:
        err = "IBM Quantum authentication token is not configured. Set IBM_QUANTUM_API_KEY or replace 'xxxxxx' in ibm_config.py."
        print(f"\n[ERROR] {err}")
        return {"status": "hardware_failed", "live_hardware": False, "error_type": "AuthenticationError", "message": err}

    if not inst:
        err = "IBM Quantum Instance CRN is not configured. Set IBM_QUANTUM_INSTANCE or replace 'xxxxxx' in ibm_config.py."
        print(f"\n[ERROR] {err}")
        return {"status": "hardware_failed", "live_hardware": False, "error_type": "InstanceNotConfigured", "message": err}

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=token,
            instance=inst,
        )
        backend = select_ibm_backend(service, bname, min_qubits=min_qubits)
        status = backend.status()
        is_operational = bool(getattr(status, "operational", True))

        print("==================================================")
        print("IBM QUANTUM HARDWARE CONNECTION")
        print("==================================================")
        print("Channel:         ibm_quantum_platform")
        print(f"Instance:        {mask_crn(inst)}")
        print(f"Backend:         {backend.name}")
        print(f"Physical qubits: {backend.num_qubits}")
        print(f"Operational:     {is_operational}")
        print("==================================================")

        return {
            "status": "connected",
            "live_hardware": True,
            "channel": "ibm_quantum_platform",
            "instance": mask_crn(inst),
            "backend": backend.name,
            "backend_type": "IBM Quantum hardware",
            "physical_qubits": backend.num_qubits,
            "operational": is_operational,
        }
    except Exception as exc:
        err_msg = f"IBM Quantum hardware connection failed: {str(exc)}"
        print(f"\n[ERROR] {err_msg}")
        return {
            "status": "hardware_failed",
            "live_hardware": False,
            "error_type": type(exc).__name__,
            "message": err_msg,
        }


def run_live_ibm_experiment(
    instance: Dict[str, Any],
    p: int = 2,
    shots: int = 2048,
    backend_name: Optional[str] = None,
    api_key: Optional[str] = None,
    instance_crn: Optional[str] = None,
    mock_simulator: bool = False,
    results_dir: str = "results/ibm_hardware",
) -> Dict[str, Any]:
    """Executes a real IBM Quantum hardware experiment on an EV problem instance.

    Scope: Strictly limited to Problem A (instance-a-2x2x2) and Problem B (custom-1791428968536).
    Channel: channel='ibm_quantum_platform'.
    NEVER silently falls back to precomputed demo data.
    """
    start_time = time.time()
    raw_id = instance.get("id") or instance.get("instance_id") or "unknown"
    canon_id = normalize_supported_id(raw_id)

    # 1. Scope verification
    if not is_supported_live_instance(canon_id):
        err = (
            f"Instance '{raw_id}' is not supported for live IBM Quantum hardware execution. "
            f"Live hardware execution is strictly supported only for: "
            f"Problem A (instance-a-2x2x2, 10 qubits) and Problem B (custom-1791428968536, 20 qubits)."
        )
        print(f"\n[SCOPE REJECTION] {err}")
        return {
            "status": "hardware_failed",
            "live_hardware": False,
            "error_type": "ScopeError",
            "message": err,
            "instance_id": raw_id,
        }

    # Retrieve canonical definition to guarantee mathematical consistency
    norm_inst = get_supported_instance(canon_id) or normalize_instance(instance)
    instance_id = canon_id
    n_ev = norm_inst["n_ev"]
    n_st = norm_inst["n_st"]
    n_t = norm_inst["n_t"]

    # 2. Compile identical binary QUBO model
    model = QUBOModel(norm_inst)
    n_vars = model.n_vars
    J, h, c_ising = model.to_ising()
    Q_sym = model.Q_sym
    off = float(model.offset)

    print("==================================================")
    print("IBM QUANTUM HARDWARE EXPERIMENT SETUP")
    print("==================================================")
    print(f"Instance ID:            {instance_id}")
    print(f"EVs:                    {n_ev}")
    print(f"Stations:               {n_st}")
    print(f"Time slots:             {n_t}")
    print(f"QUBO binary variables:  {n_vars}")
    print(f"Logical Qubits:         {n_vars}")
    print(f"QAOA Layers (p):        {p}")
    print(f"Measurement Shots:      {shots}")

    # 3. Resolve credentials
    token, target_backend_name, target_instance = get_ibm_credentials(
        api_key=api_key,
        backend_name=backend_name,
        instance_crn=instance_crn,
    )

    if not mock_simulator:
        if not token:
            err_msg = (
                "IBM Quantum authentication token is not configured. "
                "Please set environment variable IBM_QUANTUM_API_KEY=<token> "
                "or replace 'xxxxxx' in ibm_config.py with your active API key."
            )
            print(f"\n[ERROR] {err_msg}")
            return {
                "status": "hardware_failed",
                "live_hardware": False,
                "error_type": "AuthenticationError",
                "message": err_msg,
                "instance_id": instance_id,
                "logical_qubits": n_vars,
                "p": p,
                "shots": shots,
            }

        if not target_instance:
            err_msg = (
                "IBM Quantum Instance CRN is not configured. "
                "Please set environment variable IBM_QUANTUM_INSTANCE=<crn> "
                "or replace 'xxxxxx' in ibm_config.py with your instance CRN."
            )
            print(f"\n[ERROR] {err_msg}")
            return {
                "status": "hardware_failed",
                "live_hardware": False,
                "error_type": "InstanceNotConfigured",
                "message": err_msg,
                "instance_id": instance_id,
                "logical_qubits": n_vars,
                "p": p,
                "shots": shots,
            }

    # 4. Optimize parameters on Aer simulator workflow and freeze them
    print("\n--- Step 1: Classical Parameter Optimization on Aer Workflow ---")
    aer_solver = QAOASolver(p=p, shots=shots, seed=42)
    aer_result = aer_solver.solve(model)
    opt_params = aer_result.get("metrics", {}).get("optimal_parameters", {})
    gammas = np.array(opt_params.get("gamma", [0.4] * p), dtype=float)
    betas = np.array(opt_params.get("beta", [0.4] * p), dtype=float)
    print(f"Frozen Optimal Gamma: {list(np.round(gammas, 4))}")
    print(f"Frozen Optimal Beta:  {list(np.round(betas, 4))}")

    # Aer reference metrics for sanity comparison
    aer_best_bitstring = aer_result.get("best_bitstring")
    aer_best_obj = None
    aer_best_feasible = False
    if aer_best_bitstring:
        dec_aer = decode_solution(aer_best_bitstring, model)
        aer_best_obj = dec_aer.get("objective")
        aer_best_feasible = dec_aer.get("feasible", False)
    aer_feasible_prob = aer_result.get("metrics", {}).get("feasible_sample_probability", 0.0)

    # 5. Build exact QAOA circuit
    print("\n--- Step 2: Build Hardware QAOA Circuit ---")
    qc = QuantumCircuit(n_vars)
    qc.h(range(n_vars))
    for l in range(p):
        gamma_l = gammas[l]
        beta_l = betas[l]
        # Cost Hamiltonian unitary
        for i in range(n_vars):
            for j in range(i + 1, n_vars):
                if abs(J[i, j]) > 1e-6:
                    qc.rzz(4.0 * gamma_l * J[i, j], i, j)
            if abs(h[i]) > 1e-6:
                qc.rz(2.0 * gamma_l * h[i], i)
        # Mixer unitary
        for i in range(n_vars):
            qc.rx(2.0 * beta_l, i)
    qc.measure_all()
    print(f"Synthesized logical circuit depth: {qc.depth()}, ops: {dict(qc.count_ops())}")

    # 6. Connect to IBM Quantum Platform
    real_backend = None
    job_id = None
    is_live = False

    if not mock_simulator:
        print("\n--- Step 3: Connect to IBM Quantum Platform ---")
        try:
            import sys
            if "requests_ntlm" not in sys.modules:
                from unittest.mock import MagicMock
                sys.modules["requests_ntlm"] = MagicMock()

            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

            service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=token,
                instance=target_instance,
            )
            real_backend = select_ibm_backend(
                service,
                target_backend_name=target_backend_name,
                min_qubits=n_vars,
            )
            backend_status = real_backend.status()
            status_msg = getattr(backend_status, "status_msg", "active")
            print(f"IBM backend:        {real_backend.name}")
            print(f"Backend status:     {status_msg}")
            print(f"Physical qubits:    {real_backend.num_qubits}")
            is_live = True

        except Exception as exc:
            err_msg = f"Failed to connect to IBM Quantum Platform backend: {str(exc)}"
            print(f"[ERROR] {err_msg}")
            return {
                "status": "hardware_failed",
                "live_hardware": False,
                "error_type": type(exc).__name__,
                "message": err_msg,
                "instance_id": instance_id,
                "logical_qubits": n_vars,
                "backend_requested": target_backend_name,
            }

    # 7. Hardware-targeted transpilation
    print("\n--- Step 4: Hardware-Targeted Transpilation ---")
    try:
        if is_live and real_backend is not None:
            t_qc = transpile(
                qc,
                backend=real_backend,
                optimization_level=1,
                seed_transpiler=42,
            )
            phys_qubits_device = real_backend.num_qubits
            backend_label = real_backend.name
        else:
            # Transpile against target 127-qubit topology for mock validation
            cm = CouplingMap.from_heavy_hex(distance=7)
            t_qc = transpile(
                qc,
                coupling_map=cm,
                basis_gates=["rz", "sx", "x", "cx"],
                optimization_level=1,
                seed_transpiler=42,
            )
            phys_qubits_device = 127
            backend_label = target_backend_name or "ibm_brisbane"
    except Exception as exc:
        err_msg = f"Transpilation failed for target backend: {str(exc)}"
        print(f"[ERROR] {err_msg}")
        return {
            "status": "hardware_failed",
            "live_hardware": False,
            "error_type": "TranspilationError",
            "message": err_msg,
            "instance_id": instance_id,
        }

    transpiled_depth = t_qc.depth()
    ops = t_qc.count_ops()
    total_gates = sum(v for k, v in ops.items() if k != "measure")
    one_q_gates = sum(v for k, v in ops.items() if k in ["rz", "sx", "x", "id", "u", "u1", "u2", "u3"])
    two_q_gates = sum(v for k, v in ops.items() if k in ["cx", "cz", "ecr", "rzz", "swap"])
    active_qubits = {t_qc.find_bit(q).index for inst_i in t_qc.data for q in inst_i.qubits if q in t_qc.qubits}
    phys_qubits_used = len(active_qubits) if active_qubits else n_vars

    print("=== IBM HARDWARE TRANSPILE ===")
    print(f"Backend:              {backend_label}")
    print(f"Logical qubits:       {n_vars}")
    print(f"Physical qubits used: {phys_qubits_used}")
    print(f"Device total qubits:  {phys_qubits_device}")
    print(f"Transpiled depth:     {transpiled_depth}")
    print(f"Total gates:          {total_gates}")
    print(f"1Q gates:             {one_q_gates}")
    print(f"2Q/CX gates:          {two_q_gates}")

    # 8. Execute on real IBM Quantum Hardware
    print("\n--- Step 5: Hardware Execution ---")
    counts_raw: Dict[str, int] = {}

    try:
        if is_live and real_backend is not None:
            sampler = SamplerV2(mode=real_backend)
            print(f"Submitting job to real IBM Quantum hardware '{real_backend.name}' with {shots} shots...")
            job = sampler.run([t_qc], shots=shots)
            job_id = job.job_id()
            print(f"Job ID: {job_id}")
            print("Waiting for job execution to complete on IBM Quantum...")
            job_res = job.result()
            pub_data = job_res[0].data

            # Extract measurement counts from BitArray container
            for attr in dir(pub_data):
                val = getattr(pub_data, attr, None)
                if hasattr(val, "get_counts"):
                    counts_raw = val.get_counts()
                    break
        else:
            # Mock verification mode using AerSimulator on transpiled circuit
            from qiskit_aer import AerSimulator
            print(f"[MOCK MODE] Executing circuit via AerSimulator with {shots} shots...")
            sim = AerSimulator()
            job = sim.run(t_qc, shots=shots)
            job_id = f"mock-job-{int(time.time())}"
            counts_raw = job.result().get_counts()

    except Exception as exc:
        err_msg = f"IBM Quantum job execution failed: {str(exc)}"
        print(f"[ERROR] {err_msg}")
        return {
            "status": "hardware_failed",
            "live_hardware": False,
            "error_type": "ExecutionError",
            "message": err_msg,
            "instance_id": instance_id,
            "job_id": job_id,
            "backend": backend_label,
        }

    # 9. Process Raw Counts & Bitstring Reversal
    # Qiskit BitArray counts are little-endian:
    # rightmost character is classical bit 0 (qubit 0).
    # Reversing (bitstr[::-1]) aligns index 0 with qubit 0 (station 0 open).
    print("\n--- Step 6: Process Measurement Bitstrings & Decoder ---")
    counts_qubo: Dict[str, int] = {}
    for raw_str, cnt in counts_raw.items():
        qubo_str = raw_str.strip()[::-1]
        counts_qubo[qubo_str] = counts_qubo.get(qubo_str, 0) + cnt

    total_observed_shots = sum(counts_qubo.values())
    distinct_bitstrings = len(counts_qubo)

    most_frequent_bitstring = max(counts_qubo, key=counts_qubo.get)
    most_frequent_count = counts_qubo[most_frequent_bitstring]
    most_frequent_freq = round(most_frequent_count / max(1, total_observed_shots), 6)

    # Evaluate all observed candidates with system decoder
    best_qubo_bitstring = None
    best_qubo_energy = float("inf")
    best_qubo_count = 0

    best_feasible_bitstring = None
    best_feasible_energy = float("inf")
    best_feasible_count = 0
    best_feasible_obj = None

    feasible_sample_count = 0

    for bitstr, cnt in counts_qubo.items():
        z = np.array([int(c) for c in bitstr], dtype=float)
        energy = float(z @ Q_sym @ z + off)

        if energy < best_qubo_energy:
            best_qubo_energy = energy
            best_qubo_bitstring = bitstr
            best_qubo_count = cnt

        dec = decode_solution(bitstr, model)
        if dec["feasible"]:
            feasible_sample_count += cnt
            if energy < best_feasible_energy:
                best_feasible_energy = energy
                best_feasible_bitstring = bitstr
                best_feasible_count = cnt
                best_feasible_obj = dec["objective"]

    feasible_sample_prob = round(feasible_sample_count / max(1, total_observed_shots), 6)
    best_qubo_prob = round(best_qubo_count / max(1, total_observed_shots), 6)
    best_feasible_prob = round(best_feasible_count / max(1, total_observed_shots), 6) if best_feasible_bitstring else 0.0

    dec_best_qubo = decode_solution(best_qubo_bitstring, model) if best_qubo_bitstring else {}

    print(f"Total shots observed:            {total_observed_shots}")
    print(f"Number of distinct bitstrings:   {distinct_bitstrings}")
    print(f"Most frequent bitstring:         {most_frequent_bitstring} (count={most_frequent_count}, p={most_frequent_freq})")
    print(f"Best QUBO energy bitstring:      {best_qubo_bitstring}")
    print(f"  Count:                         {best_qubo_count} (p={best_qubo_prob})")
    print(f"  QUBO Energy:                   {round(best_qubo_energy, 4)}")
    print(f"  Feasible:                      {dec_best_qubo.get('feasible', False)}")
    print(f"  Physical Objective:            {dec_best_qubo.get('objective')}")
    print(f"Feasible samples observed:       {feasible_sample_count} of {total_observed_shots} (p={feasible_sample_prob})")

    if best_feasible_bitstring:
        print(f"Best feasible bitstring:         {best_feasible_bitstring}")
        print(f"  Count:                         {best_feasible_count} (p={best_feasible_prob})")
        print(f"  Physical Objective:            {best_feasible_obj}")
    else:
        print("  Notice: No feasible solution observed in 2048 hardware shots.")

    # Full Aer solution decoding for side-by-side comparison
    aer_solution = None
    if aer_result.get("status") == "completed" and aer_best_bitstring:
        dec_aer = decode_solution(aer_best_bitstring, model)
        aer_solution = {
            "status": "completed",
            "solver": "Quantum / Hybrid QAOA (Aer)",
            "bitstring": aer_best_bitstring,
            "feasible": dec_aer.get("feasible", False),
            "objective": dec_aer.get("objective"),
            "violations": dec_aer.get("violations", []),
            "stations_open": dec_aer.get("stations_open", []),
            "assignments": dec_aer.get("assignments", []),
            "schedule": dec_aer.get("assignments", []),
            "load": dec_aer.get("load", []),
            "cost_breakdown": dec_aer.get("cost_breakdown", {}),
            "metrics": aer_result.get("metrics", {}),
            "resources": aer_result.get("resources", {}),
        }
    elif aer_result.get("status") == "unsupported_size":
        aer_solution = {
            "status": "unsupported_size",
            "reason": aer_result.get("reason"),
            "message": aer_result.get("message"),
            "actual_qubits": n_vars,
        }

    # 10. Construct dedicated hardware result matching required schema
    execution_runtime = round(time.time() - start_time, 2)

    best_observed_obj = {
        "bitstring": best_qubo_bitstring,
        "count": best_qubo_count,
        "probability": best_qubo_prob,
        "qubo_energy": round(best_qubo_energy, 4),
        "feasible": bool(dec_best_qubo.get("feasible", False)),
        "objective": dec_best_qubo.get("objective"),
        "violations": dec_best_qubo.get("violations", []),
        "stations_open": dec_best_qubo.get("stations_open", []),
        "assignments": dec_best_qubo.get("assignments", []),
        "schedule": dec_best_qubo.get("assignments", []),
        "load": dec_best_qubo.get("load", []),
        "cost_breakdown": dec_best_qubo.get("cost_breakdown", {}),
    }

    best_feasible_obj_entry = None
    if best_feasible_bitstring:
        dec_feasible = decode_solution(best_feasible_bitstring, model)
        best_feasible_obj_entry = {
            "bitstring": best_feasible_bitstring,
            "count": best_feasible_count,
            "probability": best_feasible_prob,
            "qubo_energy": round(best_feasible_energy, 4),
            "feasible": True,
            "objective": best_feasible_obj,
            "violations": [],
            "stations_open": dec_feasible.get("stations_open", []),
            "assignments": dec_feasible.get("assignments", []),
            "schedule": dec_feasible.get("assignments", []),
            "load": dec_feasible.get("load", []),
            "cost_breakdown": dec_feasible.get("cost_breakdown", {}),
        }

    report = {
        "source": "IBM Quantum Hardware" if is_live else "Aer Simulator (Mock Validation)",
        "live_hardware": is_live,
        "status": "completed",
        "instance_id": instance_id,
        "backend": backend_label,
        "backend_type": "IBM Quantum hardware" if is_live else "Simulator",
        "job_id": job_id,
        "logical_qubits": n_vars,
        "physical_qubits": phys_qubits_device,
        "physical_qubits_used": phys_qubits_used,
        "p": p,
        "shots": shots,
        "optimal_parameters": {
            "gamma": [round(float(g), 4) for g in gammas],
            "beta": [round(float(b), 4) for b in betas],
        },
        "transpiled_depth": transpiled_depth,
        "total_gates": total_gates,
        "one_qubit_gates": one_q_gates,
        "two_qubit_gates": two_q_gates,
        "counts": counts_qubo,
        "statistics": {
            "total_shots": total_observed_shots,
            "distinct_bitstrings": distinct_bitstrings,
            "most_frequent_bitstring": most_frequent_bitstring,
            "most_frequent_count": most_frequent_count,
            "most_frequent_frequency": most_frequent_freq,
        },
        "best_observed": best_observed_obj,
        "best_feasible": best_feasible_obj_entry,
        "feasible_sample_count": feasible_sample_count,
        "feasible_sample_probability": feasible_sample_prob,
        "aer_solution": aer_solution,

        # Backward compatibility fields for dashboard UI renderer
        "instance_summary": {
            "n_ev": n_ev,
            "n_st": n_st,
            "n_t": n_t,
            "qubo_variables": n_vars,
            "logical_qubits": n_vars,
        },
        "resources": {
            "logical_qubits": n_vars,
            "physical_qubits_used": phys_qubits_used,
            "transpiled_depth": transpiled_depth,
            "total_gates": total_gates,
            "one_qubit_gates": one_q_gates,
            "two_qubit_gates": two_q_gates,
        },
        "best_solution": best_observed_obj,
        "feasibility": {
            "feasible_sample_count": feasible_sample_count,
            "feasible_sample_probability": feasible_sample_prob,
            "best_feasible_bitstring": best_feasible_bitstring,
            "best_feasible_count": best_feasible_count,
            "best_feasible_probability": best_feasible_prob,
            "best_feasible_energy": round(best_feasible_energy, 4) if best_feasible_bitstring else None,
            "best_feasible_objective": best_feasible_obj,
            "has_feasible_solution": bool(best_feasible_bitstring),
            "message": "Feasible solution found" if best_feasible_bitstring else "No feasible solution observed in 2048 hardware shots.",
        },
        "comparison_with_aer": {
            "p": p,
            "shots": shots,
            "aer_qaoa": {
                "best_objective": aer_best_obj,
                "feasible": aer_best_feasible,
                "feasible_probability": aer_feasible_prob,
            },
            "ibm_hardware": {
                "best_objective": dec_best_qubo.get("objective"),
                "feasible": dec_best_qubo.get("feasible", False),
                "feasible_probability": feasible_sample_prob,
            },
        },
        "runtime_s": execution_runtime,
    }

    # 11. Save artifact
    try:
        os.makedirs(results_dir, exist_ok=True)
        filename = f"{instance_id}_p{p}_{shots}.json"
        filepath = os.path.join(results_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        if p == 2 and shots == 2048:
            filepath_base = os.path.join(results_dir, f"{instance_id}_p2_2048.json")
            with open(filepath_base, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        print(f"\nArtifact saved to: {filepath}")
    except Exception as exc:
        print(f"[Warning] Failed to write result artifact: {exc}")

    return report
