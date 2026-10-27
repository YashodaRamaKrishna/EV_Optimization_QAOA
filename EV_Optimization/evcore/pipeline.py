"""Full Optimization Pipeline for EV Charger Siting & Scheduling.

Implements the required pipeline:
    Problem Instance
        ↓
    QUBO Construction
        ↓
    Binary QUBO
        ↓
    Selected Solver(s): SA (Classical) / QAOA (Quantum) / Exact (Validation)
        ↓
    Best Binary Solution
        ↓
    Decoder (Same Decoder for all solvers)
        ↓
    Feasibility Validation (Same Validation for all solvers)
        ↓
    Objective + Cost Breakdown
        ↓
    Dashboard & Comparison

Evaluates all solvers on the EXACT SAME binary QUBO formulation.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from evcore.qubo import QUBOModel, normalize_instance
from evcore.solver_sa import SimulatedAnnealingSolver
from evcore.exact_solver import ExactEnumerationSolver, calculate_optimality_gap
from evcore.qaoa_solver import QAOASolver, QAOA_DEFAULT_SIMULATION_LIMIT
from evcore.decoder import decode_solution


def run_optimization_pipeline(
    instance: Dict[str, Any],
    solver: str = "classical",
    params: Optional[Dict[str, Any]] = None,
    model: Optional[QUBOModel] = None,
    ground_truth_obj: Optional[float] = None,
) -> Dict[str, Any]:
    """Executes the optimization pipeline for a single solver on the binary QUBO."""
    params = params or {}
    norm_instance = normalize_instance(instance)

    # 1. QUBO Construction -> Binary QUBO (reused if provided)
    if model is None:
        model = QUBOModel(norm_instance)
    n_vars = model.n_vars

    # Ground truth optimum calculation for small instances (N <= 20)
    exact_solver = ExactEnumerationSolver(max_variables=20)
    if ground_truth_obj is None and exact_solver.is_tractable(n_vars):
        try:
            exact_res = exact_solver.solve(model)
            exact_decoded = decode_solution(exact_res["optimum_bitstring"], model)
            ground_truth_obj = exact_decoded["objective"]
        except Exception:
            pass

    # 2. Select Solver and run
    solver_key = solver.lower()
    run_id = f"run-{solver_key}-{uuid.uuid4().hex[:8]}"

    if solver_key in ["classical", "sa", "simulated_annealing", "classical_sa"]:
        # Primary classical solver: Simulated Annealing
        sa_iterations = int(params.get("n_iterations", params.get("iterations", 4000)))
        sa_init_temp = float(params.get("initial_temp", 10.0))
        sa_final_temp = float(params.get("final_temp", 0.01))
        sa_schedule = str(params.get("cooling_schedule", "geometric"))
        sa_restarts = int(params.get("restarts", 8))
        sa_seed = int(params.get("seed", norm_instance.get("seed", 42)))
        sa_time_budget = params.get("runtime_budget_s")
        if sa_time_budget is not None:
            sa_time_budget = float(sa_time_budget)

        sa = SimulatedAnnealingSolver(
            n_iterations=sa_iterations,
            initial_temp=sa_init_temp,
            final_temp=sa_final_temp,
            cooling_schedule=sa_schedule,
            seed=sa_seed,
            restarts=sa_restarts,
            runtime_budget_s=sa_time_budget,
        )
        solve_res = sa.solve(model)

        solver_display = "Simulated Annealing (SA)"
        backend_display = "Classical SA QUBO Engine"
        depth = "N/A"
        two_qubit_gates = "N/A"
        evaluations = solve_res["evaluations"]

        best_bitstring = solve_res.get("best_bitstring")
        decoded = decode_solution(best_bitstring, model)

        if ground_truth_obj is not None:
            gap_val, gap_str = calculate_optimality_gap(decoded["objective"], ground_truth_obj)
            optimality_gap = f"{gap_str} (vs exact {ground_truth_obj:.1f})"
        else:
            optimality_gap = "Exact ground truth not tractable for this instance size"

        return {
            "run_id": run_id,
            "instance_id": norm_instance.get("id", "instance"),
            "solver": solver_display,
            "solver_key": "sa",
            "backend": backend_display,
            "seed": sa_seed,
            "status": "completed",
            "runtime_s": solve_res["runtime_s"],
            "best": decoded,
            "metrics": {
                "optimality_gap": optimality_gap,
                "evaluations": evaluations,
                "restarts": solve_res.get("restarts_performed", 1),
                "qubo_energy": solve_res.get("best_energy"),
                "ground_truth_available": ground_truth_obj is not None,
                "ground_truth_objective": ground_truth_obj,
            },
            "resources": {
                "qubits": n_vars,
                "depth": depth,
                "two_qubit_gates": two_qubit_gates,
            },
            "parameters": {
                "solver": solver_display,
                "iterations": sa_iterations,
                "initial_temp": sa_init_temp,
                "final_temp": sa_final_temp,
                "cooling_schedule": sa_schedule,
                "restarts": sa_restarts,
                "seed": sa_seed,
            },
            "provenance": {
                "source": f"{solver_display} optimization pipeline",
                "is_demo": False,
                "pipeline": "Problem Instance -> QUBO Construction -> Binary QUBO -> SA -> Decoder -> Feasibility Validation -> Costs",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    elif solver_key in ["exact", "exact_enumeration"]:
        # Exact enumeration (small instances only, N <= 20)
        if not exact_solver.is_tractable(n_vars):
            return {
                "run_id": run_id,
                "instance_id": norm_instance.get("id", "instance"),
                "solver": "Exact Enumeration (Ground Truth)",
                "solver_key": "exact",
                "backend": "Classical Exact State Enumeration",
                "status": "unsupported_size",
                "error": f"Instance has {n_vars} variables; exceeds exact enumeration limit of 20.",
                "best": None,
                "metrics": {"evaluations": 0, "optimality_gap": "N/A"},
                "resources": {"qubits": n_vars},
                "provenance": {"is_demo": False, "timestamp": datetime.now(timezone.utc).isoformat()},
            }

        solve_res = exact_solver.solve(model)
        solver_display = "Exact Enumeration (Ground Truth)"
        backend_display = "Classical Exact State Enumeration"
        best_bitstring = solve_res.get("optimum_bitstring")
        decoded = decode_solution(best_bitstring, model)

        return {
            "run_id": run_id,
            "instance_id": norm_instance.get("id", "instance"),
            "solver": solver_display,
            "solver_key": "exact",
            "backend": backend_display,
            "seed": norm_instance.get("seed", 42),
            "status": "completed",
            "runtime_s": solve_res["runtime_s"],
            "best": decoded,
            "metrics": {
                "optimality_gap": "0.0% (ground truth optimum)",
                "evaluations": solve_res["states_evaluated"],
                "qubo_energy": solve_res.get("optimum_energy"),
                "ground_truth_available": True,
                "ground_truth_objective": decoded["objective"],
            },
            "resources": {
                "qubits": n_vars,
                "depth": "N/A",
                "two_qubit_gates": "N/A",
            },
            "provenance": {
                "source": "Exact Enumeration validation",
                "is_demo": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    elif solver_key in ["qaoa", "quantum"]:
        # Quantum / Hybrid QAOA solver
        qaoa_p = int(params.get("p", 1))
        qaoa_shots = int(params.get("shots", 512))
        qaoa_opt = str(params.get("optimizer", "COBYLA"))
        qaoa_max_iter = int(params.get("max_iterations", 25))
        qaoa_seed = int(params.get("seed", norm_instance.get("seed", 42)))
        qaoa_max_qubits = int(params.get("max_sim_qubits", QAOA_DEFAULT_SIMULATION_LIMIT))

        qaoa = QAOASolver(
            p=qaoa_p,
            shots=qaoa_shots,
            optimizer=qaoa_opt,
            max_iterations=qaoa_max_iter,
            seed=qaoa_seed,
            max_sim_qubits=qaoa_max_qubits,
        )
        solve_res = qaoa.solve(model)

        solver_display = "Quantum / Hybrid QAOA"
        backend_display = solve_res.get("backend", "Qiskit Aer Simulator (aer_simulator)")

        if solve_res.get("status") == "unsupported_size":
            return {
                "run_id": run_id,
                "instance_id": norm_instance.get("id", "instance"),
                "solver": solver_display,
                "solver_key": "qaoa",
                "backend": backend_display,
                "seed": qaoa_seed,
                "status": "unsupported_size",
                "reason": solve_res.get("reason"),
                "error": solve_res.get("message"),
                "actual_qubits": n_vars,
                "maximum_simulation_qubits": qaoa_max_qubits,
                "runtime_s": 0.0,
                "best": None,
                "metrics": solve_res.get("metrics", {}),
                "resources": solve_res.get("resources", {}),
                "parameters": solve_res.get("parameters", {}),
                "provenance": {
                    "source": "Qiskit Aer QAOA Pipeline",
                    "is_demo": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        best_bitstring = solve_res.get("best_bitstring")
        decoded = decode_solution(best_bitstring, model)

        if ground_truth_obj is not None:
            gap_val, gap_str = calculate_optimality_gap(decoded["objective"], ground_truth_obj)
            optimality_gap = f"{gap_str} (vs exact {ground_truth_obj:.1f})"
        else:
            optimality_gap = "Exact ground truth not tractable for this instance size"

        return {
            "run_id": run_id,
            "instance_id": norm_instance.get("id", "instance"),
            "solver": solver_display,
            "solver_key": "qaoa",
            "backend": backend_display,
            "seed": qaoa_seed,
            "status": "completed",
            "runtime_s": solve_res["runtime_s"],
            "best": decoded,
            "metrics": {
                **solve_res.get("metrics", {}),
                "optimality_gap": optimality_gap,
                "qubo_energy": solve_res.get("best_energy"),
                "ground_truth_available": ground_truth_obj is not None,
                "ground_truth_objective": ground_truth_obj,
            },
            "resources": solve_res.get("resources", {}),
            "parameters": solve_res.get("parameters", {}),
            "provenance": {
                "source": "Qiskit Aer QAOA Pipeline",
                "is_demo": False,
                "pipeline": "Problem Instance -> QUBO Construction -> Binary QUBO -> QAOA (Qiskit Aer) -> Decoder -> Feasibility Validation -> Costs",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    else:
        raise ValueError(f"Unknown solver: {solver}")


def run_multi_solver_pipeline(
    instance: Dict[str, Any],
    solvers: Optional[List[str]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Runs one or multiple solvers on the EXACT SAME problem instance and SAME QUBO model.

    Supports:
        solvers: list of ['sa', 'qaoa', 'exact'] or variations.
    """
    solvers = solvers or ["sa"]
    params = params or {}
    norm_instance = normalize_instance(instance)

    # 1. Single QUBO Construction used by all methods
    model = QUBOModel(norm_instance)
    n_vars = model.n_vars

    # Ground truth optimum calculation for small instances (N <= 20)
    exact_solver = ExactEnumerationSolver(max_variables=20)
    ground_truth_obj: Optional[float] = None
    if exact_solver.is_tractable(n_vars):
        try:
            exact_res = exact_solver.solve(model)
            exact_decoded = decode_solution(exact_res["optimum_bitstring"], model)
            ground_truth_obj = exact_decoded["objective"]
        except Exception:
            pass

    results_map: Dict[str, Any] = {}
    normalized_keys = []

    for s_name in solvers:
        s_key = s_name.lower().strip()
        if s_key in ["classical", "sa", "simulated_annealing", "classical_sa"]:
            norm_key = "sa"
        elif s_key in ["qaoa", "quantum"]:
            norm_key = "qaoa"
        elif s_key in ["exact", "exact_enumeration"]:
            norm_key = "exact"
        else:
            norm_key = s_key

        if norm_key in results_map:
            continue

        normalized_keys.append(norm_key)
        solver_params = params.get(norm_key, params)
        run_res = run_optimization_pipeline(
            norm_instance,
            solver=norm_key,
            params=solver_params,
            model=model,
            ground_truth_obj=ground_truth_obj,
        )
        results_map[norm_key] = run_res

    # Build comparative summary rows for completed runs
    compare_rows = []
    for k in ["exact", "sa", "qaoa"]:
        if k in results_map and results_map[k].get("status") == "completed":
            r = results_map[k]
            b = r.get("best", {})
            res = r.get("resources", {})
            m = r.get("metrics", {})
            compare_rows.append({
                "solver": r.get("solver"),
                "solver_key": k,
                "objective": b.get("objective"),
                "feasible": b.get("feasible"),
                "electricity_cost": b.get("cost_breakdown", {}).get("electricity"),
                "detour_cost": b.get("cost_breakdown", {}).get("detour"),
                "infrastructure_cost": b.get("cost_breakdown", {}).get("infrastructure"),
                "grid_stress": b.get("cost_breakdown", {}).get("grid_stress"),
                "runtime_s": r.get("runtime_s"),
                "optimality_gap": m.get("optimality_gap"),
                "evaluations": m.get("evaluations"),
                "resources": res,
                "qubits": res.get("qubits", n_vars),
                "depth": res.get("depth", "N/A"),
                "two_qubit_gates": res.get("two_qubit_gates", "N/A"),
                "total_gates": res.get("total_gates", "N/A"),
                "transpiled_depth": res.get("transpiled_depth", "N/A"),
                "shots": m.get("shots", "N/A"),
            })

    has_multi = len(results_map) > 1 or len(compare_rows) > 1

    # Primary representative run for backwards compatibility
    primary_key = "sa" if "sa" in results_map else normalized_keys[0]
    primary_run = results_map.get(primary_key, next(iter(results_map.values())))

    multi_run_id = f"multi-run-{uuid.uuid4().hex[:8]}"

    return {
        **primary_run,
        "run_id": multi_run_id,
        "instance_id": norm_instance.get("id", "instance"),
        "is_multi": has_multi,
        "solvers_requested": normalized_keys,
        "qubo_vars": n_vars,
        "results": results_map,
        "comparison": {
            "has_comparison": len(compare_rows) >= 2,
            "rows": compare_rows,
        },
        "provenance": {
            "source": "Multi-Solver Coupled Optimization",
            "is_demo": False,
            "pipeline": "Same Instance -> Same QUBO -> Selected Solvers -> Same Decoder -> Same Validation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def compare_solvers_for_instance(
    instance: Dict[str, Any],
    sa_params: Optional[Dict[str, Any]] = None,
    qaoa_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Runs Simulated Annealing and QAOA on the exact same QUBO formulation."""
    solvers = ["sa", "qaoa"]
    norm_instance = normalize_instance(instance)
    model = QUBOModel(norm_instance)
    if ExactEnumerationSolver(max_variables=18).is_tractable(model.n_vars):
        solvers.insert(0, "exact")

    multi = run_multi_solver_pipeline(
        instance,
        solvers=solvers,
        params={"sa": sa_params or {}, "qaoa": qaoa_params or {}},
    )

    return {
        "instance_id": norm_instance.get("id", "instance"),
        "rows": multi["comparison"]["rows"],
        "provenance": "Evaluated against common QUBO formulation",
    }
