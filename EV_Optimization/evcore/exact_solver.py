"""Small-instance Exact Enumeration Solver.

SEPARATE EXACT ENUMERATION METHOD for small QUBO instances.

PURPOSE (ONLY):
    1. Validating the QUBO formulation.
    2. Determining the exact ground-truth optimum for small instances.
    3. Calculating exact optimality gaps for heuristic (SA) and quantum (QAOA) solutions.

NOT the primary classical solver. Evaluates on the EXACT SAME binary QUBO
formulation as Simulated Annealing and QAOA.
"""

from typing import Any, Dict, Optional, Tuple, Union
import time
import numpy as np
from evcore.qubo import QUBOModel


class ExactEnumerationSolver:
    """Exact enumeration solver for small binary QUBO instances.

    Evaluates all 2^N binary states using Gray code bit updates.
    """

    def __init__(self, max_variables: int = 20):
        """Initializes the exact enumeration solver.

        Parameters:
            max_variables: Safety threshold for maximum binary variables
                           to enumerate (2^20 ~= 1.05M states).
        """
        self.max_variables = max_variables

    def is_tractable(self, n_vars: int) -> bool:
        """Checks if the instance size is small enough for exact enumeration."""
        return n_vars <= self.max_variables

    def solve(
        self,
        model_or_Q: Union[QUBOModel, np.ndarray],
        offset: float = 0.0,
    ) -> Dict[str, Any]:
        """Evaluates all 2^N states to find the exact ground-truth optimum.

        Parameters:
            model_or_Q: QUBOModel or QUBO matrix.
            offset: Constant offset.

        Returns:
            Dictionary containing:
                - optimum_bitstring: Exact optimum binary bitstring.
                - optimum_vector: Exact optimum binary vector.
                - optimum_energy: Exact global minimum QUBO energy.
                - states_evaluated: Total number of evaluated states (2^N).
                - runtime_s: Enumeration runtime in seconds.
                - is_exact: True (guaranteed global optimum).
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

        if n_vars > self.max_variables:
            raise ValueError(
                f"Instance has {n_vars} variables, exceeding exact enumeration safety threshold ({self.max_variables}). "
                f"Use Simulated Annealing as the primary classical solver."
            )

        num_states = 1 << n_vars
        z = np.zeros(n_vars, dtype=np.int8)
        E = off
        h = np.zeros(n_vars, dtype=float)

        best_E = E
        best_z = z.copy()

        # Gray code enumeration: flips exactly 1 bit per step
        for k in range(1, num_states):
            bit = (k & -k).bit_length() - 1
            zi = z[bit]

            if zi == 0:
                delta_E = Q_sym[bit, bit] + 2.0 * h[bit]
                z[bit] = 1
                h += Q_sym[bit]
            else:
                delta_E = Q_sym[bit, bit] - 2.0 * h[bit]
                z[bit] = 0
                h -= Q_sym[bit]

            E += delta_E
            if E < best_E:
                best_E = E
                best_z = z.copy()

        runtime_s = time.time() - start_time
        optimum_bitstring = "".join(str(int(b)) for b in best_z)

        return {
            "optimum_bitstring": optimum_bitstring,
            "optimum_vector": best_z,
            "optimum_energy": round(float(best_E), 6),
            "states_evaluated": num_states,
            "runtime_s": round(float(runtime_s), 4),
            "is_exact": True,
        }


def calculate_optimality_gap(
    candidate_obj: float,
    ground_truth_obj: float,
) -> Tuple[float, str]:
    """Calculates the relative optimality gap: (candidate - optimum) / optimum * 100%.

    Returns:
        (gap_pct, formatted_string)
    """
    if abs(ground_truth_obj) < 1e-9:
        diff = max(0.0, candidate_obj - ground_truth_obj)
        return round(diff, 4), f"{diff:.2f} (abs)"

    gap = max(0.0, (candidate_obj - ground_truth_obj) / abs(ground_truth_obj)) * 100.0
    return round(gap, 2), f"{gap:.1f}%"
