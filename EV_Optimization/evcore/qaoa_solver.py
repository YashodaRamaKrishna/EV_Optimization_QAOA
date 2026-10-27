"""Quantum / Hybrid QAOA Solver on Binary QUBO.

Operates on the EXACT SAME binary QUBO / Ising formulation as
Simulated Annealing and Exact Enumeration.

Evaluates QAOA through genuine Qiskit Aer circuit simulation.
Does not assume quantum advantage.
"""

from typing import Any, Dict, Optional, Tuple, Union
import time
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from scipy.optimize import minimize

from evcore.qubo import QUBOModel

QAOA_DEFAULT_SIMULATION_LIMIT = 24


class QAOASolver:
    """Quantum Approximate Optimization Algorithm (QAOA) solver for binary QUBOs.

    Evaluates parameterized ansatz circuits on Qiskit Aer against the identical
    binary QUBO / Ising Hamiltonian model.
    """

    def __init__(
        self,
        p: int = 1,
        shots: int = 512,
        optimizer: str = "COBYLA",
        max_iterations: int = 25,
        restarts: int = 1,
        seed: Optional[int] = 42,
        max_sim_qubits: int = QAOA_DEFAULT_SIMULATION_LIMIT,
    ):
        """Parameters:

        p: Number of QAOA alternating operator layers (circuit depth).
        shots: Number of measurement shots.
        optimizer: Classical parameter optimizer ('COBYLA' or 'SPSA').
        max_iterations: Maximum optimizer iterations.
        restarts: Classical parameter restarts.
        seed: Random seed.
        max_sim_qubits: Maximum logical qubits for Qiskit Aer simulation.
        """
        self.p = max(1, int(p))
        self.shots = max(64, int(shots))
        self.optimizer = optimizer if optimizer in ["COBYLA", "SPSA"] else "COBYLA"
        self.max_iterations = max(5, int(max_iterations))
        self.restarts = max(1, int(restarts))
        self.seed = seed
        self.max_sim_qubits = max_sim_qubits

    def solve(
        self,
        model_or_Q: Union[QUBOModel, np.ndarray],
        offset: float = 0.0,
    ) -> Dict[str, Any]:
        """Solves the QUBO using QAOA on the exact same formulation.

        Enforces the configured simulation limit. If n_vars > max_sim_qubits,
        cleanly returns structured unsupported_size status without simulating.
        """
        start_time = time.time()

        if isinstance(model_or_Q, QUBOModel) or (hasattr(model_or_Q, "Q_sym") and hasattr(model_or_Q, "to_ising")):
            model = model_or_Q
            Q_sym = model.Q_sym
            off = getattr(model, "offset", 0.0)
            n_vars = getattr(model, "n_vars", Q_sym.shape[0])
            J, h, c_ising = model.to_ising()
        else:
            Q = np.asarray(model_or_Q, dtype=float)
            Q_sym = 0.5 * (Q + Q.T)
            off = float(offset)
            n_vars = Q_sym.shape[0]
            J, h, c_ising = self._qubo_to_ising(Q_sym, off)

        two_qubit_terms = int(np.count_nonzero(np.triu(np.abs(J) > 1e-6, k=1)))
        one_qubit_terms = int(np.count_nonzero(np.abs(h) > 1e-6))
        total_hamiltonian_terms = 1 + one_qubit_terms + two_qubit_terms

        # -------------------------------------------------------------
        # QAOA Simulation Guard
        # -------------------------------------------------------------
        if n_vars > self.max_sim_qubits:
            return {
                "status": "unsupported_size",
                "solver": "Quantum / Hybrid QAOA",
                "backend": "Qiskit Aer Simulator (aer_simulator)",
                "reason": "QAOA Aer simulation limit exceeded",
                "actual_qubits": n_vars,
                "maximum_simulation_qubits": self.max_sim_qubits,
                "message": (
                    f"QAOA simulation unavailable for this instance. The problem produces "
                    f"{n_vars} logical qubits, exceeding the configured Qiskit Aer simulation "
                    f"limit of {self.max_sim_qubits} qubits."
                ),
                "runtime_s": 0.0,
                "metrics": {
                    "p": self.p,
                    "shots": self.shots,
                    "optimizer": self.optimizer,
                    "evaluations": 0,
                },
                "resources": {
                    "qubits": n_vars,
                    "depth": "N/A",
                    "transpiled_depth": "N/A",
                    "total_gates": "N/A",
                    "two_qubit_gates": "N/A",
                    "hamiltonian_terms": total_hamiltonian_terms,
                    "is_estimated": True,
                },
                "parameters": {
                    "solver": "Quantum / Hybrid QAOA",
                    "p": self.p,
                    "shots": self.shots,
                    "optimizer": self.optimizer,
                    "seed": self.seed,
                },
            }

        # -------------------------------------------------------------
        # Circuit Construction
        # -------------------------------------------------------------
        def build_circuit(gammas: np.ndarray, betas: np.ndarray) -> QuantumCircuit:
            qc = QuantumCircuit(n_vars)
            qc.h(range(n_vars))
            for l in range(self.p):
                gamma_l = gammas[l]
                beta_l = betas[l]
                # Cost Hamiltonian unitary e^{-i \gamma H_C}
                for i in range(n_vars):
                    for j in range(i + 1, n_vars):
                        if abs(J[i, j]) > 1e-6:
                            qc.rzz(4.0 * gamma_l * J[i, j], i, j)
                    if abs(h[i]) > 1e-6:
                        qc.rz(2.0 * gamma_l * h[i], i)
                # Mixer unitary e^{-i \beta \sum X_i}
                for i in range(n_vars):
                    qc.rx(2.0 * beta_l, i)
            qc.measure_all()
            return qc

        # -------------------------------------------------------------
        # Parameter Optimization
        # -------------------------------------------------------------
        sim = AerSimulator()
        eval_count = 0

        def cost_fn(params: np.ndarray) -> float:
            nonlocal eval_count
            eval_count += 1
            g = params[:self.p]
            b = params[self.p:]
            circ = build_circuit(g, b)
            seed_sim = (self.seed + eval_count) if self.seed is not None else None
            job = sim.run(circ, shots=min(self.shots, 512), seed_simulator=seed_sim)
            counts = job.result().get_counts()
            total_e = 0.0
            total_s = 0
            for bitstr, cnt in counts.items():
                z = np.array([int(c) for c in bitstr[::-1]], dtype=float)
                e = z @ Q_sym @ z + off
                total_e += e * cnt
                total_s += cnt
            return float(total_e / max(1, total_s))

        x0 = [0.4] * self.p + [0.4] * self.p
        bounds = [(0.0, 2.0 * np.pi)] * self.p + [(0.0, np.pi)] * self.p

        opt_res = minimize(
            cost_fn,
            x0,
            method="COBYLA",
            options={"maxiter": self.max_iterations},
        )

        opt_gammas = np.array(opt_res.x[:self.p], dtype=float)
        opt_betas = np.array(opt_res.x[self.p:], dtype=float)

        # -------------------------------------------------------------
        # Candidate Bitstring Sampling
        # -------------------------------------------------------------
        final_qc = build_circuit(opt_gammas, opt_betas)
        job_final = sim.run(final_qc, shots=self.shots, seed_simulator=self.seed)
        final_counts = job_final.result().get_counts()

        best_bitstring = None
        best_energy = float("inf")
        best_sample_cnt = 0
        distinct_samples = len(final_counts)

        for bitstr, cnt in final_counts.items():
            # Qiskit right-to-left bit order reverse to index order
            z = np.array([int(c) for c in bitstr[::-1]], dtype=float)
            e = float(z @ Q_sym @ z + off)
            if e < best_energy:
                best_energy = e
                best_bitstring = "".join(str(int(b)) for b in z)
                best_sample_cnt = cnt

        # Check feasibility across all sampled bitstrings if model is available
        feasible_sample_count = 0
        best_sampled_feasible_energy = None
        best_feasible_count = 0

        if isinstance(model_or_Q, QUBOModel):
            from evcore.decoder import decode_solution
            for bitstr, cnt in final_counts.items():
                rev = bitstr[::-1]
                dec = decode_solution(rev, model_or_Q)
                if dec["feasible"]:
                    feasible_sample_count += cnt
                    z = np.array([int(c) for c in rev], dtype=float)
                    e = float(z @ Q_sym @ z + off)
                    if best_sampled_feasible_energy is None or e < best_sampled_feasible_energy:
                        best_sampled_feasible_energy = round(float(e), 4)
                        best_feasible_count = cnt

        feasible_sample_probability = round(float(feasible_sample_count / max(1, self.shots)), 6)
        best_sample_frequency = round(float(best_sample_cnt / max(1, self.shots)), 6)
        best_feasible_frequency = round(float(best_feasible_count / max(1, self.shots)), 6)

        runtime_s = time.time() - start_time

        # -------------------------------------------------------------
        # Circuit Resource Metrics
        # -------------------------------------------------------------
        depth = final_qc.depth()
        total_gates = sum(v for k, v in final_qc.count_ops().items() if k != "measure")
        two_qubit_gates = final_qc.count_ops().get("rzz", 0) + final_qc.count_ops().get("cx", 0)

        try:
            t_qc = transpile(final_qc, basis_gates=["u", "cx"])
            transpiled_depth = t_qc.depth()
            transpiled_cx = t_qc.count_ops().get("cx", 0)
        except Exception:
            transpiled_depth = depth
            transpiled_cx = two_qubit_gates

        return {
            "status": "completed",
            "solver": "Quantum / Hybrid QAOA",
            "backend": "Qiskit Aer Simulator (aer_simulator)",
            "best_bitstring": best_bitstring,
            "best_energy": round(float(best_energy), 6),
            "runtime_s": round(float(runtime_s), 4),
            "metrics": {
                "evaluations": eval_count,
                "p": self.p,
                "shots": self.shots,
                "optimizer": self.optimizer,
                "best_sampled_qubo_energy": round(float(best_energy), 6),
                "best_sampled_feasible_energy": best_sampled_feasible_energy,
                "feasible_sample_count": feasible_sample_count,
                "feasible_sample_probability": feasible_sample_probability,
                "distinct_samples": distinct_samples,
                "best_sample_frequency": best_sample_frequency,
                "best_feasible_frequency": best_feasible_frequency,
                "optimal_parameters": {
                    "gamma": [round(float(g), 4) for g in opt_gammas],
                    "beta": [round(float(b), 4) for b in opt_betas],
                },
            },
            "resources": {
                "qubits": n_vars,
                "depth": depth,
                "transpiled_depth": transpiled_depth,
                "total_gates": total_gates,
                "two_qubit_gates": two_qubit_gates,
                "transpiled_cx_gates": transpiled_cx,
                "hamiltonian_terms": total_hamiltonian_terms,
                "is_estimated": False,
            },
            "parameters": {
                "solver": "Quantum / Hybrid QAOA",
                "p": self.p,
                "shots": self.shots,
                "optimizer": self.optimizer,
                "seed": self.seed,
            },
        }

    def _qubo_to_ising(
        self, Q_sym: np.ndarray, offset: float
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Converts symmetric QUBO matrix to Ising formulation."""
        N = Q_sym.shape[0]
        J = 0.25 * Q_sym.copy()
        np.fill_diagonal(J, 0.0)
        h = -0.5 * np.sum(Q_sym, axis=1)
        c_ising = float(offset + 0.25 * np.sum(Q_sym) + 0.25 * np.trace(Q_sym))
        return J, h, c_ising
