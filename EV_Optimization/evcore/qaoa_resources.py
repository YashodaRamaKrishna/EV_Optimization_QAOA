"""Quantum Resource Estimator for EV Charging QAOA Circuits.

Uses the EXACT EXISTING problem definition -> QUBO -> Ising -> QAOA circuit pipeline.
Analyzes circuit scaling and hardware transpilation WITHOUT running optimization
or full parameter search loops.
"""

from typing import Any, Dict, Optional
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

from evcore.qubo import QUBOModel, normalize_instance

MAX_CIRCUIT_SYNTHESIS_QUBITS = 127

BACKEND_CONFIGS = {
    "ibm_brisbane": {
        "name": "ibm_brisbane",
        "label": "IBM Brisbane — 127 qubits",
        "physical_qubits": 127,
        "family": "Eagle r3",
        "distance": 7,
        "basis_gates": ["rz", "sx", "x", "cx"],
    },
    "ibm_kyoto": {
        "name": "ibm_kyoto",
        "label": "IBM Kyoto — 127 qubits",
        "physical_qubits": 127,
        "family": "Eagle r3",
        "distance": 7,
        "basis_gates": ["rz", "sx", "x", "cx"],
    },
    "ibm_sherbrooke": {
        "name": "ibm_sherbrooke",
        "label": "IBM Sherbrooke — 127 qubits",
        "physical_qubits": 127,
        "family": "Eagle r3",
        "distance": 7,
        "basis_gates": ["rz", "sx", "x", "cx"],
    },
    "ibm_torino": {
        "name": "ibm_torino",
        "label": "IBM Torino — 133 qubits",
        "physical_qubits": 133,
        "family": "Heron",
        "distance": 7,
        "basis_gates": ["rz", "sx", "x", "cx"],
    },
}


def format_memory_bytes(byte_count: int) -> str:
    """Formats raw byte count into human-readable B, KB, MB, GB, TB, PB, EB."""
    if byte_count < 1000:
        return f"{byte_count} B"
    units = ["KB", "MB", "GB", "TB", "PB", "EB"]
    if byte_count >= 10**18:
        if byte_count.bit_length() > 900:
            return "> 10^100 EB (Astronomical)"
        try:
            val_eb = float(byte_count) / 1e18
            return f"{val_eb:.1f} EB"
        except OverflowError:
            return "> 10^100 EB (Astronomical)"
    val = float(byte_count)
    for i, unit in enumerate(units):
        val /= 1000.0
        if val < 1000.0 or i == len(units) - 1:
            return f"{val:.1f} {unit}"
    return f"{val:.1f} EB"


def estimate_qaoa_resources(
    instance_dict: Dict[str, Any],
    p: int = 1,
    backend_name: str = "ibm_brisbane",
) -> Dict[str, Any]:
    """Computes exact derived and transpiled quantum resource requirements for an EV problem.

    Does NOT run classical SA or Exact optimization.
    Does NOT execute classical parameter optimization loops.
    """
    p_layers = max(1, min(5, int(p)))
    norm = normalize_instance(instance_dict)
    model = QUBOModel(norm)
    n_vars = model.n_vars
    J, h, c_ising = model.to_ising()

    two_q_terms = int(np.count_nonzero(np.triu(np.abs(J) > 1e-6, k=1)))
    one_q_terms = int(np.count_nonzero(np.abs(h) > 1e-6))
    hamiltonian_terms = 1 + one_q_terms + two_q_terms

    b_cfg = BACKEND_CONFIGS.get(backend_name, BACKEND_CONFIGS["ibm_brisbane"])
    phys_qubits = b_cfg["physical_qubits"]

    # Raw double-precision complex statevector memory (16 bytes per amplitude)
    raw_statevector_bytes = 16 * (2 ** n_vars)
    statevector_mem_str = format_memory_bytes(raw_statevector_bytes)
    if n_vars <= 24:
        amplitudes_str = f"2^{n_vars} ({2**n_vars:,})"
    else:
        amplitudes_str = f"2^{n_vars}"

    # Aer simulation feasibility rules
    aer_sim_feasible = n_vars <= 24
    if n_vars <= 20:
        aer_sim_status_code = "practical"
        aer_sim_status_label = "✓ Practical"
        aer_sim_status_msg = "Statevector simulation feasible within standard desktop RAM (< 17 MB)."
        aer_runtime_est = "Benchmark estimate: < 0.5 s"
    elif n_vars <= 24:
        aer_sim_status_code = "high_memory"
        aer_sim_status_label = "⚠ High-memory simulation"
        aer_sim_status_msg = "Simulation feasible on Qiskit Aer (requires ~1 to 16 GB RAM)."
        aer_runtime_est = "Benchmark estimate: ~1 to 4 s"
    else:
        aer_sim_status_code = "not_practical"
        aer_sim_status_label = "✕ Not practical"
        aer_sim_status_msg = (
            f"Exceeds configured Aer statevector limit ({n_vars} qubits > 24 limit). "
            "Circuit resources were derived successfully. Full statevector execution was not performed."
        )
        aer_runtime_est = "Statevector simulation intractable on classical hardware (> 10^6 s)"

    aer_status_msg = (
        f"✓ Simulation feasible on Qiskit Aer ({n_vars} qubits ≤ 24 limit)"
        if aer_sim_feasible
        else f"✕ Aer statevector simulation infeasible ({n_vars} qubits > 24 limit). Circuit metrics derived exactly."
    )

    fits_ibm = n_vars <= phys_qubits

    # If problem exceeds circuit synthesis limit, return clean analytical report
    if n_vars > MAX_CIRCUIT_SYNTHESIS_QUBITS:
        return {
            "status": "analytical_estimation",
            "instance_summary": {
                "n_ev": norm["n_ev"],
                "n_st": norm["n_st"],
                "n_t": norm["n_t"],
                "qubo_variables": n_vars,
                "logical_qubits": n_vars,
                "offset": round(float(model.offset), 4),
                "hamiltonian_terms": hamiltonian_terms,
                "one_qubit_terms": one_q_terms,
                "two_qubit_terms": two_q_terms,
            },
            "aer": {
                "status": "symbolic_scaling",
                "logical_qubits": n_vars,
                "hamiltonian_terms": hamiltonian_terms,
                "p": p_layers,
                "circuit_depth": "Exceeds synthesis limit",
                "total_gates": f"~{n_vars + p_layers * (two_q_terms + one_q_terms + n_vars)} (analytical)",
                "two_qubit_gates": f"{p_layers * two_q_terms} (analytical)",
                "transpiled_depth": "N/A",
                "transpiled_cx": f"~{2 * p_layers * two_q_terms} (analytical)",
                "statevector_amplitudes": amplitudes_str,
                "statevector_memory_bytes": raw_statevector_bytes,
                "statevector_memory_str": statevector_mem_str,
                "simulation_feasible": False,
                "simulation_status_code": aer_sim_status_code,
                "simulation_status_label": aer_sim_status_label,
                "simulation_status_message": aer_sim_status_msg,
                "status_message": f"Circuit construction exceeds configured estimation limit of {MAX_CIRCUIT_SYNTHESIS_QUBITS} qubits.",
                "estimated_runtime": aer_runtime_est,
                "note": "Estimated memory required for the raw double-precision statevector (16 bytes per amplitude). Actual system RAM requirements may be higher due to simulator/runtime overhead.",
            },
            "ibm": {
                "backend": b_cfg["name"],
                "label": b_cfg["label"],
                "architecture": f"{phys_qubits}-Qubit Heavy-Hex",
                "physical_qubits": phys_qubits,
                "device_capacity": phys_qubits,
                "physical_qubits_required": n_vars,
                "logical_qubits": n_vars,
                "p": p_layers,
                "fits_backend": False,
                "transpiled_depth": "N/A",
                "total_gates": "N/A",
                "two_qubit_gates": "N/A",
                "routing_overhead": "N/A",
                "compatibility_status": f"✕ Exceeds device physical capacity ({n_vars} logical qubits > {phys_qubits} physical qubits)",
                "note": "The QAOA circuit will be transpiled for this particular IBM Quantum device to estimate hardware-specific resources.",
            },
            "classification": _get_classification_metadata(),
        }

    # Construct actual QAOA ansatz circuit for configured p
    qc = QuantumCircuit(n_vars)
    qc.h(range(n_vars))
    for _ in range(p_layers):
        # Cost Hamiltonian unitary
        for i in range(n_vars):
            for j in range(i + 1, n_vars):
                if abs(J[i, j]) > 1e-6:
                    qc.rzz(1.0, i, j)
            if abs(h[i]) > 1e-6:
                qc.rz(1.0, i)
        # Mixer unitary
        for i in range(n_vars):
            qc.rx(1.0, i)

    logical_depth = qc.depth()
    logical_gates = sum(qc.count_ops().values())
    logical_2q = qc.count_ops().get("rzz", 0)

    # Transpile for ideal Aer (all-to-all connectivity, basis ["u", "cx"])
    try:
        t_aer = transpile(qc, basis_gates=["u", "cx"], optimization_level=1)
        aer_depth = t_aer.depth()
        aer_cx = t_aer.count_ops().get("cx", 0)
    except Exception:
        aer_depth = logical_depth
        aer_cx = 2 * logical_2q

    # Hardware transpilation on target IBM Heavy-Hex topology
    try:
        cm = CouplingMap.from_heavy_hex(distance=b_cfg["distance"])
        if fits_ibm and n_vars <= cm.size():
            t_ibm = transpile(
                qc,
                coupling_map=cm,
                basis_gates=b_cfg["basis_gates"],
                optimization_level=1,
            )
            ibm_depth = t_ibm.depth()
            ibm_tot = sum(t_ibm.count_ops().values())
            ibm_cx = t_ibm.count_ops().get("cx", 0)
            overhead = round(ibm_cx / max(1, logical_2q), 2)
            overhead_str = f"{overhead}x"
            active_qubits = {t_ibm.find_bit(q).index for inst in t_ibm.data for q in inst.qubits}
            phys_required = len(active_qubits) if active_qubits else n_vars
            compat_str = f"✓ Fits ({phys_required} of {phys_qubits} physical qubits)"
        else:
            ibm_depth = "N/A"
            ibm_tot = "N/A"
            ibm_cx = "N/A"
            overhead_str = "N/A"
            phys_required = n_vars
            compat_str = f"✕ Exceeds device physical capacity ({n_vars} logical qubits > {phys_qubits} physical qubits)"
    except Exception as exc:
        ibm_depth = "N/A"
        ibm_tot = "N/A"
        ibm_cx = "N/A"
        overhead_str = "N/A"
        phys_required = n_vars
        compat_str = f"Transpilation warning: {str(exc)}"

    return {
        "status": "derived_from_circuit",
        "instance_summary": {
            "n_ev": norm["n_ev"],
            "n_st": norm["n_st"],
            "n_t": norm["n_t"],
            "qubo_variables": n_vars,
            "logical_qubits": n_vars,
            "offset": round(float(model.offset), 4),
            "hamiltonian_terms": hamiltonian_terms,
            "one_qubit_terms": one_q_terms,
            "two_qubit_terms": two_q_terms,
        },
        "aer": {
            "status": "derived_from_circuit",
            "logical_qubits": n_vars,
            "hamiltonian_terms": hamiltonian_terms,
            "p": p_layers,
            "circuit_depth": logical_depth,
            "total_gates": logical_gates,
            "two_qubit_gates": logical_2q,
            "transpiled_depth": aer_depth,
            "transpiled_cx": aer_cx,
            "statevector_amplitudes": amplitudes_str,
            "statevector_memory_bytes": raw_statevector_bytes,
            "statevector_memory_str": statevector_mem_str,
            "simulation_feasible": aer_sim_feasible,
            "simulation_status_code": aer_sim_status_code,
            "simulation_status_label": aer_sim_status_label,
            "simulation_status_message": aer_sim_status_msg,
            "status_message": aer_status_msg,
            "estimated_runtime": aer_runtime_est,
            "note": "Estimated memory required for the raw double-precision statevector (16 bytes per amplitude). Actual system RAM requirements may be higher due to simulator/runtime overhead.",
        },
        "ibm": {
            "backend": b_cfg["name"],
            "label": b_cfg["label"],
            "architecture": f"{phys_qubits}-Qubit Heavy-Hex",
            "physical_qubits": phys_qubits,
            "device_capacity": phys_qubits,
            "physical_qubits_required": phys_required,
            "logical_qubits": n_vars,
            "p": p_layers,
            "fits_backend": fits_ibm,
            "transpiled_depth": ibm_depth,
            "total_gates": ibm_tot,
            "two_qubit_gates": ibm_cx,
            "routing_overhead": overhead_str,
            "compatibility_status": compat_str,
            "note": "The QAOA circuit will be transpiled for this particular IBM Quantum device to estimate hardware-specific resources.",
        },
        "classification": _get_classification_metadata(),
    }


def _get_classification_metadata() -> Dict[str, Any]:
    return {
        "derived_computed": [
            "QUBO Variables",
            "Logical Qubits",
            "Hamiltonian Terms",
            "Circuit Depth",
            "Total Gates",
            "2-Qubit Gates",
        ],
        "transpiler_derived": [
            "Physical Qubits Required",
            "Device Physical Qubit Capacity",
            "Transpiled Circuit Depth",
            "Transpiled Total Gates",
            "Transpiled 2-Qubit Gates (CX)",
            "Routing Overhead",
        ],
        "actual_hardware_measured": [
            "Actual Execution Runtime",
            "Measured Output Distribution",
            "Measured Objective",
            "Feasibility Probability",
            "Empirical Optimality Gap",
        ],
        "note": "Hardware execution measurements pending physical runs on IBM Quantum hardware.",
    }
