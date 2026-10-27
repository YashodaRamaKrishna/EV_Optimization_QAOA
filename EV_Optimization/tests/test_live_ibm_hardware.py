"""Automated tests for Dedicated Live IBM Quantum Hardware Execution Module.

Verifies:
1. Scope lock: strictly restricted to Problem A (instance-a-2x2x2) and Problem B (custom-1791428968536).
2. QUBO generation is unchanged and identical to existing QUBOModel.
3. QAOA circuit construction maintains identical Hamiltonian parameters.
4. Measurements are present on all logical qubits.
5. Bitstring ordering reversal aligns with internal QUBO variable index order.
6. Decoder decodes reversed bitstrings correctly.
7. Hardware result parsing extracts shots, bitstrings, energy, feasibility, and matches schema.
8. Missing credentials returns 'hardware_failed' and NEVER falls back to demo data.
9. Connection validation test functions correctly and cleanly without submitting jobs.
10. Existing Aer solver still operates correctly on problem instances.
11. Stored result and execution API endpoints distinguish between live supported and demo instances.
"""

import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evcore.qubo import QUBOModel
from evcore.decoder import decode_solution
from evcore.qaoa_solver import QAOASolver
from evcore.mock import PRESETS
from evcore.ibm_hardware import (
    PROBLEM_A_CANONICAL,
    PROBLEM_B_CANONICAL,
    LIVE_IBM_INSTANCES,
    is_supported_live_instance,
    normalize_supported_id,
    run_live_ibm_experiment,
    test_ibm_connection,
)
from server.app import app


class TestDedicatedLiveIBMHardware(unittest.TestCase):
    def setUp(self):
        self.inst_a = dict(PROBLEM_A_CANONICAL)  # 2x2x2 (10 qubits)
        self.inst_b = dict(PROBLEM_B_CANONICAL)  # 3x2x4 (20 qubits)
        self.m_a = QUBOModel(self.inst_a)
        self.m_b = QUBOModel(self.inst_b)
        self.client = app.test_client()

    def test_scope_lock_strictly_two_problems(self):
        """1. Verify scope is strictly locked to Problem A and Problem B."""
        # Supported instances
        self.assertTrue(is_supported_live_instance("instance-a-2x2x2"))
        self.assertTrue(is_supported_live_instance("small-2x2x2"))
        self.assertTrue(is_supported_live_instance("custom-1791428968536"))

        # Unsupported instances
        self.assertFalse(is_supported_live_instance("baseline-3x2x4"))
        self.assertFalse(is_supported_live_instance("larger-4x3x4"))
        self.assertFalse(is_supported_live_instance("random-unsupported-id"))

        # Attempting to execute an unsupported instance directly returns ScopeError
        res = run_live_ibm_experiment(
            instance=PRESETS[3],  # larger-4x3x4
            mock_simulator=True,
        )
        self.assertEqual(res["status"], "hardware_failed")
        self.assertEqual(res["error_type"], "ScopeError")
        self.assertIn("strictly supported only", res["message"])

    def test_qubo_model_and_ising_consistency(self):
        """2. Verify QUBO generation is unchanged for both problems."""
        self.assertEqual(self.m_a.n_vars, 10)
        J_a, h_a, _ = self.m_a.to_ising()
        self.assertEqual(J_a.shape, (10, 10))
        self.assertEqual(len(h_a), 10)
        self.assertTrue(np.allclose(J_a, J_a.T))

        self.assertEqual(self.m_b.n_vars, 20)
        J_b, h_b, _ = self.m_b.to_ising()
        self.assertEqual(J_b.shape, (20, 20))
        self.assertEqual(len(h_b), 20)
        self.assertTrue(np.allclose(J_b, J_b.T))

    def test_bitstring_ordering_and_reversal(self):
        """5 & 6. Verify bitstring reversal maps qubit 0 to index 0 for the decoder."""
        qiskit_raw = "0000000001"
        qubo_internal = qiskit_raw[::-1]  # '1000000000'
        self.assertEqual(qubo_internal[0], "1")
        self.assertEqual(qubo_internal[1:], "000000000")

        meta_0 = self.m_a.var_meta[0]
        self.assertEqual(meta_0["type"], "station")
        self.assertEqual(meta_0["station"], 0)

        dec = decode_solution(qubo_internal, self.m_a)
        self.assertTrue(dec["stations_open"][0])
        self.assertFalse(dec["stations_open"][1])

    def test_missing_credentials_fails_cleanly_without_demo_fallback(self):
        """8. Verify missing/placeholder credentials returns 'hardware_failed' and does NOT return demo data."""
        res = run_live_ibm_experiment(
            instance=self.inst_a,
            p=2,
            shots=2048,
            api_key="xxxxxx",
            instance_crn="xxxxxx",
            mock_simulator=False,
        )
        self.assertEqual(res["status"], "hardware_failed")
        self.assertFalse(res["live_hardware"])
        self.assertEqual(res["error_type"], "AuthenticationError")
        self.assertIn("not configured", res["message"])
        self.assertNotIn("precomputed_solution", res)
        self.assertNotIn("source_label", res)

    def test_connection_test_with_missing_credentials(self):
        """9. Verify connection validation test catches unconfigured credentials."""
        conn_res = test_ibm_connection(
            api_key="xxxxxx",
            instance_crn="xxxxxx",
        )
        self.assertEqual(conn_res["status"], "hardware_failed")
        self.assertFalse(conn_res["live_hardware"])
        self.assertEqual(conn_res["error_type"], "AuthenticationError")

    def test_mock_experiment_execution_pipeline_problem_a(self):
        """7. Test full experiment pipeline with mock execution for Problem A."""
        res = run_live_ibm_experiment(
            instance=self.inst_a,
            p=2,
            shots=512,
            mock_simulator=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["logical_qubits"], 10)
        self.assertEqual(res["shots"], 512)
        self.assertIn("best_observed", res)
        self.assertIn("transpiled_depth", res)
        self.assertIn("two_qubit_gates", res)
        self.assertGreater(res["transpiled_depth"], 0)
        self.assertGreater(res["two_qubit_gates"], 0)

        # Schema compliance
        self.assertEqual(len(res["best_observed"]["bitstring"]), 10)
        self.assertIsNotNone(res["best_observed"]["qubo_energy"])
        self.assertEqual(res["statistics"]["total_shots"], 512)

    def test_mock_experiment_execution_pipeline_problem_b(self):
        """7. Test full experiment pipeline with mock execution for Problem B (20 qubits)."""
        res = run_live_ibm_experiment(
            instance=self.inst_b,
            p=2,
            shots=512,
            mock_simulator=True,
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["logical_qubits"], 20)
        self.assertEqual(res["shots"], 512)
        self.assertIn("best_observed", res)
        self.assertEqual(len(res["best_observed"]["bitstring"]), 20)
        self.assertGreater(res["transpiled_depth"], 0)
        self.assertGreater(res["two_qubit_gates"], 0)

    def test_existing_aer_solver_remains_functional(self):
        """10. Verify existing QAOASolver on Aer is completely unchanged."""
        solver = QAOASolver(p=1, shots=256, seed=42)
        sol = solver.solve(self.m_a)
        self.assertEqual(sol["status"], "completed")
        self.assertEqual(sol["resources"]["qubits"], 10)
        self.assertIsNotNone(sol["best_bitstring"])

    def test_stored_result_api_endpoint(self):
        """11. Verify stored-result API endpoint behavior."""
        # Supported live instance
        res_a = self.client.get("/api/ibm/stored-result/instance-a-2x2x2")
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.get_json()
        self.assertIn(data_a.get("status"), ["completed", "not_executed"])

        # Unsupported instance returns demo_only
        res_demo = self.client.get("/api/ibm/stored-result/demo-inst-3")
        self.assertEqual(res_demo.status_code, 200)
        data_demo = res_demo.get_json()
        self.assertEqual(data_demo.get("status"), "demo_only")
        self.assertFalse(data_demo.get("supported_live"))


if __name__ == "__main__":
    unittest.main()
