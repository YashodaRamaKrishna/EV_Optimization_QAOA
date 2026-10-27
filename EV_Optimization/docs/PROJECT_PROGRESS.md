# Project Progress

## 1. Current Project Status
- **System State:** Fully operational end-to-end optimization pipeline and interactive local research dashboard with both Classical (SA) and Quantum (Qiskit Aer QAOA) execution paths.
- **Formulation:** Binary Quadratic Unconstrained Binary Optimization (QUBO) with exact mathematical equivalence to Ising Cost Hamiltonian ($x_i = (1 - Z_i)/2$), verified across random bitstrings within machine precision ($10^{-10}$).
- **Primary Classical Solver:** Simulated Annealing (SA) operating directly on the binary QUBO formulation.
- **Validation Solver:** Exact Enumeration for small instances ($N \le 20$).
- **Quantum / Hybrid Solver:** Genuine QAOA circuit simulation via Qiskit Aer (`aer_simulator`), evaluating the exact same binary QUBO formulation with measured circuit resource metrics.
- **Problem Limits:** Hard bounded limits for custom problem creation: max 8 EVs, 5 stations, 8 time slots (problem-level definition limit).
- **Simulation Limit:** Strict guard of 24 logical qubits for QAOA Aer simulation; problems exceeding 24 qubits are cleanly blocked with structured `unsupported_size` status without executing large statevectors or fabricating results. SA remains runnable on all instances within problem limits (up to 325 QUBO variables).
- **Current Test Status:** 19 of 19 automated tests passing cleanly across Flask API, Simulated Annealing, QUBO formulation, Exact Enumeration, and Qiskit Aer QAOA test suites.
- **Acceptance Verification:** All 5 mandatory end-to-end acceptance tests (Tests A through E) verified and passing with 100% success.

---

## 2. Current Implementation Stage
- **Phase:** Quantum QAOA Aer Integration, Multi-Solver Selection, Bounded Custom Problem Limits & Dynamic Results Presentation.
- **Previous Stage:** Classical Simulated Annealing with exact small-instance validation.
- **Current Stage:** Full multi-solver execution pipeline:
  `Same Problem Instance → Same QUBO Formulation → Selected Solvers (SA / QAOA / Exact) → Same Decoder → Same Feasibility Validation → Result & Comparison Presentation`.

---

## 3. What is Working
- **Bounded Custom Problem Creation:** Strict dimension bounds (max 8 EVs, 5 stations, 8 time slots) enforced across frontend inputs, JavaScript pre-validation, and Flask backend (`POST /api/instances` returns HTTP 400 for out-of-bounds instances).
- **Dynamic Binary Variable Count:** Actual exact QUBO size $N_{\text{qubo}} = n_{st} + \sum_{e} (n_{st} \times |W_e|)$ dynamically computed and displayed in Problem Setup and Model views (no estimates or hardcoded numbers).
- **Multi-Solver Selection on Solve Page:** Checkbox-based solver cards allow users to select one or any combination of:
  1. *Simulated Annealing (SA)* — primary classical heuristic baseline.
  2. *Quantum / Hybrid QAOA* — Qiskit Aer simulation with parameter controls ($p$, shots, optimizer, iterations).
  3. *Exact Enumeration* — small-instance validation solver ($N \le 20$).
  Compatibility badges dynamically reflect solver availability based on instance size (QAOA disabled with warning if $N > 24$; Exact disabled if $N > 20$).
- **Genuine Qiskit Aer QAOA Simulator:**
  - $p$-layer QAOA ansatz with $R_{ZZ}(4 \gamma J_{ij})$ cost unitaries and $R_X(2 \beta)$ mixer unitaries.
  - Classical parameter optimization via COBYLA.
  - Candidate bitstring measurement and evaluation against the common QUBO matrix.
  - Measured quantum circuit resources: circuit depth, transpiled depth (basic basis gates `['u', 'cx']`), two-qubit gates, total gates, number of variational parameters ($2p$), and shot count.
  - Simulation guard capped at 24 logical qubits with clean `unsupported_size` response if exceeded.
- **Redesigned Result & Comparison Presentation:**
  - Individual semantic charging schedules rendered for each selected solver.
  - Comparative grid-load profiles rendered side-by-side when multiple solvers are executed.
  - Solver comparison metrics table rendered *only* when multiple solvers were run; omitted for single-solver runs.
  - Measured quantum resources card rendered whenever QAOA is run.
  - Full support for single-solver runs (SA-only and QAOA-only).
- **Exact Mathematical Consistency:** Verified that $E_{\text{qubo}}(z) == E_{\text{ising}}(s)$ with $s = 1 - 2z$ and symmetric Ising offset $c_{\text{ising}} = \text{offset} + \frac{1}{4}\sum Q_{\text{sym}} + \frac{1}{4}\text{Tr}(Q_{\text{sym}})$.

---

## 4. What is Partially Working / Deferred
- **IBM Quantum Hardware Execution:** Intentionally deferred. Execution currently targets local Qiskit Aer simulation. Hardware execution and IBM Runtime credentials will be integrated in a future milestone.
- **Deep Variational Parameter Optimization ($p \ge 3$):** Default ansatz uses $p=1$ with COBYLA. Higher $p$ layers and advanced optimizers (SPSA/ADAM) can be enabled via solver parameters.

---

## 5. Known Bugs
- **None currently identified.**
- *Resolved Bug:* Fixed trace correction term in Ising energy constant offset calculation ensuring exact energy match with QUBO.
- *Resolved Bug:* Fixed schedule rendering key mapping between decoder assignments and schedule tables.

---

## 6. Current Dashboard Status
- **Problem Setup:** Dimension limits enforced (max 8 EVs, 5 stations, 8 slots). Dynamic QUBO variable count displayed immediately.
- **Model:** Displays dynamic binary variable count, decision variables, physical objective, 5 constraints, QUBO formulation, and Ising transformation equations ($x_i = (1 - Z_i)/2$).
- **Solve:** Multi-select solver cards with compatibility badges, parameter accordions for SA and QAOA, and clear simulation limit explanations.
- **Result:** Adaptive view supporting single-solver and multi-solver runs, individual schedule tables, comparative load profiles, quantum resource cards, and conditional comparative tables.
- **Compare:** Evaluates completed runs on the common QUBO formulation.
- **Scaling:** Displays scaling ladder across dimensions.

---

## 7. Current Classical Solver Status
- **Primary Solver:** Simulated Annealing (`evcore/solver_sa.py`).
- **Formulation:** Direct binary QUBO ($z^T Q z + c$).
- **Computational Budgets:** Expressed through iterations, evaluations, runtime cutoff, and restarts. No arbitrary upper bound on objective value is required.
- **Performance:** Solves 3×2×4 baseline to global optimum (10.1) in ~0.25 s; solves custom 2×2×2 instance to global optimum (18.0) in ~0.02 s; solves 325-variable instance in ~0.35 s.

---

## 8. Current Quantum / QAOA Status
- **Primary Simulator:** Qiskit Aer (`aer_simulator`).
- **Implementation:** `evcore/qaoa_solver.py`.
- **Ansatz:** $p$-layer QAOA ($R_{ZZ}$ cost unitaries, $R_X$ mixer unitaries).
- **Variational Optimization:** COBYLA optimizer minimizing expected energy over candidate states.
- **Simulation Limit:** Hard cap at 24 logical qubits. Clean `unsupported_size` status returned when $N > 24$.
- **Circuit Resource Metrics:** Measured depth, transpiled depth, two-qubit gates, total gates, parameters, shots.

---

## 9. QUBO Status
- **Implementation:** `evcore/qubo.py`.
- **Indexing:**
  - $0 \dots n_{st}-1$: Station opening variables $y_s$.
  - $n_{st} \dots N-1$: Charging variables $x_{e,s,t}$ ordered by EV $e$, then station $s$, then slot $t \in W_e$.
- **Objective Terms:** Electricity pricing, EV detour travel cost, station opening cost, quadratic grid stress penalty ($\beta \sum_t \text{load}_t^2$).
- **Penalty Terms:** EV charging demand, station opening coupling, simultaneous charging prevention, station charger capacity, grid capacity.

---

## 10. Tests and Latest Test Results
- **Runner:** `python run_tests.py`
- **Result:** 19 of 19 tests passed (0 failures, 0 errors).
- **Test Suites Executed:**
  - `tests/test_api.py`: 8 tests (Health, Custom instance storage, SA run execution, Compare endpoint, Custom 2×2×2 API workflow, Bounded problem limits rejected, Multi-solver API execution, QAOA-only API execution).
  - `tests/test_classical_sa.py`: 5 tests (SA parameters, Budget limits without upper bounds, Baseline feasibility/optimality, Optimization pipeline end-to-end, Custom 2×2×2 optimization and grid metrics).
  - `tests/test_qubo_and_exact.py`: 4 tests (QUBO compilation, QUBO-Ising energy consistency, Exact enumeration ground truth, Optimality gap computation across solvers).
  - `tests/test_qaoa.py`: 2 tests (QAOA Aer execution and circuit metrics, QAOA simulation guard over limit).
- **End-to-End Acceptance Tests:** `python verify_scenarios.py` (Tests A through E: 100% passed).

---

## 11. Important Decisions
1. **Simulated Annealing is the Sole Primary Classical Solver:** Operates directly on the binary QUBO to provide an equitable heuristic baseline for QAOA.
2. **Exact Enumeration is for Validation Only:** Restricted to small instances ($N \le 20$) to determine ground-truth optimum and calculate optimality gaps.
3. **Bounded Custom Problem Limits:** Capped at 8 EVs, 5 stations, 8 time slots to prevent arbitrary payload generation.
4. **QAOA Aer Simulation Limit:** Capped at 24 logical qubits. Above this limit, QAOA is cleanly blocked with `unsupported_size` status without executing large statevectors or fabricating results.
5. **Unified QUBO and Decoder Pipeline:** Both SA and QAOA evaluate against the identical `QUBOModel` and decode bitstrings using the identical `decode_solution` function.
6. **Multi-Solver Presentation:** Comparison tables and comparative load series are shown conditionally only when multiple solvers are executed. Single-solver runs omit comparison blocks.

---

## 12. Known Limitations
1. **QAOA Simulator Limit:** Aer statevector simulation memory requirements limit local QAOA execution to $N \le 24$ logical qubits.
2. **Exact Enumeration Limit:** Exponential complexity ($O(2^N)$) limits exact enumeration to $N \le 20$.
3. **Single-Charger Station Simplification:** Station capacity penalty assumes 1 charger per station candidate ($C_s = 1$). Higher charger counts require separate station nodes or slack variables.
4. **Process Memory Storage:** Instances and runs reside in process memory; restarting Flask resets stored instances to defaults.

---

## 13. Immediate Next Steps
1. Add IBM Quantum hardware / IBM Runtime integration when hardware API credentials are provided.
2. Enable higher layer ansatz options ($p \in \{2, 3\}$) and alternative optimizers (SPSA).
3. Implement persistent SQLite storage for historical runs across server restarts.

---

## 14. Files Recently Changed
- `evcore/qaoa_solver.py`: Implemented genuine Qiskit Aer QAOA solver, circuit resource measurement, and 24-qubit simulation guard.
- `evcore/qubo.py`: Corrected Ising offset trace term to ensure exact $E_{\text{qubo}} == E_{\text{ising}}$ energy equivalence.
- `evcore/decoder.py`: Added detailed schedule assignment properties and schedule alias for seamless UI rendering.
- `evcore/pipeline.py`: Added `run_multi_solver_pipeline` and multi-solver result aggregation.
- `server/app.py`: Added bounded custom problem limits validation (HTTP 400), actual QUBO variable calculation, and multi-solver run dispatch.
- `server/static/index.html`: Added bounded problem controls, multi-solver checkboxes, badges, and adaptive result cards.
- `server/static/styles.css`: Added styles for solver cards, availability badges, multi-schedule grid, comparative bars, and quantum resource metrics.
- `server/static/app.js`: Added multi-solver selection handling, compatibility badge updates, custom bounds validation, and adaptive result rendering.
- `tests/test_api.py`: Added tests for bounded problem limits, multi-solver execution, and QAOA-only execution.
- `tests/test_qubo_and_exact.py`: Added test for QUBO-Ising energy consistency across random bitstrings.
- `tests/test_qaoa.py`: Created dedicated test suite for QAOA execution, circuit resource metrics, and simulation guard.
- `run_tests.py`: Updated test runner to execute all 19 automated tests.
- `verify_scenarios.py`: Created end-to-end acceptance test script for Tests A through E.

---

## 15. Handoff Notes for the Next Developer
1. **Do not change the primary classical solver:** The primary classical solver MUST remain Simulated Annealing. Do not replace it with MILP, CPLEX, or Tabu Search.
2. **Do not fabricate quantum results:** When an instance exceeds 24 qubits, QAOA must remain blocked with `unsupported_size`. Do not fabricate or substitute mock results.
3. **Preserve dual-directory synchronization:** Always keep `c:\Users\LOQ\Desktop\Quantum_2k26\project_1-10-2026` and `C:\Users\LOQ\Desktop\Quantum_2k26\Quantique_RGUKTN\project_1-10-2026` synchronized.
4. **Run both test suites before completing work:**
   - `python run_tests.py` (all 19 tests must pass).
   - `python verify_scenarios.py` (all 5 acceptance scenarios must pass).
