"""Simulated Annealing (SA) QUBO Solver.

PRIMARY CLASSICAL SOLVER for the EV Coupled Optimization project.

Operates directly on the binary QUBO formulation:
    min z^T Q z + offset,  z in {0, 1}^N

Provides a practical classical heuristic baseline for comparison with QAOA
and evaluation against exact ground truth.

Exposes configurable computational budgets and cooling parameters without
requiring any arbitrary upper bound on the objective value.
"""

from typing import Any, Dict, List, Optional, Union
import math
import time
import numpy as np
from evcore.qubo import QUBOModel


class SimulatedAnnealingSolver:
    """Configurable Simulated Annealing solver for binary QUBO problems."""

    def __init__(
        self,
        n_iterations: int = 4000,
        initial_temp: float = 10.0,
        final_temp: float = 0.01,
        cooling_schedule: str = "geometric",
        seed: Optional[int] = 42,
        restarts: int = 5,
        quench: bool = True,
        runtime_budget_s: Optional[float] = None,
        eval_budget: Optional[int] = None,
    ):
        """Initializes the SA solver with configurable computational parameters.

        Parameters:
            n_iterations: Number of evaluation steps / iterations per restart.
            initial_temp: Starting temperature T_0.
            final_temp: Final temperature T_f (must be > 0).
            cooling_schedule: "geometric", "linear", or "exponential".
            seed: Random seed for deterministic reproducibility.
            restarts: Number of independent restarts/runs.
            quench: Whether to perform a zero-temperature local greedy quench
                    at the end of each restart to reach a local optimum.
            runtime_budget_s: Optional maximum runtime budget in seconds.
            eval_budget: Optional maximum evaluation count budget.
        """
        self.n_iterations = max(10, int(n_iterations))
        self.initial_temp = max(1e-4, float(initial_temp))
        self.final_temp = max(1e-6, min(float(final_temp), self.initial_temp))
        self.cooling_schedule = cooling_schedule.lower()
        self.seed = seed
        self.restarts = max(1, int(restarts))
        self.quench = bool(quench)
        self.runtime_budget_s = (
            float(runtime_budget_s) if runtime_budget_s is not None else None
        )
        self.eval_budget = (
            int(eval_budget) if eval_budget is not None else None
        )

    def solve(
        self,
        model_or_Q: Union[QUBOModel, np.ndarray],
        offset: float = 0.0,
    ) -> Dict[str, Any]:
        """Solves the binary QUBO problem using Simulated Annealing.

        Parameters:
            model_or_Q: QUBOModel instance or symmetric/upper QUBO matrix.
            offset: Scalar constant offset (ignored if QUBOModel is passed).

        Returns:
            Dictionary containing:
                - best_bitstring: Best binary solution bitstring found.
                - best_vector: Best binary vector (np.ndarray).
                - best_energy: Minimum QUBO energy achieved.
                - evaluations: Total number of proposed candidate evaluations.
                - runtime_s: Solver execution time in seconds.
                - restarts_performed: Number of restarts executed.
                - parameters: Configured solver parameters.
        """
        start_time = time.time()

        if isinstance(model_or_Q, QUBOModel):
            Q_sym = model_or_Q.Q_sym
            off = model_or_Q.offset
            n_vars = model_or_Q.n_vars
        else:
            Q = np.asarray(model_or_Q, dtype=float)
            Q_sym = 0.5 * (Q + Q.T)
            off = float(offset)
            n_vars = Q_sym.shape[0]

        rng = np.random.RandomState(self.seed)

        best_overall_z = rng.randint(0, 2, size=n_vars)
        best_overall_energy = float(best_overall_z.dot(Q_sym).dot(best_overall_z)) + off

        total_evaluations = 0
        restarts_done = 0
        energy_history: List[float] = []

        # Precompute cooling parameters
        if self.cooling_schedule == "geometric":
            decay_rate = (self.final_temp / self.initial_temp) ** (
                1.0 / max(1, self.n_iterations - 1)
            )
        elif self.cooling_schedule == "exponential":
            decay_rate = math.log(self.initial_temp / self.final_temp) / max(
                1, self.n_iterations - 1
            )
        else:
            decay_rate = 0.0

        for r in range(self.restarts):
            # Budget check before restart
            if self.runtime_budget_s is not None and (time.time() - start_time) >= self.runtime_budget_s:
                break
            if self.eval_budget is not None and total_evaluations >= self.eval_budget:
                break

            restarts_done += 1

            # Independent restart state initialization
            z = rng.randint(0, 2, size=n_vars).astype(np.int8)
            current_energy = float(z.dot(Q_sym).dot(z)) + off
            total_evaluations += 1

            # Running field vector h_i = sum_j Q_sym[i, j] z[j]
            # Enables O(1) delta energy calculation for proposed bit flips
            h = Q_sym.dot(z.astype(float))

            best_restart_z = z.copy()
            best_restart_energy = current_energy

            if current_energy < best_overall_energy:
                best_overall_energy = current_energy
                best_overall_z = z.copy()

            T = self.initial_temp

            for step in range(self.n_iterations):
                if self.runtime_budget_s is not None and (time.time() - start_time) >= self.runtime_budget_s:
                    break
                if self.eval_budget is not None and total_evaluations >= self.eval_budget:
                    break

                i = rng.randint(0, n_vars)
                zi = z[i]

                # Exact delta energy:
                # If flipping 0 -> 1: delta_E = Q_sym[i, i] + 2 * h[i]
                # If flipping 1 -> 0: delta_E = Q_sym[i, i] - 2 * h[i]
                if zi == 0:
                    delta_e = Q_sym[i, i] + 2.0 * h[i]
                else:
                    delta_e = Q_sym[i, i] - 2.0 * h[i]

                total_evaluations += 1

                # Metropolis-Hastings acceptance criterion
                accept = False
                if delta_e <= 0.0:
                    accept = True
                else:
                    temp_safe = max(T, 1e-9)
                    arg = -delta_e / temp_safe
                    if arg > -700.0 and rng.rand() < math.exp(arg):
                        accept = True

                if accept:
                    diff = 1.0 if zi == 0 else -1.0
                    z[i] = 1 - zi
                    current_energy += delta_e
                    h += Q_sym[:, i] * diff

                    if current_energy < best_restart_energy:
                        best_restart_energy = current_energy
                        best_restart_z = z.copy()

                    if current_energy < best_overall_energy:
                        best_overall_energy = current_energy
                        best_overall_z = z.copy()

                # Cooling update
                if self.cooling_schedule == "geometric":
                    T *= decay_rate
                elif self.cooling_schedule == "exponential":
                    T = self.initial_temp * math.exp(-decay_rate * step)
                elif self.cooling_schedule == "linear":
                    frac = step / max(1, self.n_iterations - 1)
                    T = self.initial_temp - frac * (self.initial_temp - self.final_temp)
                else:
                    T *= 0.995

            # Optional local quench (zero-temperature greedy descent)
            if self.quench:
                quench_improved = True
                max_quench_passes = 10
                pass_count = 0
                while quench_improved and pass_count < max_quench_passes:
                    quench_improved = False
                    pass_count += 1
                    for i in range(n_vars):
                        zi = z[i]
                        delta_e = (Q_sym[i, i] + 2.0 * h[i]) if zi == 0 else (Q_sym[i, i] - 2.0 * h[i])
                        total_evaluations += 1
                        if delta_e < -1e-9:
                            diff = 1.0 if zi == 0 else -1.0
                            z[i] = 1 - zi
                            current_energy += delta_e
                            h += Q_sym[:, i] * diff
                            quench_improved = True

                if current_energy < best_restart_energy:
                    best_restart_energy = current_energy
                    best_restart_z = z.copy()

                if current_energy < best_overall_energy:
                    best_overall_energy = current_energy
                    best_overall_z = z.copy()

            energy_history.append(float(best_restart_energy))

        runtime_s = time.time() - start_time
        best_bitstring = "".join(str(int(b)) for b in best_overall_z)

        return {
            "best_bitstring": best_bitstring,
            "best_vector": best_overall_z,
            "best_energy": round(float(best_overall_energy), 6),
            "evaluations": total_evaluations,
            "runtime_s": round(float(runtime_s), 4),
            "restarts_performed": restarts_done,
            "parameters": {
                "solver": "Simulated Annealing (SA)",
                "n_iterations": self.n_iterations,
                "initial_temp": self.initial_temp,
                "final_temp": self.final_temp,
                "cooling_schedule": self.cooling_schedule,
                "seed": self.seed,
                "restarts": self.restarts,
                "quench": self.quench,
                "runtime_budget_s": self.runtime_budget_s,
                "eval_budget": self.eval_budget,
            },
            "history": energy_history,
        }
