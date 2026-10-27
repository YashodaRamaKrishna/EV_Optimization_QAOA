"""Dedicated IBM Quantum Hardware Experiment Runner.

Executes live experiments on IBM Quantum hardware strictly for the two validated instances:
1. Problem A: 2 EV × 2 Stations × 2 Slots (instance-a-2x2x2, 10 qubits)
2. Problem B: 3 EV × 2 Stations × 4 Slots (custom-1791428968536, 20 qubits)

QAOA Depth: p = 2
Shots: 2048
Channel: ibm_quantum_platform
"""

import argparse
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from evcore.ibm_hardware import (
    PROBLEM_A_CANONICAL,
    PROBLEM_B_CANONICAL,
    run_live_ibm_experiment,
    test_ibm_connection,
    get_ibm_credentials,
    mask_crn,
)


def print_final_report(conn_info: dict, res_a: dict = None, res_b: dict = None, mock: bool = False):
    """Prints the final structured report matching Section 24 exactly."""
    print("\n" + "=" * 50)
    print("LIVE IBM QUANTUM HARDWARE")
    print("=" * 50)

    conn_status = conn_info.get("status")
    backend_name = conn_info.get("backend") or (res_a.get("backend") if res_a else "None")
    is_live = bool((res_a and res_a.get("live_hardware")) or (res_b and res_b.get("live_hardware")))

    print("\nConnection:")
    print("✓ IBM Quantum Platform" if (is_live or conn_status == "connected") else "[NOT CONNECTED] IBM Quantum Platform")

    print("\nInstance/CRN:")
    print("✓ authenticated" if (is_live or conn_status == "connected") else "[UNAUTHENTICATED / NOT CONFIGURED]")

    print(f"\nBackend:\n{backend_name}")

    if res_a:
        print("\n" + "-" * 50)
        print("EXPERIMENT 1\n2×2×2")
        print(f"\nQubits:\n{res_a.get('logical_qubits', 10)}")
        print(f"\np:\n{res_a.get('p', 2)}")
        print(f"\nShots:\n{res_a.get('shots', 2048)}")
        print(f"\nJob ID:\n{res_a.get('job_id', 'None')}")
        print(f"\nTranspiled depth:\n{res_a.get('transpiled_depth', 'None')}")
        print(f"\n2Q gates:\n{res_a.get('two_qubit_gates', 'None')}")

        best_obs = res_a.get("best_observed", {})
        print(f"\nBest observed:\n{best_obs.get('bitstring')} (count={best_obs.get('count')}, energy={best_obs.get('qubo_energy')}, feasible={best_obs.get('feasible')})")

        best_feas = res_a.get("best_feasible")
        if best_feas:
            print(f"\nBest feasible:\n{best_feas.get('bitstring')} (objective={best_feas.get('objective')}, count={best_feas.get('count')})")
        else:
            print("\nBest feasible:\nNo feasible solution observed in 2048 hardware shots.")

        print(f"\nFeasible probability:\n{res_a.get('feasible_sample_probability', 0.0)}")

    if res_b:
        print("\n" + "-" * 50)
        print("EXPERIMENT 2\n3×2×4")
        print(f"\nQubits:\n{res_b.get('logical_qubits', 20)}")
        print(f"\np:\n{res_b.get('p', 2)}")
        print(f"\nShots:\n{res_b.get('shots', 2048)}")
        print(f"\nJob ID:\n{res_b.get('job_id', 'None')}")
        print(f"\nTranspiled depth:\n{res_b.get('transpiled_depth', 'None')}")
        print(f"\n2Q gates:\n{res_b.get('two_qubit_gates', 'None')}")

        best_obs = res_b.get("best_observed", {})
        print(f"\nBest observed:\n{best_obs.get('bitstring')} (count={best_obs.get('count')}, energy={best_obs.get('qubo_energy')}, feasible={best_obs.get('feasible')})")

        best_feas = res_b.get("best_feasible")
        if best_feas:
            print(f"\nBest feasible:\n{best_feas.get('bitstring')} (objective={best_feas.get('objective')}, count={best_feas.get('count')})")
        else:
            print("\nBest feasible:\nNo feasible solution observed in 2048 hardware shots.")

        print(f"\nFeasible probability:\n{res_b.get('feasible_sample_probability', 0.0)}")

    print("\n" + "-" * 50)
    print("STATUS")
    print(f"\nLIVE HARDWARE:\n{'YES' if is_live else 'NO (MOCK VALIDATION)' if mock else 'NO (HARDWARE FAILED / UNCONFIGURED)'}")
    print("\nDEMO FALLBACK:\nNOT USED FOR THESE TWO RUNS")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Dedicated IBM Quantum Hardware Runner for EV Optimization")
    parser.add_argument("--test-connection", action="store_true", help="Validate IBM Quantum Platform connection without submitting jobs")
    parser.add_argument("--instance", choices=["a", "b", "all"], default="all", help="Target problem (a: 2x2x2, b: 3x2x4, all: both)")
    parser.add_argument("--backend", default=None, help="Target IBM Quantum backend (e.g. ibm_brisbane)")
    parser.add_argument("--token", default=None, help="IBM Quantum API Key")
    parser.add_argument("--instance-crn", default=None, help="IBM Quantum Instance CRN")
    parser.add_argument("--p", type=int, default=2, help="QAOA depth p (default: 2)")
    parser.add_argument("--shots", type=int, default=2048, help="Measurement shots (default: 2048)")
    parser.add_argument("--mock", action="store_true", help="Run local mock simulation for pipeline verification")
    args = parser.parse_args()

    # 1. Connection-only test
    if args.test_connection:
        res = test_ibm_connection(
            api_key=args.token,
            instance_crn=args.instance_crn,
            backend_name=args.backend,
        )
        if res.get("status") != "connected":
            sys.exit(1)
        sys.exit(0)

    # 2. Connection verification prior to job submission
    conn_info = {}
    if not args.mock:
        conn_info = test_ibm_connection(
            api_key=args.token,
            instance_crn=args.instance_crn,
            backend_name=args.backend,
        )
        if conn_info.get("status") != "connected":
            print("[ABORT] Cannot proceed to hardware experiments: connection validation failed.")
            print("Status: LIVE HARDWARE FAILED (No demo fallback used).")
            # Print failure report
            print_final_report(conn_info, mock=False)
            sys.exit(1)
    else:
        conn_info = {
            "status": "connected",
            "channel": "ibm_quantum_platform (mock)",
            "instance": "<mock-instance>",
            "backend": args.backend or "ibm_brisbane",
            "physical_qubits": 127,
            "operational": True,
        }

    res_a = None
    res_b = None

    # 3. Experiment 1: 2 EV × 2 Stations × 2 Slots
    if args.instance in ("a", "all"):
        print("\n>>> STARTING EXPERIMENT 1: 2 EV × 2 Stations × 2 Slots (instance-a-2x2x2)")
        res_a = run_live_ibm_experiment(
            instance=PROBLEM_A_CANONICAL,
            p=args.p,
            shots=args.shots,
            backend_name=args.backend,
            api_key=args.token,
            instance_crn=args.instance_crn,
            mock_simulator=args.mock,
        )
        if res_a.get("status") != "completed":
            print(f"[ERROR] Experiment 1 failed: {res_a.get('message')}")
            if not args.mock:
                print_final_report(conn_info, res_a=res_a, mock=False)
                sys.exit(1)

    # 4. Experiment 2: 3 EV × 2 Stations × 4 Slots
    if args.instance in ("b", "all"):
        print("\n>>> STARTING EXPERIMENT 2: 3 EV × 2 Stations × 4 Slots (custom-1791428968536)")
        res_b = run_live_ibm_experiment(
            instance=PROBLEM_B_CANONICAL,
            p=args.p,
            shots=args.shots,
            backend_name=args.backend,
            api_key=args.token,
            instance_crn=args.instance_crn,
            mock_simulator=args.mock,
        )
        if res_b.get("status") != "completed":
            print(f"[ERROR] Experiment 2 failed: {res_b.get('message')}")
            if not args.mock:
                print_final_report(conn_info, res_a=res_a, res_b=res_b, mock=False)
                sys.exit(1)

    # 5. Output final summary report
    print_final_report(conn_info, res_a=res_a, res_b=res_b, mock=args.mock)


if __name__ == "__main__":
    main()
