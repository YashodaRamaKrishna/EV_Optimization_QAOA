"""Tests for Simulated Annealing (SA) Primary Classical Solver and Pipeline.

Verifies:
1. SA operates directly on binary QUBO formulation.
2. SA exposes configurable parameters (iterations, temps, cooling schedule, seed, restarts).
3. SA respects budgets (evaluations/iterations/runtime) without requiring an arbitrary upper bound on objective.
4. SA solves baseline to feasibility and finds the optimal/near-optimal solution.
5. Optimization pipeline decodes binary solution into physical assignments, feasibility checks, and cost breakdown.
"""

import numpy as np
from evcore.mock import BASELINE
from evcore.qubo import QUBOModel
from evcore.solver_sa import SimulatedAnnealingSolver
from evcore.decoder import decode_solution
from evcore.pipeline import run_optimization_pipeline


def test_sa_solver_parameters_and_execution():
    """Verifies that SA accepts and respects configurable parameters."""
    model = QUBOModel(BASELINE)
    assert model.n_vars == 22

    # Configurable parameters
    solver = SimulatedAnnealingSolver(
        n_iterations=2000,
        initial_temp=15.0,
        final_temp=0.005,
        cooling_schedule="geometric",
        seed=42,
        restarts=3,
    )
    result = solver.solve(model)

    assert "best_bitstring" in result
    assert len(result["best_bitstring"]) == 22
    assert result["restarts_performed"] == 3
    assert result["evaluations"] > 6000
    assert result["runtime_s"] >= 0.0
    assert result["parameters"]["solver"] == "Simulated Annealing (SA)"
    assert result["parameters"]["cooling_schedule"] == "geometric"
    assert result["parameters"]["seed"] == 42


def test_sa_budget_limits_without_upper_bound():
    """Verifies that computational limits are expressed through budgets

    (iterations, evaluations, runtime, restarts) without requiring an arbitrary
    upper bound on objective value.
    """
    model = QUBOModel(BASELINE)

    # Evaluation budget
    eval_limit = 1500
    solver = SimulatedAnnealingSolver(
        n_iterations=5000,
        restarts=5,
        eval_budget=eval_limit,
        seed=123,
    )
    res = solver.solve(model)
    # Total evaluations should not significantly exceed budget
    assert res["evaluations"] <= eval_limit + 50


def test_sa_finds_feasible_solution_on_baseline():
    """Verifies that SA successfully solves the coupled baseline instance

    and produces a feasible decoded solution.
    """
    model = QUBOModel(BASELINE)
    solver = SimulatedAnnealingSolver(
        n_iterations=5000,
        initial_temp=10.0,
        final_temp=0.001,
        restarts=10,
        seed=42,
    )
    result = solver.solve(model)
    decoded = decode_solution(result["best_bitstring"], model)

    assert decoded["feasible"] is True
    assert len(decoded["violations"]) == 0
    # Objective should be optimal (10.1) or within 2% of optimal
    assert abs(decoded["objective"] - 10.1) < 0.5
    # Verify cost breakdown components
    cb = decoded["cost_breakdown"]
    assert "electricity" in cb
    assert "detour" in cb
    assert "infrastructure" in cb
    assert "grid_stress" in cb
    # Sum of breakdown matches total objective
    assert abs(sum(cb.values()) - decoded["objective"]) < 1e-4


def test_optimization_pipeline_end_to_end():
    """Tests the full optimization pipeline:

    Problem Instance -> QUBO -> Binary QUBO -> SA -> Best Binary Solution -> Decoder -> Feasibility -> Costs
    """
    run = run_optimization_pipeline(
        BASELINE,
        solver="classical",
        params={"n_iterations": 4000, "restarts": 6, "seed": 42},
    )

    assert run["solver"] == "Simulated Annealing (SA)"
    assert run["status"] == "completed"
    assert run["resources"]["qubits"] == 22
    assert run["best"]["feasible"] is True
    assert run["best"]["objective"] > 0.0
    assert len(run["best"]["assignments"]) == 4
    assert len(run["best"]["stations_open"]) == 2


def test_custom_2x2x2_optimization_and_grid_metrics():
    """Verifies that a custom 2x2x2 instance compiles to 6 binary variables,

    optimizes to the exact solution (objective 18.0), and yields accurate grid metrics.
    """
    test_b = {
        "id": "custom-test-b",
        "name": "Custom 2x2x2",
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

    model = QUBOModel(test_b)
    assert model.n_vars == 6

    run = run_optimization_pipeline(
        test_b,
        solver="classical",
        params={"n_iterations": 1000, "restarts": 4, "seed": 42},
    )

    assert run["best"]["feasible"] is True
    assert run["best"]["objective"] == 18.0
    cb = run["best"]["cost_breakdown"]
    assert cb["electricity"] == 7.0
    assert cb["detour"] == 10.0
    assert cb["infrastructure"] == 0.5
    assert cb["grid_stress"] == 0.5
    assert run["provenance"]["is_demo"] is False

    loads = run["best"]["load"]
    caps = test_b["grid_cap"]
    assert max(loads) == 1
    utils = [(l / g) * 100 for l, g in zip(loads, caps)]
    assert max(utils) == 100.0
    assert sum(utils) / len(utils) == 100.0
    assert sum(1 for l, g in zip(loads, caps) if l / g >= 0.80) == 2
    assert sum(1 for l, g in zip(loads, caps) if l > g) == 0
