"""Runs all test suites for the EV Coupled Optimization project."""

import sys
import unittest
import tests.test_api as test_api
import tests.test_classical_sa as test_sa
import tests.test_qubo_and_exact as test_qubo
import tests.test_qaoa as test_qaoa
import tests.test_scaling_and_estimate as test_scaling


def run_all():
    print("=" * 60)
    print("RUNNING ALL AUTOMATED TEST SUITES")
    print("=" * 60)

    try:
        print("\n[1/4] Testing Flask API Endpoints (tests/test_api.py)...")
        test_api.test_health_and_baseline()
        print("  [OK] test_health_and_baseline passed")
        test_api.test_custom_instance_is_stored_with_detour_matrix()
        print("  [OK] test_custom_instance_is_stored_with_detour_matrix passed")
        test_api.test_create_run_simulated_annealing()
        print("  [OK] test_create_run_simulated_annealing passed")
        test_api.test_compare_endpoint()
        print("  [OK] test_compare_endpoint passed")
        test_api.test_custom_2x2x2_api_workflow()
        print("  [OK] test_custom_2x2x2_api_workflow passed")
        test_api.test_bounded_problem_limits_rejected()
        print("  [OK] test_bounded_problem_limits_rejected passed")
        test_api.test_multi_solver_api_execution()
        print("  [OK] test_multi_solver_api_execution passed")
        test_api.test_qaoa_only_api_execution()
        print("  [OK] test_qaoa_only_api_execution passed")
        test_api.test_unknown_instance_returns_404()
        print("  [OK] test_unknown_instance_returns_404 passed")
        test_api.test_presets_registration_and_small_instance_isolation()
        print("  [OK] test_presets_registration_and_small_instance_isolation passed")
        test_api.test_baseline_endpoint_has_instance_id()
        print("  [OK] test_baseline_endpoint_has_instance_id passed")
        test_api.test_custom_instance_persistence_and_deletion()
        print("  [OK] test_custom_instance_persistence_and_deletion passed")
        test_api.test_builtin_presets_cannot_be_deleted()
        print("  [OK] test_builtin_presets_cannot_be_deleted passed")
        test_api.test_human_readable_violation_numbering()
        print("  [OK] test_human_readable_violation_numbering passed")

        print("\n[2/4] Testing Simulated Annealing Solver & Pipeline (tests/test_classical_sa.py)...")
        test_sa.test_sa_solver_parameters_and_execution()
        print("  [OK] test_sa_solver_parameters_and_execution passed")
        test_sa.test_sa_budget_limits_without_upper_bound()
        print("  [OK] test_sa_budget_limits_without_upper_bound passed")
        test_sa.test_sa_finds_feasible_solution_on_baseline()
        print("  [OK] test_sa_finds_feasible_solution_on_baseline passed")
        test_sa.test_optimization_pipeline_end_to_end()
        print("  [OK] test_optimization_pipeline_end_to_end passed")
        test_sa.test_custom_2x2x2_optimization_and_grid_metrics()
        print("  [OK] test_custom_2x2x2_optimization_and_grid_metrics passed")

        print("\n[3/4] Testing QUBO & Small-Instance Exact Enumeration (tests/test_qubo_and_exact.py)...")
        test_qubo.test_qubo_model_construction()
        print("  [OK] test_qubo_model_construction passed")
        test_qubo.test_qubo_ising_energy_consistency()
        print("  [OK] test_qubo_ising_energy_consistency passed")
        test_qubo.test_exact_enumeration_ground_truth()
        print("  [OK] test_exact_enumeration_ground_truth passed")
        test_qubo.test_optimality_gap_computation()
        print("  [OK] test_optimality_gap_computation passed")
        test_qubo.test_same_qubo_evaluation_across_all_solvers()
        print("  [OK] test_same_qubo_evaluation_across_all_solvers passed")

        print("\n[4/4] Testing Qiskit Aer QAOA & Circuit Metrics (tests/test_qaoa.py)...")
        test_qaoa.test_qaoa_solver_execution_and_metrics()
        print("  [OK] test_qaoa_solver_execution_and_metrics passed")
        test_qaoa.test_qaoa_simulation_guard_over_limit()
        print("  [OK] test_qaoa_simulation_guard_over_limit passed")
        test_qaoa.test_cost_hamiltonian_unitary_circuit_equivalence()
        print("  [OK] test_cost_hamiltonian_unitary_circuit_equivalence passed")
        test_qaoa.test_qaoa_computational_basis_bitstring_ordering()
        print("  [OK] test_qaoa_computational_basis_bitstring_ordering passed")

        print("\n[5/5] Testing Scaling & Estimate Resources (tests/test_scaling_and_estimate.py)...")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_scaling.TestScalingAndEstimate)
        runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=1)
        res = runner.run(suite)
        if not res.wasSuccessful():
            raise RuntimeError("Scaling & Estimate Resources tests failed!")

        print("\n" + "=" * 60)
        print("SUCCESS: ALL 32 TESTS PASSED CLEANLY!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\nFAILED with error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all())
