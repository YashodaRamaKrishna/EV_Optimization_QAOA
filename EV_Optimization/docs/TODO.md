# TODO

## Current task

- [x] Implement Simulated Annealing (SA) as the primary classical QUBO solver.
- [x] Implement small-instance Exact Enumeration for ground-truth validation and optimality gap calculation.
- [x] Connect the end-to-end optimization pipeline: Problem Instance → QUBO Construction → Binary QUBO → SA → Best Binary Solution → Decoder → Feasibility Validation → Objective + Cost Breakdown → Dashboard.
- [x] Expose configurable SA computational parameters (iterations, temperatures, cooling schedule, seed, restarts, budgets) without requiring arbitrary upper bounds on objective values.
- [x] Connect Flask API and dashboard to the real pipeline.
- [x] Add comprehensive tests for SA, QUBO, Exact Enumeration, and API.
- [x] Implement dynamic binary variable count on Model tab based on active instance.
- [x] Add Hamiltonian transformation block on Model tab ($x_i = (1 - Z_i)/2$ and QAOA mapping).
- [x] Bind live cost breakdown directly to solver output on Result tab, suppressing demo references for live runs.
- [x] Implement Grid Performance section with 5 metrics (Peak Load, Peak Util, Avg Util, Near-Capacity Slots, Capacity Violations).
- [x] Implement dimension-agnostic semantic HTML EV charging schedule table (`table.schedule-table`) fixing column alignment.
- [x] Add automated regression tests for custom 2×2×2 instances across API and solver suites.
- [x] Enforce bounded custom problem limits: max 8 EVs, 5 stations, 8 time slots (frontend, JS, API 400).
- [x] Implement actual exact QUBO size computation dynamically in Problem Setup and Model views.
- [x] Implement multi-solver selection on Solve page (SA, QAOA, Exact) with dynamic compatibility badges.
- [x] Implement genuine Qiskit Aer QAOA circuit simulator with COBYLA and parameter measurement.
- [x] Implement simulation guard at 24 logical qubits with clean unsupported_size status.
- [x] Verify mathematical consistency between QUBO and Ising energies ($E_{\text{qubo}} == E_{\text{ising}}$).
- [x] Redesign Result presentation for multi-schedules, comparative load charts, quantum resources, and conditional comparison.
- [x] Validate all 5 mandatory end-to-end acceptance scenarios (Tests A through E).
- [x] Expand automated regression test suite to 19 passed tests across all 4 suites.

## Next tasks

- [ ] Add IBM Quantum hardware / IBM Runtime integration when hardware credentials and access are provided.
- [ ] Evaluate QAOA with deeper circuit layers (p > 1) and alternative classical optimizers (SPSA/ADAM).
- [ ] Add CSV/JSON export for multi-run benchmark results.
- [ ] Optionally add SQLite/file persistence if runs need to survive server restarts.

## Future research / experiments

- [ ] Evaluate QAOA on IBM Quantum hardware (e.g. ibm_brisbane / ibm_sherbrooke) via Qiskit Runtime Service.
- [ ] Populate empirical scaling ladder from batch experimental executions.
- [ ] Assess solution quality and resource scaling without assuming quantum advantage.
