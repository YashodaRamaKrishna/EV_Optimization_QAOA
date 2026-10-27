# Changelog

## 2026-10-05 — Qiskit Aer QAOA Simulator, Multi-Solver Selection & Bounded Problem Limits

- **Files/components:** `evcore/qaoa_solver.py`, `evcore/qubo.py`, `evcore/decoder.py`, `evcore/pipeline.py`, `server/app.py`, `server/static/index.html`, `server/static/app.js`, `server/static/styles.css`, `tests/test_qaoa.py`, `tests/test_api.py`, `tests/test_qubo_and_exact.py`, `run_tests.py`, `verify_scenarios.py`, documentation.
- **Change:** Implemented genuine Qiskit Aer QAOA simulation on the common QUBO formulation, multi-solver selection on the Solve page, bounded custom problem limits, and adaptive multi-schedule & comparative load presentations.
- **Description:**
  - **Bounded Custom Problem Limits:** Enforced maximum 8 EVs, 5 stations, 8 time slots on frontend input controls, JavaScript validation, and Flask backend (`POST /api/instances` returns 400 with descriptive error if violated).
  - **Exact QUBO Size Calculation:** Calculated and displayed actual binary variable count $N = n_{st} + \sum n_{st} \times |W_e|$ across Problem Setup and Model views.
  - **Multi-Solver Selection:** Redesigned Solve page with selectable solver cards for Simulated Annealing (SA), Quantum / Hybrid QAOA, and Exact Enumeration. Implemented dynamic compatibility badges that disable QAOA if $N > 24$ and Exact Enumeration if $N > 20$.
  - **Genuine Qiskit Aer QAOA:** Implemented parameterized QAOA circuit simulation using Qiskit Aer (`aer_simulator`), $R_{ZZ}$ cost unitaries, $R_X$ mixer unitaries, and COBYLA classical parameter optimization. Circuit analysis measures genuine quantum resources: logical qubits, circuit depth, transpiled depth, two-qubit gates, total gates, parameters, and shots.
  - **Simulation Guard (24 Logical Qubits):** Distinguished problem limits (up to 325 variables) from simulation limits (24 qubits). Instances with $N > 24$ return structured `unsupported_size` status with clear explanation without executing large statevectors or fabricating results. SA continues to solve the instance.
  - **Mathematical Consistency:** Verified exact energy equivalence between QUBO and Ising formulation ($E_{\text{qubo}}(z) == E_{\text{ising}}(s)$) within machine precision across random bitstrings and instances.
  - **Adaptive Result Presentation:** Rendered individual semantic schedule tables for each executed solver, comparative grid load profiles for multi-solver runs, measured quantum resources card for QAOA runs, and conditional comparison metrics shown only when multiple solvers are run.
  - **Testing & Verification:** Added 6 new automated tests (expanding test suite to 19 passed tests) and verified all 5 mandatory end-to-end acceptance scenarios (Tests A through E) with 100% success. Synchronized changes across both workspace directories.

## 2026-10-02 — Dashboard Corrections & Grid Performance Integration

- **Files/components:** `server/static/index.html`, `server/static/app.js`, `server/static/styles.css`, `evcore/pipeline.py`, `tests/test_classical_sa.py`, `tests/test_api.py`, `run_tests.py`, documentation.
- **Change:** Implemented dynamic binary-variable count, added Hamiltonian transformation explanation, fixed live cost-breakdown binding, added Grid Performance analytics with 5 metrics, and fixed EV charging schedule table alignment across arbitrary instance dimensions.
- **Description:**
  - Dynamic binary variable count: Replaced hard-coded "22 variables" on the Model tab with a dynamic count computed from active instance dimensions ($N = n_{st} + \sum n_{st} \times |W_e|$), correctly showing 22 for baseline and 6 for a custom 2×2×2 instance.
  - Hamiltonian transformation: Added an explanatory section on the Model tab below QUBO transformation showing $x_i = (1 - Z_i)/2$ and the workflow: Problem $\to$ Objective + Constraints $\to$ QUBO $\to$ Ising $\to$ Cost Hamiltonian $\to$ QAOA.
  - Live cost breakdown binding: Resolved display issue where "Precomputed demo reference" remained visible on live runs; bound Result cards and charts directly to the current decoded solution.
  - Grid Performance: Renamed section and added 5 metrics: Peak Load ($L_{\max}$), Peak Utilization ($\max_t L_t/G_t$), Average Utilization ($\frac{1}{T}\sum_t L_t/G_t$), Near-Capacity Slots ($L_t/G_t \ge 0.80$), and Capacity Violations ($L_t > G_t$).
  - Schedule Table Alignment: Replaced fixed 4-column CSS grid with a semantic HTML table (`.schedule-table`), ensuring the first column strictly contains EV identifiers, header columns strictly contain time slots, and cells correctly render decoded station IDs.
  - Added automated tests for custom 2×2×2 optimization and grid metrics, expanding the regression suite to 13 passed tests.

## 2026-10-02 — Simulated Annealing Primary Classical Solver & Pipeline Integration

- **Files/components:** `evcore/qubo.py`, `evcore/solver_sa.py`, `evcore/exact_solver.py`, `evcore/decoder.py`, `evcore/qaoa_solver.py`, `evcore/pipeline.py`, `server/app.py`, `server/static/app.js`, `server/static/index.html`, `server/static/styles.css`, `tests/test_classical_sa.py`, `tests/test_qubo_and_exact.py`, `tests/test_api.py`, documentation.
- **Change:** Implemented Simulated Annealing (SA) as the primary classical QUBO solver along with small-instance Exact Enumeration for ground-truth validation, connecting the complete optimization pipeline from problem instance to decoded dashboard views.
- **Description:**
  - Constructed the full binary QUBO formulation from problem instances (infrastructure opening, electricity pricing, EV detour travel cost, quadratic grid stress penalty, and constraint penalties for demand, coupling, time windows, and capacity limits).
  - Implemented `SimulatedAnnealingSolver` operating directly on the binary QUBO with configurable parameters: iterations/evaluations, initial/final temperature, cooling schedules (geometric, linear, exponential), random seed, and independent restarts. Enforced computational limits via solver budgets without requiring arbitrary upper bounds on objective values.
  - Implemented `ExactEnumerationSolver` separately for small instances (N ≤ 20) to determine exact ground truth optimum, validate QUBO formulations, and compute exact optimality gaps.
  - Implemented `decode_solution` to map binary solution vectors into domain decisions, perform comprehensive feasibility validation, and compute itemized cost breakdowns (electricity, detour, infrastructure, grid stress).
  - Evaluated Simulated Annealing, QAOA, and Exact Enumeration on the identical binary QUBO formulation.
  - Updated Flask backend and interactive dashboard frontend to configure solver parameters and visualize decoded schedules, load charts, cost breakdowns, and optimality gap metrics.

## 2026-10-01 — Custom Problem builder

- **Files/components:** `server/static/index.html`, `server/static/app.js`, `server/static/styles.css`, `tests/test_api.py`, documentation.
- **Change:** Added incremental custom instance creation inside Problem Setup.
- **Description:** Users can set dimensions, generate EV/station/time-slot/travel-cost fields, receive inline validation, and save a compatible active instance through the existing API. The baseline and all other dashboard tabs remain unchanged.

## 2026-10-01 — Project documentation baseline

- **Files/components:** `docs/PROJECT_PROGRESS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/TODO.md`, `docs/CHANGELOG.md`
- **Change:** Added the dedicated project progress and documentation set.
- **Description:** Recorded the current Flask/vanilla-JS dashboard, mock API/core status, actual interfaces, decisions, limitations, and pending work. No application behavior was changed.
