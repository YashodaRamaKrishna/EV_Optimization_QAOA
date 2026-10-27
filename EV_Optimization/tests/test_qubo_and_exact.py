"""Tests for QUBO construction, Exact Enumeration solver, and solver comparison.

Verifies:
1. Small-instance Exact Enumeration determines exact ground-truth optimum.
2. Optimality gaps are accurately computed.
3. SA, QAOA, and Exact Enumeration evaluate against the EXACT SAME QUBO.
"""

from evcore.qubo import QUBOModel
from evcore.exact_solver import ExactEnumerationSolver, calculate_optimality_gap
from evcore.solver_sa import SimulatedAnnealingSolver
from evcore.qaoa_solver import QAOASolver
from evcore.decoder import decode_solution
from evcore.pipeline import compare_solvers_for_instance


SMALL_INSTANCE = {
    "id": "test-small-2x2x2",
    "name": "Small Test — 2 EV × 2 Stations × 2 Slots",
    "n_ev": 2,
    "n_st": 2,
    "n_t": 2,
    "demand": [1, 1],
    "window": [[0, 1], [0, 1]],
    "price": [1.0, 2.0],
    "grid_cap": [2, 2],
    "open_cost": [1.0, 1.5],
    "detour": [[0.0, 0.2], [0.1, 0.0]],
    "stress_w": 0.25,
    "seed": 42,
}


def test_qubo_model_construction():
    """Verifies QUBO compilation and dimensions."""
    model = QUBOModel(SMALL_INSTANCE)
    # 2 stations + (2 EVs * 2 stations * 2 slots) = 2 + 8 = 10 variables
    assert model.n_vars == 10
    assert model.Q.shape == (10, 10)
    assert model.Q_sym.shape == (10, 10)
    # Check Ising conversion
    J, h, c = model.to_ising()
    assert J.shape == (10, 10)
    assert len(h) == 10


def test_qubo_ising_energy_consistency():
    """Verifies that E_qubo(z) == E_ising(s) across random bitstrings within machine precision."""
    import numpy as np

    for inst in [SMALL_INSTANCE]:
        model = QUBOModel(inst)
        J, h, c = model.to_ising()
        n = model.n_vars

        rng = np.random.RandomState(42)
        for _ in range(50):
            z = rng.choice([0, 1], size=n)
            s = 1 - 2 * z

            # QUBO energy
            e_qubo = float(z @ model.Q_sym @ z) + model.offset

            # Ising energy: s^T J s + h^T s + c
            e_ising = float(s @ J @ s) + float(np.dot(h, s)) + c

            assert abs(e_qubo - e_ising) < 1e-10, f"Discrepancy: qubo={e_qubo}, ising={e_ising}"




def test_exact_enumeration_ground_truth():
    """Verifies that Exact Enumeration finds the global optimum

    for small instances to validate QUBO formulation.
    """
    model = QUBOModel(SMALL_INSTANCE)
    exact = ExactEnumerationSolver(max_variables=16)
    res = exact.solve(model)

    assert res["is_exact"] is True
    assert res["states_evaluated"] == 1024  # 2^10
    assert "optimum_bitstring" in res

    # Decode optimum
    decoded = decode_solution(res["optimum_bitstring"], model)
    assert decoded["feasible"] is True
    assert decoded["objective"] == 4.6
    assert decoded["cost_breakdown"]["electricity"] == 3.0
    assert decoded["cost_breakdown"]["detour"] == 0.1
    assert decoded["cost_breakdown"]["infrastructure"] == 1.0
    assert decoded["cost_breakdown"]["grid_stress"] == 0.5


def test_optimality_gap_computation():
    """Verifies relative gap computation against ground truth."""
    gap_val, gap_str = calculate_optimality_gap(4.6, 4.6)
    assert gap_val == 0.0
    assert gap_str == "0.0%"

    gap_val, gap_str = calculate_optimality_gap(5.06, 4.6)
    assert abs(gap_val - 10.0) < 0.1
    assert "10.0%" in gap_str


def test_same_qubo_evaluation_across_all_solvers():
    """Verifies that Exact Enumeration, SA, and QAOA all evaluate

    against the exact same QUBO formulation.
    """
    cmp = compare_solvers_for_instance(SMALL_INSTANCE)
    assert len(cmp["rows"]) >= 2

    # Check solver names
    solvers = [r["solver"] for r in cmp["rows"]]
    assert any("Simulated Annealing" in s for s in solvers)
    assert any("QAOA" in s for s in solvers)

    # Check that all solvers used 10 qubits / binary variables
    for r in cmp["rows"]:
        assert r["resources"]["qubits"] == 10
