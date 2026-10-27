"""EV Coupled Optimization Core.

Primary Classical Solver: Simulated Annealing (SA)
Validation Solver: Exact Enumeration (Small instances only)
Quantum/Hybrid Solver: QAOA
"""

from evcore.qubo import QUBOModel, normalize_instance
from evcore.solver_sa import SimulatedAnnealingSolver
from evcore.exact_solver import ExactEnumerationSolver, calculate_optimality_gap
from evcore.qaoa_solver import QAOASolver
from evcore.decoder import decode_solution
from evcore.pipeline import run_optimization_pipeline, compare_solvers_for_instance

__all__ = [
    "QUBOModel",
    "normalize_instance",
    "SimulatedAnnealingSolver",
    "ExactEnumerationSolver",
    "calculate_optimality_gap",
    "QAOASolver",
    "decode_solution",
    "run_optimization_pipeline",
    "compare_solvers_for_instance",
]
