# Current Architecture

This document describes the repository architecture, solvers, APIs, and multi-solver optimization pipeline.

## Folder structure

```text
server/
  __main__.py          Flask local entry point
  app.py               routes, bounded limits validation, multi-solver dispatch, in-memory state
  static/
    index.html         single-page dashboard markup (bounded controls, multi-solver selection, results)
    styles.css         technical styles, badges, multi-schedule layout, comparative load bars
    app.js             browser state, multi-solver selection, validation, API integration, rendering
evcore/
  qubo.py              instance normalization, QUBO compilation, exact Ising mapping (with trace correction)
  solver_sa.py         primary classical solver (Simulated Annealing on binary QUBO)
  exact_solver.py      small-instance validation solver (Exact Enumeration, N <= 20)
  decoder.py           solution decoder, feasibility validator, cost breakdown, schedule assignments
  qaoa_solver.py       genuine Qiskit Aer QAOA simulator, circuit metrics, 24-qubit simulation guard
  pipeline.py          multi-solver execution pipeline, optimality gap evaluator, common QUBO dispatch
  mock.py              baseline reference fixture and presets
tests/
  test_classical_sa.py SA solver parameter, budget, and pipeline tests (5 tests)
  test_qubo_and_exact.py QUBO model, exact Ising energy consistency, Exact Enumeration tests (4 tests)
  test_api.py          Flask API endpoints, bounded limits, and multi-solver run tests (8 tests)
  test_qaoa.py         QAOA Aer simulation, circuit resource metrics, simulation guard tests (2 tests)
docs/                  project documentation (Progress, Architecture, Decisions, Todo, Changelog)
run_tests.py           automated runner executing all 19 regression tests
verify_scenarios.py    acceptance test verifying all 5 end-to-end scenarios (Tests A through E)
requirements.txt       Flask, NumPy, SciPy, Qiskit, Qiskit-Aer dependencies
```

## Primary Optimization Pipeline

The core multi-solver architecture guarantees that all solvers evaluate on the exact same QUBO formulation and are evaluated against identical physical constraints:

```text
Problem Instance (Max 8 EVs, 5 Stations, 8 Slots)
    ↓
QUBO Construction (Actual N_qubo = n_st + \sum n_st * |W_e|)
    ↓
Binary QUBO Matrix Q & Offset
    ↓
    ├───────────────────────────────┬───────────────────────────────┐
    ↓                               ↓                               ↓
Simulated Annealing          Exact Enumeration                Qiskit Aer QAOA
(Primary Classical)           (Small instances N <= 20)      (Simulation guard N <= 24)
    ↓                               ↓                               ↓
Candidate Bitstring          Ground Truth Bitstring           Candidate Bitstring
    └───────────────────────────────┴───────────────────────────────┘
                                    ↓
                       Common Solution Decoder
                                    ↓
                          Feasibility Validator
                                    ↓
                     Objective & Itemized Cost Breakdown
                                    ↓
            Dashboard (Individual Schedules, Load Profiles, Comparison)
```

## Solvers

### 1. Simulated Annealing (SA) — Primary Classical Solver
- Operates directly on the binary QUBO formulation ($z^T Q z + c$).
- Configurable parameters:
  - Iterations / candidate evaluations per restart
  - Initial temperature ($T_0$)
  - Final temperature ($T_f$) and cooling schedules (geometric, linear, exponential)
  - Random seed for reproducibility
  - Number of independent restarts/runs
  - Evaluation and runtime budgets
- Computational limits are strictly expressed through budgets (iterations, evaluations, runtime, restarts) without requiring an arbitrary upper bound on objective values.

### 2. Quantum / Hybrid QAOA — Qiskit Aer Simulator
- Evaluates on the exact same QUBO / Ising formulation ($x_i = (1 - Z_i)/2$).
- Cost Hamiltonian unitary: $e^{-i \gamma H_C} = \prod_{i < j} R_{ZZ}(4 \gamma J_{ij}) \prod_i R_Z(2 \gamma h_i)$.
- Mixer unitary: $e^{-i \beta H_M} = \prod_i R_X(2 \beta)$.
- Variational parameter optimization via COBYLA on Qiskit Aer simulator (`aer_simulator`).
- **Simulation Guard:** Strictly capped at 24 logical qubits. If $N > 24$, QAOA returns a structured `unsupported_size` status explaining that the problem size exceeds the simulator limit, preventing large statevector execution or crashes. SA continues to solve.
- **Circuit Resource Metrics Measured:** Logical qubits, circuit depth, transpiled depth (basic basis gates `['u', 'cx']`), two-qubit gates, total gates, variational parameters ($2p$), and shot count.

### 3. Exact Enumeration — Validation Solver (Small Instances)
- Evaluates all $2^N$ binary states using Gray code updates.
- Purpose strictly limited to:
  1. Validating the QUBO formulation.
  2. Determining exact ground-truth optimum for small instances ($N \le 20$).
  3. Calculating exact optimality gaps for heuristic (SA) and quantum (QAOA) solutions.
- Not the primary classical solver.

## Frontend

`server/static/index.html` contains all six tab panels:
1. **Problem Setup**: Preset loading and Custom Problem builder with bounded dimension controls (max 8 EVs, 5 stations, 8 slots), dynamic exact QUBO variable count, window selectors, station costs, grid capacities, and travel detour matrix.
2. **Model**: Pipeline walkthrough, dynamic binary variable count ($N = n_{st} + \sum_{e} n_{st} |W_e|$), mathematical formulation, constraint breakdown, QUBO transformation, and Ising transformation equations ($x_i = (1 - Z_i)/2$).
3. **Solve**: Multi-solver selector (SA, QAOA, Exact Enumeration) with dynamic compatibility badges, parameter accordions, and simulation guard warnings.
4. **Result**:
   - Single-solver mode: Selected solver's schedule table, station status, load profile chart, cost breakdown, and quantum resources (if QAOA). Empty comparison blocks omitted.
   - Multi-solver mode: Individual charging schedule tables for each solver, comparative grid load chart, comparative metrics table, and quantum resources card.
5. **Compare**: Multi-solver comparison table and comparative objective/runtime bars across completed runs.
6. **Scaling & Resources**: Empirical scaling ladder across instance dimensions.

## Backend API

| Endpoint | Method | Behavior |
| --- | --- | --- |
| `/api/health` | GET | Returns local engine status and primary solver declaration. |
| `/api/presets` | GET | Returns fixture presets and baseline provenance. |
| `/api/instances` | POST | Validates bounded limits (max 8 EVs, 5 stations, 8 slots; returns 400 if exceeded), stores instance, computes exact QUBO variable count. |
| `/api/instances/<id>` | GET | Returns stored instance, otherwise baseline. |
| `/api/instances/<id>/runs` | POST | Dispatches multi-solver (`solvers: [...]`) or single-solver (`solver: "..."`) optimization pipeline on the common QUBO; returns decoded runs payload. |
| `/api/runs/<id>` | GET | Returns stored run result. |
| `/api/results/baseline` | GET | Returns fixed reference solution and provenance. |
| `/api/instances/<id>/compare` | GET | Runs Simulated Annealing, QAOA, and Exact Enumeration on the same QUBO. |
| `/api/results/ladder` | GET | Returns empirical scaling ladder rows. |

## Data Structures

- **Instance**: `id`, `name`, `n_ev`, `n_st`, `n_t`, `demand`, `window`, `price`, `grid_cap`, `open_cost`, `detour`, `stress_w`, `n_qubits`, `seed`.
- **Decoded Solution**: `bitstring`, `stations_open`, `assignments` / `schedule` (`ev`, `station`, `slot`, `demand`, `detour_cost`, `electricity_price`), `load`, `feasible`, `violations`, `objective`, `cost_breakdown` (`electricity`, `detour`, `infrastructure`, `grid_stress`).
- **Multi-Run Payload**: `run_id`, `instance_id`, `is_multi`, `solvers_requested`, `qubo_vars`, `results` (map of solver keys to run dicts), `comparison` (`has_comparison`, `rows`), `provenance`.
