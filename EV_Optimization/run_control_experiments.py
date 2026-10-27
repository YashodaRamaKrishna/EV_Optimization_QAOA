"""Section 7: Control Experiments on Baseline QUBO (22 Qubits).

Runs:
Experiment A: p=1, shots=512,  max_iterations=25,  seed=42
Experiment B: p=1, shots=4096, max_iterations=100, seed=42
Experiment C: p=2, shots=4096, max_iterations=100, seed=42

For each experiment, reports:
- p
- shots
- optimizer evaluations
- best sampled QUBO energy
- best feasible QUBO energy
- best physical objective
- feasible?
- P(feasible)
- runtime
- optimality gap (vs exact ground truth / SA best 10.1 or 10.3)
"""

import time
import numpy as np
from evcore.mock import BASELINE
from evcore.qubo import QUBOModel
from evcore.qaoa_solver import QAOASolver
from evcore.decoder import decode_solution
from evcore.exact_solver import calculate_optimality_gap

model = QUBOModel(BASELINE)
ground_truth_obj = 10.1  # Global optimum for baseline

experiments = [
    {"name": "Experiment A", "p": 1, "shots": 512,  "max_iter": 25,  "seed": 42},
    {"name": "Experiment B", "p": 1, "shots": 4096, "max_iter": 100, "seed": 42},
    {"name": "Experiment C", "p": 2, "shots": 4096, "max_iter": 100, "seed": 42},
]

print("=" * 80)
print("SECTION 7: QAOA CONTROL EXPERIMENTS (BASELINE 22 QUBITS)")
print("=" * 80)

for exp in experiments:
    print(f"\n--- Running {exp['name']}: p={exp['p']}, shots={exp['shots']}, max_iter={exp['max_iter']} ---")
    start = time.time()
    
    solver = QAOASolver(
        p=exp["p"],
        shots=exp["shots"],
        optimizer="COBYLA",
        max_iterations=exp["max_iter"],
        seed=exp["seed"],
    )
    res = solver.solve(model)
    elapsed = time.time() - start
    
    best_bitstr = res["best_bitstring"]
    best_dec = decode_solution(best_bitstr, model)
    best_qubo_e = res["best_energy"]
    
    # Analyze all sampled states from the run
    # To get distribution, run circuit with optimal parameters
    from qiskit_aer import AerSimulator
    from qiskit import QuantumCircuit
    
    sim = AerSimulator()
    gammas = np.array(res["metrics"]["optimal_parameters"]["gamma"])
    betas = np.array(res["metrics"]["optimal_parameters"]["beta"])
    J, h, c = model.to_ising()
    n_vars = model.n_vars
    
    qc = QuantumCircuit(n_vars)
    qc.h(range(n_vars))
    for l in range(exp["p"]):
        for i in range(n_vars):
            for j in range(i + 1, n_vars):
                if abs(J[i, j]) > 1e-6:
                    qc.rzz(4.0 * gammas[l] * J[i, j], i, j)
            if abs(h[i]) > 1e-6:
                qc.rz(2.0 * gammas[l] * h[i], i)
        for i in range(n_vars):
            qc.rx(2.0 * betas[l], i)
    qc.measure_all()
    
    counts = sim.run(qc, shots=exp["shots"], seed_simulator=exp["seed"]).result().get_counts()
    
    feasible_count = 0
    best_feas_energy = float("inf")
    best_feas_obj = None
    
    for b_str, cnt in counts.items():
        rev = b_str[::-1]
        z = [int(c) for c in rev]
        e = model.evaluate_energy(z)
        dec = decode_solution(rev, model)
        if dec["feasible"]:
            feasible_count += cnt
            if e < best_feas_energy:
                best_feas_energy = e
                best_feas_obj = dec["objective"]
                
    p_feas = feasible_count / float(exp["shots"])
    
    gap_val, gap_str = calculate_optimality_gap(best_dec["objective"], ground_truth_obj)
    
    print(f"  p:                           {exp['p']}")
    print(f"  shots:                       {exp['shots']}")
    print(f"  optimizer evaluations:       {res['metrics']['evaluations']}")
    print(f"  best sampled QUBO energy:    {best_qubo_e:.4f}")
    if feasible_count > 0:
        print(f"  best feasible QUBO energy:   {best_feas_energy:.4f}")
    else:
        print(f"  best feasible QUBO energy:   None (No feasible solution observed)")
    print(f"  best physical objective:     {best_dec['objective']:.4f}")
    print(f"  feasible?:                   {best_dec['feasible']}")
    if not best_dec['feasible']:
        print(f"  violations:                  {best_dec['violations']}")
    print(f"  P(feasible):                 {p_feas:.4f} ({p_feas * 100:.2f}%)")
    print(f"  runtime:                     {elapsed:.2f}s")
    print(f"  optimality gap (vs {ground_truth_obj}): {gap_str}")
    print(f"  optimal parameters:          gamma={gammas.tolist()}, beta={betas.tolist()}")
