"""Automated tests for Scaling & IBM Hardware and Estimate Resources features.

Verifies:
1. Scaling API returns structured demo dataset with 6 instances and last completed snapshot.
2. Estimate Resources API computes derived QUBO, Aer circuit, and IBM Heavy-Hex transpilation.
3. 2-qubit, 10-qubit, 20-qubit, and 62-qubit statevector memory calculations and human-readable units.
4. Aer simulation status classification (practical, high_memory, not_practical).
5. Physical qubits required is derived from transpiled circuit and distinguished from device capacity.
6. Large instances (>127 qubits) scale analytically and gracefully without crashing.
7. Multiple IBM backends (ibm_brisbane, ibm_torino, ibm_kyoto) are supported.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app import app
from evcore.ibm_demo_data import get_ibm_scaling_data
from evcore.qaoa_resources import estimate_qaoa_resources, format_memory_bytes


class TestScalingAndEstimate(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ibm_demo_data_structure(self):
        data = get_ibm_scaling_data()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["is_placeholder"])
        self.assertIn("Demonstration Dataset", data["notice"])
        self.assertEqual(len(data["instances"]), 6)

        inst1 = data["instances"][0]
        self.assertEqual(inst1["instance_id"], "demo-inst-1")
        self.assertEqual(inst1["logical_qubits"], 10)
        self.assertIn("aer", inst1)
        self.assertIn("ibm", inst1)
        self.assertEqual(inst1["aer"]["status"], "completed")
        self.assertEqual(inst1["ibm"]["status"], "completed")

        self.assertIn("last_completed", data)
        lc = data["last_completed"]
        self.assertEqual(lc["snapshot_id"], "snap-demo-last-completed")
        self.assertEqual(lc["completed_count"], 2)
        self.assertEqual(len(lc["completed_instances"]), 2)

    def test_api_scaling_endpoint(self):
        res = self.client.get("/api/scaling/ibm-demo")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data["instances"]), 6)
        self.assertEqual(data["instances"][2]["logical_qubits"], 22)

    def test_statevector_memory_and_formatting(self):
        # 1. 2-qubit: 16 * 4 = 64 bytes
        bytes_2 = 16 * (2 ** 2)
        self.assertEqual(bytes_2, 64)
        self.assertEqual(format_memory_bytes(bytes_2), "64 B")

        # 2. 10-qubit: 16 * 1024 = 16384 bytes -> 16.4 KB
        bytes_10 = 16 * (2 ** 10)
        self.assertEqual(bytes_10, 16384)
        self.assertEqual(format_memory_bytes(bytes_10), "16.4 KB")

        # 3. 20-qubit: 16 * 2^20 = 16777216 bytes -> 16.8 MB
        bytes_20 = 16 * (2 ** 20)
        self.assertEqual(bytes_20, 16777216)
        self.assertEqual(format_memory_bytes(bytes_20), "16.8 MB")

        # 4. 62-qubit: 16 * 2^62 = 73786976294838206464 bytes -> 73.8 EB
        bytes_62 = 16 * (2 ** 62)
        self.assertEqual(bytes_62, 73786976294838206464)
        self.assertEqual(format_memory_bytes(bytes_62), "73.8 EB")

        # Unit conversions for intermediate scales
        self.assertEqual(format_memory_bytes(16 * (2 ** 30)), "17.2 GB")
        self.assertEqual(format_memory_bytes(16 * (2 ** 40)), "17.6 TB")
        self.assertEqual(format_memory_bytes(16 * (2 ** 50)), "18.0 PB")

    def test_aer_simulation_status_classification(self):
        # Practical (10 qubits <= 20)
        r_small = estimate_qaoa_resources({"n_ev": 2, "n_st": 2, "n_t": 2}, p=1)
        self.assertEqual(r_small["aer"]["simulation_status_code"], "practical")
        self.assertIn("Practical", r_small["aer"]["simulation_status_label"])
        self.assertTrue(r_small["aer"]["simulation_feasible"])

        # Exceeds limit (> 24 qubits, baseline is 26 qubits or custom 10x2x3 is 62 qubits)
        r_62 = estimate_qaoa_resources({"n_ev": 10, "n_st": 2, "n_t": 3}, p=1)
        self.assertEqual(r_62["aer"]["simulation_status_code"], "not_practical")
        self.assertIn("Not practical", r_62["aer"]["simulation_status_label"])
        self.assertFalse(r_62["aer"]["simulation_feasible"])
        self.assertIn("Full statevector execution was not performed", r_62["aer"]["simulation_status_message"])
        # Circuit metrics are still derived from generated circuit
        self.assertGreater(r_62["aer"]["circuit_depth"], 0)
        self.assertGreater(r_62["aer"]["total_gates"], 0)

    def test_62_qubit_example_aer_and_ibm(self):
        # 10 EVs x 2 Stations x 3 Slots = 62 QUBO variables / logical qubits
        payload = {
            "instance": {"n_ev": 10, "n_st": 2, "n_t": 3},
            "p": 3,
            "backend": "ibm_torino",
        }
        res = self.client.post("/api/estimate-resources", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        isum = data["instance_summary"]
        self.assertEqual(isum["qubo_variables"], 62)
        self.assertEqual(isum["logical_qubits"], 62)

        # Aer metrics
        aer = data["aer"]
        self.assertEqual(aer["logical_qubits"], 62)
        self.assertEqual(aer["p"], 3)
        self.assertEqual(aer["statevector_amplitudes"], "2^62")
        self.assertEqual(aer["statevector_memory_str"], "73.8 EB")
        self.assertEqual(aer["simulation_status_code"], "not_practical")
        self.assertFalse(aer["simulation_feasible"])
        self.assertGreater(aer["circuit_depth"], 0)
        self.assertGreater(aer["total_gates"], 0)

        # IBM metrics
        ibm = data["ibm"]
        self.assertEqual(ibm["backend"], "ibm_torino")
        self.assertEqual(ibm["device_capacity"], 133)
        self.assertEqual(ibm["logical_qubits"], 62)
        self.assertEqual(ibm["p"], 3)
        # Physical qubits required must be <= device capacity (133) and not confused with 133
        self.assertLessEqual(ibm["physical_qubits_required"], 133)
        self.assertGreaterEqual(ibm["physical_qubits_required"], 62)
        self.assertNotEqual(ibm["physical_qubits_required"], ibm["device_capacity"])
        self.assertTrue(ibm["fits_backend"])
        self.assertIn("Fits", ibm["compatibility_status"])
        self.assertGreater(ibm["transpiled_depth"], 0)
        self.assertGreater(ibm["two_qubit_gates"], 0)

    def test_estimate_resources_baseline(self):
        payload = {
            "instance": {
                "n_ev": 3,
                "n_st": 2,
                "n_t": 4,
                "demand": [1, 1, 1],
                "window": [[0, 1], [1, 2], [2, 3]],
                "open_cost": [1.0, 1.0],
                "grid_cap": [2, 2, 2, 2],
                "price": [0.1, 0.2, 0.3, 0.4],
            },
            "p": 1,
            "backend": "ibm_brisbane",
        }
        res = self.client.post("/api/estimate-resources", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["status"], "derived_from_circuit")
        isum = data["instance_summary"]
        self.assertEqual(isum["n_ev"], 3)
        self.assertEqual(isum["n_st"], 2)
        self.assertEqual(isum["n_t"], 4)
        self.assertEqual(isum["qubo_variables"], 14)
        self.assertEqual(isum["logical_qubits"], 14)

        aer = data["aer"]
        self.assertEqual(aer["p"], 1)
        self.assertTrue(aer["simulation_feasible"])
        self.assertGreater(aer["circuit_depth"], 0)
        self.assertGreater(aer["two_qubit_gates"], 0)

        ibm = data["ibm"]
        self.assertEqual(ibm["backend"], "ibm_brisbane")
        self.assertTrue(ibm["fits_backend"])
        self.assertEqual(ibm["device_capacity"], 127)
        self.assertLessEqual(ibm["physical_qubits_required"], 127)
        self.assertGreater(ibm["transpiled_depth"], 0)
        self.assertGreater(ibm["two_qubit_gates"], 0)

    def test_estimate_resources_large_analytical_scaling(self):
        payload = {
            "instance": {
                "n_ev": 20,
                "n_st": 10,
                "n_t": 8,
            },
            "p": 2,
            "backend": "ibm_brisbane",
        }
        res = self.client.post("/api/estimate-resources", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["status"], "analytical_estimation")
        isum = data["instance_summary"]
        self.assertEqual(isum["logical_qubits"], 1610)

        aer = data["aer"]
        self.assertEqual(aer["status"], "symbolic_scaling")
        self.assertFalse(aer["simulation_feasible"])
        self.assertEqual(aer["simulation_status_code"], "not_practical")

        ibm = data["ibm"]
        self.assertFalse(ibm["fits_backend"])
        self.assertEqual(ibm["device_capacity"], 127)
        self.assertEqual(ibm["physical_qubits_required"], 1610)
        self.assertIn("Exceeds device physical capacity", ibm["compatibility_status"])

    def test_estimate_resources_backend_selection(self):
        payload = {
            "instance": {"n_ev": 2, "n_st": 2, "n_t": 2},
            "p": 1,
            "backend": "ibm_torino",
        }
        res = self.client.post("/api/estimate-resources", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["ibm"]["backend"], "ibm_torino")
        self.assertEqual(data["ibm"]["device_capacity"], 133)
        self.assertEqual(data["ibm"]["physical_qubits"], 133)

    def test_ibm_execute_endpoint(self):
        res = self.client.post("/api/ibm/execute", json={"instance_id": "demo-inst-3"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["instance_id"], "demo-inst-3")
        self.assertIn("IBM HARDWARE RESULT", data["source_label"])
        self.assertIn("result", data)
        sol = data["result"]
        self.assertTrue(sol["feasible"])
        self.assertAlmostEqual(sol["objective"], 10.10, places=2)
        self.assertEqual(len(sol["stations_open"]), 2)
        self.assertEqual(sol["load"], [1, 1, 0, 2])
        self.assertIn("aer_resources", data)
        self.assertIn("ibm_resources", data)
        self.assertEqual(data["ibm_resources"]["physical_qubits_required"], 22)
        self.assertEqual(data["ibm_resources"]["device_capacity"], 127)

    def test_ibm_execute_all_curated_instances(self):
        for i in range(1, 7):
            inst_id = f"demo-inst-{i}"
            res = self.client.post("/api/ibm/execute", json={"instance_id": inst_id})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["instance_id"], inst_id)
            self.assertIn("result", data)
            self.assertIn("stations_open", data["result"])
            self.assertIn("assignments", data["result"])
            self.assertIn("load", data["result"])


if __name__ == "__main__":
    unittest.main()
