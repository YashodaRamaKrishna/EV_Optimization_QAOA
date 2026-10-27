"""Comprehensive diagnostic script for QAOA on the Baseline Problem (22 qubits).
Addresses Sections 1, 2, 3, and 6 of the prompt:
1. Actual QAOA energy vs physical objective & penalty breakdown.
2. Ranking of all sampled bitstrings by actual QUBO energy (top 10).
3. Whether known feasible optimum or ANY feasible state was sampled.
6. Penalty magnitude comparison.
"""

import numpy as np
from evcore.mock import BASELINE
from evcore.qubo import QUBOModel
from evcore.qaoa_solver import QAOASolver
from evcore.solver_sa import SimulatedAnnealingSolver
from evcore.decoder import decode_solution

model = QUBOModel(BASELINE)

# 1. Best known feasible solution via SA
sa = SimulatedAnnealingSolver(n_iterations=5000, restarts=10, seed=42)
sa_res = sa.solve(model)
best_sa_bitstr = sa_res["best_bitstring"]
best_sa_decoded = decode_solution(best_sa_bitstr, model)
best_sa_energy = model.evaluate_energy([int(c) for c in best_sa_bitstr])

print("=" * 70)
print("SECTION 1 & 6: KNOWN FEASIBLE OPTIMUM VS QAOA RETURNED CANDIDATE")
print("=" * 70)
print(f"Known Feasible Bitstring: {best_sa_bitstr}")
print(f"  QUBO Energy:       {best_sa_energy:.4f}")
print(f"  Physical Obj:      {best_sa_decoded['objective']:.4f}")
print(f"  Feasible:          {best_sa_decoded['feasible']}")
print(f"  Violations:        {best_sa_decoded['violations']}")
print(f"  Cost Breakdown:    {best_sa_decoded['cost_breakdown']}")

# Run QAOA p=1, shots=512, iter=25, seed=42
qaoa = QAOASolver(p=1, shots=512, optimizer="COBYLA", max_iterations=25, seed=42)

# We want to inspect all counts from the final circuit
# Let's run qaoa.solve and also inspect counts
qaoa_res = qaoa.solve(model)
qaoa_bitstr = qaoa_res["best_bitstring"]
qaoa_decoded = decode_solution(qaoa_bitstr, model)
qaoa_energy = model.evaluate_energy([int(c) for c in qaoa_bitstr])

print("\nQAOA Returned Candidate (p=1, shots=512, iter=25):")
print(f"  Raw Bitstring:     {qaoa_bitstr}")
print(f"  QUBO Energy:       {qaoa_energy:.4f}")
print(f"  Physical Obj:      {qaoa_decoded['objective']:.4f}")
print(f"  Total Penalty:     {qaoa_energy - qaoa_decoded['objective']:.4f}")
print(f"  Feasible:          {qaoa_decoded['feasible']}")
print(f"  Violations:        {qaoa_decoded['violations']}")
print(f"  Cost Breakdown:    {qaoa_decoded['cost_breakdown']}")

print("\nPenalty Magnitude Verification:")
print(f"  Physical Obj Difference (QAOA - SA):  {qaoa_decoded['objective'] - best_sa_decoded['objective']:+.4f}")
print(f"  Total Penalty Difference (QAOA - SA): {qaoa_energy - qaoa_decoded['objective']:+.4f} (demand penalty)")
print(f"  Total QUBO Energy Difference:         {qaoa_energy - best_sa_energy:+.4f}")

# Re-run final circuit to examine ALL sampled bitstrings
gammas = np.array(qaoa_res["metrics"]["optimal_parameters"]["gamma"])
betas = np.array(qaoa_res["metrics"]["optimal_parameters"]["beta"])

from qiskit_aer import AerSimulator
sim = AerSimulator()
final_qc = qaoa_res  # We can rebuild or re-run
# To be exact, build circuit with optimal gammas/betas
J, h, c_ising = model.to_ising()
n_vars = model.n_vars
from qiskit import QuantumCircuit
qc = QuantumCircuit(n_vars)
qc.h(range(n_vars))
for l in range(qaoa.p):
    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            if abs(J[i, j]) > 1e-6:
                qc.rzz(4.0 * gammas[l] * J[i, j], i, j)
        if abs(h[i]) > 1e-6:
            qc.rz(2.0 * gammas[l] * h[i], i)
    for i in range(n_vars):
        qc.rx(2.0 * betas[l], i)
qc.measure_all()

counts = sim.run(qc, shots=512, seed_simulator=42).result().get_counts()

print("\n" + "=" * 70)
print("SECTION 2: ALL SAMPLED BITSTRINGS RANKED BY ACTUAL QUBO ENERGY")
print("=" * 70)

samples = []
for bitstr, cnt in counts.items():
    rev_bitstr = bitstr[::-1]
    z = [int(c) for c in rev_bitstr]
    energy = model.evaluate_energy(z)
    dec = decode_solution(rev_bitstr, model)
    samples.append({
        "bitstring": rev_bitstr,
        "count": cnt,
        "prob": cnt / 512.0,
        "qubo_energy": energy,
        "physical_obj": dec["objective"],
        "feasible": dec["feasible"],
        "violations": dec["violations"],
    })

# Sort by actual QUBO energy
samples.sort(key=lambda s: s["qubo_energy"])

print(f"Total distinct bitstrings sampled: {len(samples)} out of 512 shots")
print(f"{'Rank':<5} {'Bitstring':<24} {'Count':<6} {'Prob':<6} {'QUBO Energy':<12} {'Phys Obj':<10} {'Feasible':<9} {'Violations'}")
print("-" * 105)

for rank, s in enumerate(samples[:15], 1):
    viols_str = "; ".join(s["violations"]) if s["violations"] else "None"
    print(f"{rank:<5} {s['bitstring']:<24} {s['count']:<6} {s['prob']:<6.3f} {s['qubo_energy']:<12.3f} {s['physical_obj']:<10.2f} {str(s['feasible']):<9} {viols_str}")

print("\n" + "=" * 70)
print("SECTION 3: FEASIBLE SAMPLING ANALYSIS")
print("=" * 70)

feasible_samples = [s for s in samples if s["feasible"]]
feasible_shots = sum(s["count"] for s in feasible_samples)
p_feasible = feasible_shots / 512.0

print(f"Known optimum bitstring sampled?: {any(s['bitstring'] == best_sa_bitstr for s in samples)}")
print(f"Any feasible bitstring sampled?:  {len(feasible_samples) > 0}")
print(f"Total feasible samples:           {len(feasible_samples)} distinct bitstrings ({feasible_shots} total shots)")
print(f"P(feasible):                      {p_feasible:.4f} ({p_feasible * 100:.2f}%)")

if feasible_samples:
    best_feas = min(feasible_samples, key=lambda s: s["qubo_energy"])
    print(f"Best sampled feasible QUBO energy: {best_feas['qubo_energy']:.4f} (Obj: {best_feas['physical_obj']:.2f})")
else:
    print("No feasible solution was observed in the QAOA samples.")

print(f"Best sampled overall QUBO energy:  {samples[0]['qubo_energy']:.4f} (Feasible: {samples[0]['feasible']})")
