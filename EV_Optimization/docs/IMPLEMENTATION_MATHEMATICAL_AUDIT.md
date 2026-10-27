# Implementation & Mathematical Audit: EV Coupled Optimization Engine

**Document Status:** Complete Read-Only Audit  
**Date of Audit:** October 7, 2026  
**Auditor:** Antigravity Advanced Agentic Coding Engine  
**Project Workspace:** `c:\Users\LOQ\Desktop\Quantum_2k26\project_1-10-2026`  
**Target Output File:** `docs/IMPLEMENTATION_MATHEMATICAL_AUDIT.md`  

---

## Executive Summary & Scope

This audit provides an exhaustive, faithful, line-by-line inspection of the mathematical models, algorithms, data structures, variables, constraints, QUBO/Ising transformations, solvers (Simulated Annealing, Exact Enumeration, QAOA), decoders, resource estimators, and frontend APIs implemented in the codebase.

### Core Principle of this Audit
* The **source code is the sole source of truth**.
* Theoretical expectations and textbook formulations are omitted unless explicitly confirmed by the implementation.
* Any unconfirmed, missing, dead, or ambiguous features are documented as **NOT DETERMINED FROM CURRENT IMPLEMENTATION** or **NOT IMPLEMENTED**.
* **Zero code modifications** were introduced during this investigation.

---

## 1. Actual Project Inventory

The repository consists of 33 active project files organized across five functional directories:

```text
project_1-10-2026/
├── evcore/                          Core mathematical & algorithmic optimization engine
│   ├── __init__.py                  Module exports
│   ├── qubo.py                      Instance normalization, QUBO compilation, Ising transformation
│   ├── decoder.py                   Solution decoder, feasibility validator, physical objective & cost calculation
│   ├── solver_sa.py                 Primary classical solver (Simulated Annealing on QUBO)
│   ├── qaoa_solver.py               Quantum/hybrid QAOA solver (Qiskit Aer simulator, circuit metrics)
│   ├── exact_solver.py              Small-instance Exact Enumeration ground-truth solver (Gray code)
│   ├── qaoa_resources.py            Quantum resource estimator & target Heavy-Hex transpiler
│   ├── pipeline.py                  End-to-end multi-solver dispatch pipeline & comparison evaluator
│   ├── ibm_demo_data.py             Curated 6-instance experimental dataset & hardware execution stub
│   └── mock.py                      Baseline reference fixture, presets, and legacy mock solutions
├── server/                          Backend Flask web server & static asset host
│   ├── __init__.py                  Package initializer
│   ├── __main__.py                  Server startup script (`python -m server`)
│   ├── app.py                       REST API routing, request validation, bounded limits, solver dispatch
│   └── static/
│       ├── index.html               Single-page application dashboard layout (6 tabs)
│       ├── app.js                   Frontend state management, solver controls, SVG chart renderers
│       └── styles.css               Application stylesheet, badge classes, layout grids
├── tests/                           Automated test suites (34 tests across 6 files)
│   ├── test_api.py                  API endpoint and custom problem creation tests (11 tests)
│   ├── test_classical_sa.py         Simulated Annealing solver, budget, and pipeline tests (5 tests)
│   ├── test_qubo_and_exact.py       QUBO compilation, Ising consistency, Exact solver tests (5 tests)
│   ├── test_qaoa.py                 QAOA Aer execution, unitary equivalence, bitstring ordering (4 tests)
│   ├── test_scaling_and_estimate.py Scaling dataset, memory formatting, hardware endpoints (10 tests)
│   └── test_live_server_frontend.py Live server HTML integrity and API validation (acceptance test)
├── docs/                            Project documentation
│   ├── ARCHITECTURE.md              Architecture specification
│   ├── CHANGELOG.md                 Chronological change history
│   ├── DECISIONS.md                 Design decisions and constraints log
│   ├── PROJECT_PROGRESS.md          Progress tracking against milestones
│   ├── README.md                    Project overview
│   ├── TODO.md                      Parked tasks and backlog
│   └── IMPLEMENTATION_MATHEMATICAL_AUDIT.md  This audit document
├── diagnose_qaoa_sampling.py        Diagnostic script for QAOA sampling distribution on baseline
├── run_control_experiments.py       Control experiments comparing QAOA depths and shot counts
├── run_tests.py                     Universal test runner script
├── requirements.txt                 Runtime dependencies (Flask, NumPy, SciPy, Qiskit, Qiskit-Aer)
└── verify_scenarios.py              End-to-end scenario verification script (Tests A–E)
```

### Module Breakdown

| File Path | Purpose | Key Classes | Key Functions | Direct Dependencies |
|---|---|---|---|---|
| `evcore/qubo.py` | QUBO matrix compilation & Ising conversion | `QUBOModel` | `normalize_instance`, `evaluate_energy`, `to_ising`, `_build_variable_index`, `_build_matrix` | `numpy` |
| `evcore/decoder.py` | Translates bitstrings to physical decisions, validates constraints, computes true physical objective | None | `decode_solution` | `numpy`, `evcore.qubo` |
| `evcore/solver_sa.py` | Primary classical heuristic QUBO solver | `SimulatedAnnealingSolver` | `solve` | `numpy`, `math`, `time`, `evcore.qubo` |
| `evcore/qaoa_solver.py` | Variational quantum optimization on Qiskit Aer | `QAOASolver` | `solve`, `_qubo_to_ising` | `qiskit`, `qiskit_aer`, `scipy.optimize`, `numpy`, `evcore.qubo`, `evcore.decoder` |
| `evcore/exact_solver.py` | Global ground-truth validation for small instances | `ExactEnumerationSolver` | `solve`, `is_tractable`, `calculate_optimality_gap` | `numpy`, `time`, `evcore.qubo` |
| `evcore/qaoa_resources.py` | Computes circuit metrics, statevector memory, Heavy-Hex transpilation | None | `estimate_qaoa_resources`, `format_memory_bytes`, `_get_classification_metadata` | `qiskit`, `numpy`, `evcore.qubo` |
| `evcore/pipeline.py` | Unified execution harness across solvers on common QUBO | None | `run_optimization_pipeline`, `run_multi_solver_pipeline`, `compare_solvers_for_instance` | `evcore.qubo`, `evcore.solver_sa`, `evcore.exact_solver`, `evcore.qaoa_solver`, `evcore.decoder` |
| `evcore/ibm_demo_data.py` | Curated experimental benchmark instances and fallback execution stub | None | `get_ibm_scaling_data`, `execute_ibm_hardware_problem`, `_build_dataset` | `evcore.qubo`, `evcore.decoder`, `evcore.mock` |
| `evcore/mock.py` | Reference data fixtures | None | `result` | `copy`, `datetime` |
| `server/app.py` | Flask REST API controller | `app` | `health`, `presets`, `create_instance`, `create_run`, `compare`, `ibm_scaling_demo`, `estimate_resources_endpoint`, `ibm_execute_endpoint` | `flask`, `evcore.pipeline`, `evcore.qubo`, `evcore.qaoa_resources`, `evcore.ibm_demo_data` |
| `server/static/app.js` | Frontend controller & DOM renderer | None | `initialize`, `renderSetup`, `updateModelTab`, `updateSolverAvailability`, `renderResults`, `loadIbmScalingData`, `runIbmHardwareProblem`, `runEstimation` | Vanilla JS / DOM APIs |

---

## 2. Reconstructed Execution Pipelines

The codebase supports six distinct execution pathways:

```text
Path 1: Primary Classical (Simulated Annealing)
Problem Input → normalize_instance() → QUBOModel() → SimulatedAnnealingSolver.solve() 
              → best_bitstring → decode_solution() → Feasibility Validation → Physical Costs

Path 2: Small-Instance Validation (Exact Enumeration)
Problem Input → normalize_instance() → QUBOModel() → ExactEnumerationSolver.solve() [if N <= 20]
              → optimum_bitstring → decode_solution() → Ground Truth Baseline

Path 3: Quantum / Hybrid QAOA (Qiskit Aer)
Problem Input → normalize_instance() → QUBOModel() → model.to_ising() → QAOASolver.solve() [guard: N <= 24]
              → COBYLA parameter loop on AerSimulator → sampled bitstrings → minimum QUBO energy bitstring
              → decode_solution() → Feasibility Validation → Physical Costs

Path 4: Multi-Solver Comparison Pipeline
Problem Input → normalize_instance() → QUBOModel() (Single formulation instance)
              → Ground truth check (if N <= 20)
              → Dispatch to requested solvers in parallel loop
              → Common decode_solution() for each returned bitstring
              → Unified comparison matrix and optimality gap calculation

Path 5: Quantum Resource Estimation (No Optimization Run)
Problem Input → normalize_instance() → QUBOModel() → model.to_ising()
              → If N > 127: Analytical symbolic scaling
              → If N <= 127: Synthesize QuantumCircuit(N, p) → Aer basis transpile → Heavy-Hex CouplingMap transpile
              → Output circuit depth, gate counts, physical qubits required, statevector memory string

Path 6: IBM Quantum Hardware Demonstration / Benchmark
Problem Selector → Curated instance definition → POST /api/ibm/execute
                 → Check live token (IBMQ_TOKEN / QISKIT_IBM_TOKEN) with 2.0s timeout
                 → If absent or timed out: Retrieve verified precomputed hardware benchmark
                 → Common decode_solution() → Common Results visualizer
```

### Implementation Status Matrix

| Pipeline Path | Implemented | Connected to UI | Mock / Placeholder / Precomputed | Notes |
|---|---|---|---|---|
| Simulated Annealing | **YES** | **YES** | Real heuristic solver | Fully generic for baseline & custom instances |
| Exact Enumeration | **YES** | **YES** | Real exact solver | Safety capped at $N \le 20$ binary variables |
| Qiskit Aer QAOA | **YES** | **YES** | Real simulator | Safety capped at $N \le 24$ logical qubits |
| Multi-Solver Orchestrator | **YES** | **YES** | Real orchestration | Dispatches to common `QUBOModel` instance |
| Resource Estimator | **YES** | **YES** | Circuit derivation / analytical | Analyzes circuits up to $N=127$; analytical beyond |
| IBM Live Hardware Execution | **PARTIAL** | **YES** | Precomputed fallback | Live token check present; falls back to precomputed data |
| Legacy Ladder Endpoint (`/api/results/ladder`) | **YES** | **NO** | Hardcoded static list | Unused in current dashboard UI |
| Legacy Mock Baseline (`/api/results/baseline`) | **YES** | **NO** | Static fixture in `mock.py` | Replaced by live SA solver runs |

---

## 3. Actual Data Structures

### 3.1 Problem Instance Structure

Created in: `server/app.py`, `evcore/mock.py`, `server/static/app.js` (`makeCustomProblem`)  
Normalized in: `evcore/qubo.py` (`normalize_instance`)  
Consumed in: `QUBOModel`, `decode_solution`, `estimate_qaoa_resources`

```python
{
    "id": str,                  # Instance identifier (e.g., "baseline-3x2x4", "custom-local")
    "name": str,                # Display name
    "n_ev": int,                # Number of electric vehicles (1 to 8)
    "n_st": int,                # Number of candidate charging stations (1 to 5)
    "n_t": int,                 # Number of discrete scheduling time slots (1 to 8)
    "demand": List[int],        # Charging slots required per EV [d_0, d_1, ...], len = n_ev, d_e >= 1
    "window": List[List[int]],  # Allowed time slots per EV [[0, 1], [1, 2, 3], ...], sorted unique integers in [0, n_t - 1]
    "price": List[float],       # Electricity price per time slot [$ / kWh], len = n_t
    "grid_cap": List[int],      # Substation capacity limit (maximum concurrent EVs) per time slot, len = n_t
    "open_cost": List[float],   # Capital infrastructure opening cost per station, len = n_st
    "detour": List[List[float]],# Travel / detour penalty matrix [n_ev][n_st], float >= 0.0
    "stress_w": float,          # Grid stress weight coefficient (default: 0.25)
    "seed": int,                # PRNG seed (default: 42)
    "n_qubits": int             # Optional cached QUBO variable count
}
```

### 3.2 QUBO Model Internal Representation

Created in: `evcore/qubo.py` (`QUBOModel.__init__`)  
Consumed in: Solvers, Decoder, Estimator

* `self.var_names`: `List[str]`, length $N$. Format: `"y_{s}"` or `"x_{e}_{s}_{t}"`.
* `self.var_map`: `Dict[str, int]`, maps variable name to integer index $0 \le i < N$.
* `self.var_meta`: `List[Dict[str, Any]]`, metadata for index $i$:
  * Station variable: `{"type": "station", "station": s}`
  * Charging variable: `{"type": "assignment", "ev": e, "station": s, "slot": t}`
* `self.Q`: `np.ndarray` of shape $(N, N)$, dtype `float64`. Upper-triangular convention ($Q_{ij} = 0$ for $i > j$).
* `self.offset`: `float`, scalar constant offset accumulated from expanded constraint square terms.
* `self.Q_sym`: `np.ndarray` of shape $(N, N)$, symmetric matrix: $Q_{\text{sym}} = \frac{1}{2}(Q + Q^T)$.

### 3.3 Decoded Solution Representation

Created in: `evcore/decoder.py` (`decode_solution`)  
Consumed in: Pipeline runners, comparison builders, frontend renderers

```python
{
    "bitstring": str,           # Binary solution string, length N (e.g., "1110000000010100010000")
    "stations_open": List[bool],# Length n_st, True if station s is opened (y_s = 1)
    "assignments": List[Dict],  # Active assignments (x_{e,s,t} = 1)
                                # Dict keys: "ev", "station", "slot", "demand", "detour_cost", "electricity_price"
    "schedule": List[Dict],     # Alias to assignments
    "load": List[int],          # Length n_t, concurrent EV count charging at slot t
    "feasible": bool,           # True iff len(violations) == 0
    "violations": List[str],    # List of human-readable constraint violation messages
    "objective": float,         # True physical objective (excluding penalty values) rounded to 4 decimals
    "cost_breakdown": {
        "electricity": float,   # sum_t price[t] * load[t]
        "detour": float,        # sum_{e, s} detour[e][s]
        "infrastructure": float,# sum_s open_cost[s] * y_s
        "grid_stress": float    # stress_w * sum_t (load[t])^2
    }
}
```

---

## 4. Actual Optimization Variables

Every optimization variable in the formulation is binary ($\{0, 1\}$). **No auxiliary variables, slack variables, continuous variables, or integer expansion bits exist.**

| Mathematical Symbol | Code Name | Meaning | Domain | Indices | Range | Variable Count |
|---|---|---|---|---|---|---|
| $y_s$ | `y_{s}` | Station siting decision (1 = station $s$ is opened, 0 = closed) | $\{0, 1\}$ | $s$ | $s \in \{0, \dots, n_{st} - 1\}$ | $n_{st}$ |
| $x_{e,s,t}$ | `x_{e}_{s}_{t}` | EV charging assignment (1 = EV $e$ charges at station $s$ during time slot $t$) | $\{0, 1\}$ | $e, s, t$ | $e \in \{0, \dots, n_{ev}-1\}$, $s \in \{0, \dots, n_{st}-1\}$, $t \in W_e$ | $\sum_{e=0}^{n_{ev}-1} n_{st} \cdot \|W_e\|$ |

### Critical Finding on Variable Domains
Variables $x_{e,s,t}$ are **only instantiated for allowed time slots** $t \in W_e$. If $t \notin W_e$, no decision variable is created; the choice is pruned *a priori* during variable index construction rather than penalized in the QUBO.

---

## 5. Exact Variable Indexing

The mapping from variable names to integer QUBO indices $0 \le i < N$ is deterministic, contiguous, 0-indexed, and constructed by `QUBOModel._build_variable_index`:

### Loop Order
1. **Station variables ($y_s$) first**:
   ```python
   for s in range(n_st):
       # index = s
   ```
2. **Charging variables ($x_{e,s,t}$) second**, in outer-to-inner loop order:
   ```python
   for e in range(n_ev):
       for s in range(n_st):
           for t in window[e]:
               # index = next contiguous integer
   ```

### Concrete Mapping for Baseline Instance (3 EVs, 2 Stations, 4 Slots, 22 Variables)

* $W_0 = \{0, 1, 2\}$ (length 3)
* $W_1 = \{1, 2, 3\}$ (length 3)
* $W_2 = \{0, 1, 2, 3\}$ (length 4)

| QUBO Index $i$ | Variable Code Name | Mathematical Symbol | Domain Meaning |
|---|---|---|---|
| `0` | `y_0` | $y_0$ | Station 1 Open/Closed |
| `1` | `y_1` | $y_1$ | Station 2 Open/Closed |
| `2` | `x_0_0_0` | $x_{0,0,0}$ | EV 1 at Station 1 at Slot 1 |
| `3` | `x_0_0_1` | $x_{0,0,1}$ | EV 1 at Station 1 at Slot 2 |
| `4` | `x_0_0_2` | $x_{0,0,2}$ | EV 1 at Station 1 at Slot 3 |
| `5` | `x_0_1_0` | $x_{0,1,0}$ | EV 1 at Station 2 at Slot 1 |
| `6` | `x_0_1_1` | $x_{0,1,1}$ | EV 1 at Station 2 at Slot 2 |
| `7` | `x_0_1_2` | $x_{0,1,2}$ | EV 1 at Station 2 at Slot 3 |
| `8` | `x_1_0_1` | $x_{1,0,1}$ | EV 2 at Station 1 at Slot 2 |
| `9` | `x_1_0_2` | $x_{1,0,2}$ | EV 2 at Station 1 at Slot 3 |
| `10` | `x_1_0_3` | $x_{1,0,3}$ | EV 2 at Station 1 at Slot 4 |
| `11` | `x_1_1_1` | $x_{1,1,1}$ | EV 2 at Station 2 at Slot 2 |
| `12` | `x_1_1_2` | $x_{1,1,2}$ | EV 2 at Station 2 at Slot 3 |
| `13` | `x_1_1_3` | $x_{1,1,3}$ | EV 2 at Station 2 at Slot 4 |
| `14` | `x_2_0_0` | $x_{2,0,0}$ | EV 3 at Station 1 at Slot 1 |
| `15` | `x_2_0_1` | $x_{2,0,1}$ | EV 3 at Station 1 at Slot 2 |
| `16` | `x_2_0_2` | $x_{2,0,2}$ | EV 3 at Station 1 at Slot 3 |
| `17` | `x_2_0_3` | $x_{2,0,3}$ | EV 3 at Station 1 at Slot 4 |
| `18` | `x_2_1_0` | $x_{2,1,0}$ | EV 3 at Station 2 at Slot 1 |
| `19` | `x_2_1_1` | $x_{2,1,1}$ | EV 3 at Station 2 at Slot 2 |
| `20` | `x_2_1_2` | $x_{2,1,2}$ | EV 3 at Station 2 at Slot 3 |
| `21` | `x_2_1_3` | $x_{2,1,3}$ | EV 3 at Station 2 at Slot 4 |

---

## 6. Actual Variable Count Formula

The exact formula implemented across `evcore/qubo.py`, `evcore/pipeline.py`, and `server/static/app.js` is:

$$N = n_{st} + \sum_{e=0}^{n_{ev}-1} \left( n_{st} \cdot |W_e| \right) = n_{st} \left( 1 + \sum_{e=0}^{n_{ev}-1} |W_e| \right)$$

Where:
* $n_{st}$: Candidate station count.
* $n_{ev}$: EV count.
* $|W_e|$: Number of allowed time slots in the charging window of vehicle $e$ ($|W_e| \le n_t$).

### Special Cases
* **Full Window ($W_e = \{0, \dots, n_t - 1\}$ for all $e$)**:
  $$N_{\text{full}} = n_{st} + n_{ev} \cdot n_{st} \cdot n_t = n_{st} (1 + n_{ev} n_t)$$
* **Unrestricted 2×2×2 instance**: $N = 2 + 2 \cdot 2 \cdot 2 = 10$ binary variables.
* **Restricted 2×2×2 instance ($|W_0|=1, |W_1|=1$)**: $N = 2 + 2(1 + 1) = 6$ binary variables.
* **Baseline (3×2×4, $|W_0|=3, |W_1|=3, |W_2|=4$)**: $N = 2 + 2(3 + 3 + 4) = 22$ binary variables.

---

## 7. Problem Parameters Inventory

| Parameter | Symbol | Type | Default Value | Code Location | Usage |
|---|---|---|---|---|---|
| Number of EVs | $n_{ev}$ | `int` | `3` | `qubo.py:19` | Dimension bound (max 8) |
| Number of Stations | $n_{st}$ | `int` | `2` | `qubo.py:20` | Dimension bound (max 5) |
| Number of Time Slots | $n_t$ | `int` | `4` | `qubo.py:21` | Dimension bound (max 8) |
| Energy Demand | $d_e$ | `List[int]` | `[1] * n_ev` | `qubo.py:26` | Required charging slots per EV |
| Time Windows | $W_e$ | `List[List[int]]` | `[range(n_t)]` | `qubo.py:34` | Allowed charging slots per EV |
| Electricity Price | $p_t$ | `List[float]` | `[1.0] * n_t` | `qubo.py:39` | Cost per slot per charging EV |
| Grid Substation Capacity | $G_t$ | `List[int]` | `[n_ev] * n_t` | `qubo.py:44` | Maximum allowable concurrent charging load |
| Station Opening Cost | $O_s$ | `List[float]` | `[1.0] * n_st` | `qubo.py:49` | Fixed capital cost to open station $s$ |
| Detour / Travel Cost | $D_{es}$ | `List[List[float]]` | `[[0.0]*n_st]` | `qubo.py:57` | Travel penalty for vehicle $e$ to station $s$ |
| Grid Stress Weight | $w_{\text{stress}}$ | `float` | `0.25` | `qubo.py:59` | Weight of quadratic load penalty |
| PRNG Seed | `seed` | `int` | `42` | `qubo.py:60` | Solver reproducibility |
| Demand Penalty Weight | $\lambda_{\text{demand}}$ | `float` | `20.0` | `qubo.py:84` | Multiplier for demand violation |
| Coupling Penalty Weight | $\lambda_{\text{coupling}}$ | `float` | `15.0` | `qubo.py:85` | Multiplier for un-opened station usage |
| Conflict Penalty Weight | $\lambda_{\text{conflict}}$ | `float` | `20.0` | `qubo.py:86` | Multiplier for simultaneous EV/station conflicts |
| Grid Capacity Penalty Weight | $\lambda_{\text{grid}}$ | `float` | `20.0` | `qubo.py:87` | Multiplier for grid limit exceedance (applied when $G_t = 1$) |

---

## 8. Exact Objective Function

The total optimization objective minimized by the system contains four physical cost components:

$$f_{\text{physical}}(y, x) = C_{\text{infra}}(y) + C_{\text{elec}}(x) + C_{\text{detour}}(x) + C_{\text{stress}}(x)$$

### 1. Infrastructure Cost
$$C_{\text{infra}}(y) = \sum_{s=0}^{n_{st}-1} O_s y_s$$
* Source: `qubo.py:153-155`, `decoder.py:148-150`
* Variables: $y_s$ linear diagonal terms.

### 2. Electricity Consumption Cost
$$C_{\text{elec}}(x) = \sum_{e=0}^{n_{ev}-1} \sum_{s=0}^{n_{st}-1} \sum_{t \in W_e} p_t x_{e,s,t}$$
* Source: `qubo.py:161-165`, `decoder.py:146`
* Variables: $x_{e,s,t}$ linear diagonal terms.

### 3. Detour / Travel Cost
$$C_{\text{detour}}(x) = \sum_{e=0}^{n_{ev}-1} \sum_{s=0}^{n_{st}-1} \sum_{t \in W_e} D_{es} x_{e,s,t}$$
* Source: `qubo.py:161-165`, `decoder.py:147`
* Variables: $x_{e,s,t}$ linear diagonal terms.

### 4. Grid Stress Cost
$$C_{\text{stress}}(x) = w_{\text{stress}} \sum_{t=0}^{n_t-1} \left( L_t \right)^2 = w_{\text{stress}} \sum_{t=0}^{n_t-1} \left( \sum_{e: t \in W_e} \sum_{s=0}^{n_{st}-1} x_{e,s,t} \right)^2$$
* Source: `qubo.py:172-185`, `decoder.py:151`
* Expanded in binary quadratic form:
  $$\left( \sum_i x_i \right)^2 = \sum_i x_i^2 + 2 \sum_{i < j} x_i x_j = \sum_i x_i + 2 \sum_{i < j} x_i x_j$$
  Yields:
  * Diagonal: $Q_{ii} \mathrel{+}= w_{\text{stress}}$
  * Off-diagonal: $Q_{ij} \mathrel{+}= 2 w_{\text{stress}}$ for all charging variable pairs active at the same time slot $t$.

---

## 9. Grid Stress vs. Grid Capacity Implementation

A critical architectural distinction exists between **Grid Stress** and **Grid Capacity**:

| Property | Grid Stress ($C_{\text{stress}}$) | Grid Capacity Limit ($G_t$) |
|---|---|---|
| Nature | Soft quadratic objective penalty | Physical system constraint |
| Equation | $w_{\text{stress}} \sum_t L_t^2$ | $L_t \le G_t \quad \forall t$ |
| Parameter | `stress_w` (default 0.25) | `grid_cap` (default $[2, 1, 1, 2]$ in baseline) |
| Decoder Role | Always added to physical objective | Checked in `decoder.py:135-139`: if $L_t > G_t$, marks solution as infeasible |
| QUBO Role | Contributes $+w_{\text{stress}}$ to diagonals and $+2w_{\text{stress}}$ to off-diagonals across all concurrent slots | **Conditional:** In `qubo.py:263-269`, penalty $\lambda_{\text{grid}}$ is ONLY applied if $G_t == 1$. If $G_t > 1$, no hard quadratic penalty is added to $Q$. |

---

## 10. All Constraints: Equations, Enforcement & Penalties

| # | Constraint Name | Mathematical Expression | Variables | Enforcement Mechanism | Penalty Multiplier | Source Location |
|---|---|---|---|---|---|---|
| 1 | EV Demand Satisfaction | $\sum_{s} \sum_{t \in W_e} x_{e,s,t} = d_e \quad \forall e$ | $x_{e,s,t}$ | QUBO Penalty Term + Decoder Validation | $\lambda_{\text{demand}} = 20.0$ | `qubo.py:190-204`, `decoder.py:85-93` |
| 2 | Allowed Time Windows | $x_{e,s,t} = 0 \quad \forall t \notin W_e$ | $x_{e,s,t}$ | *A priori* variable elimination (never instantiated) + Decoder check | None (pruned) | `qubo.py:124`, `decoder.py:96-100` |
| 3 | Station Opening Coupling | $x_{e,s,t} \le y_s \iff x_{e,s,t}(1 - y_s) = 0$ | $x_{e,s,t}, y_s$ | QUBO Penalty Term + Decoder Validation | $\lambda_{\text{coupling}} = 15.0$ | `qubo.py:210-218`, `decoder.py:123-127` |
| 4 | Simultaneous Charging Prevention | $\sum_{s=0}^{n_{st}-1} x_{e,s,t} \le 1 \quad \forall e, t$ | $x_{e,s,t}$ | QUBO Penalty Term + Decoder Validation | $\lambda_{\text{conflict}} = 20.0$ | `qubo.py:224-232`, `decoder.py:103-110` |
| 5 | Station Charger Capacity | $\sum_{e=0}^{n_{ev}-1} x_{e,s,t} \le 1 \quad \forall s, t$ | $x_{e,s,t}$ | QUBO Penalty Term + Decoder Validation | $\lambda_{\text{conflict}} = 20.0$ | `qubo.py:237-250`, `decoder.py:113-120` |
| 6 | Grid Substation Capacity | $\sum_{e} \sum_{s} x_{e,s,t} \le G_t \quad \forall t$ | $x_{e,s,t}$ | QUBO Penalty (if $G_t=1$) + Decoder Validation | $\lambda_{\text{grid}} = 20.0$ | `qubo.py:255-270`, `decoder.py:135-140` |

### Detailed Expansion of QUBO Penalties

#### Demand Satisfaction Penalty
$$\lambda_{\text{demand}} \left( \sum_{s} \sum_{t \in W_e} x_{e,s,t} - d_e \right)^2$$
Expanded:
* Offset: $\text{offset} \mathrel{+}= \lambda_{\text{demand}} d_e^2$
* Diagonal: $Q_{ii} \mathrel{+}= \lambda_{\text{demand}} (1 - 2 d_e)$
* Off-diagonal: $Q_{ij} \mathrel{+}= 2 \lambda_{\text{demand}}$ for all pairs belonging to the same EV $e$.

#### Station Coupling Penalty
$$\lambda_{\text{coupling}} \left( x_{e,s,t} - x_{e,s,t} y_s \right)$$
* Diagonal of $x_{e,s,t}$: $Q_{xx} \mathrel{+}= \lambda_{\text{coupling}}$
* Off-diagonal between $x_{e,s,t}$ and $y_s$: $Q_{xy} \mathrel{-}= \lambda_{\text{coupling}}$ (where row $< $ col).

#### Simultaneous Charging & Charger Capacity Conflicts
$$\lambda_{\text{conflict}} \sum_{s_1 < s_2} x_{e,s_1,t} x_{e,s_2,t} \quad \text{and} \quad \lambda_{\text{conflict}} \sum_{e_1 < e_2} x_{e_1,s,t} x_{e_2,s,t}$$
* Off-diagonal: $Q_{ij} \mathrel{+}= \lambda_{\text{conflict}}$.

---

## 11. QUBO Construction Details

* **Storage Format:** NumPy 2D array `self.Q` of size $N \times N$, upper-triangular storage ($i \le j$).
* **Constant Offset:** `self.offset` float scalar.
* **Energy Evaluation:**
  $$E_{\text{QUBO}}(z) = z^T Q z + \text{offset} = \sum_{i=0}^{N-1} Q_{ii} z_i + \sum_{0 \le i < j < N} Q_{ij} z_i z_j + \text{offset}$$
* **Symmetric Matrix:**
  $$Q_{\text{sym}} = \frac{1}{2}(Q + Q^T)$$
  Allows quadratic evaluations via matrix-vector multiplication $z^T Q_{\text{sym}} z$.

---

## 12. QUBO Sparsity & Interaction Graph Structure

The off-diagonal coupling terms $Q_{ij} \neq 0$ ($i < j$) define the QUBO interaction graph:

| Interaction Category | Variable Pair | Coupling Coefficient $Q_{ij}$ ($i < j$) | Generating Mechanism | Scaling Behavior |
|---|---|---|---|---|
| Station ↔ Station | $y_{s_1} \leftrightarrow y_{s_2}$ | **0 (Always zero)** | None (stations do not directly couple) | 0 terms |
| Station ↔ Charging | $y_s \leftrightarrow x_{e,s,t}$ | $-\lambda_{\text{coupling}} = -15.0$ | Station-opening coupling | Exactly $\sum_e \|W_e\| \cdot n_{st}$ terms |
| Same EV, Different Slots/Stations | $x_{e,s_1,t_1} \leftrightarrow x_{e,s_2,t_2}$ | $+2\lambda_{\text{demand}} = +40.0$ | Demand expansion cross-terms | $\sum_e \binom{n_{st} \|W_e\|}{2}$ terms |
| Same EV, Same Slot, Different Stations | $x_{e,s_1,t} \leftrightarrow x_{e,s_2,t}$ | $+2\lambda_{\text{demand}} + \lambda_{\text{conflict}} + 2w_{\text{stress}} = +60.5$ | Demand + Simultaneous conflict + Grid stress | $\sum_e \|W_e\| \binom{n_{st}}{2}$ terms |
| Different EVs, Same Station, Same Slot | $x_{e_1,s,t} \leftrightarrow x_{e_2,s,t}$ | $\lambda_{\text{conflict}} + 2w_{\text{stress}} (+ \lambda_{\text{grid}}) = +20.5$ (or $+40.5$) | Charger capacity + Grid stress (+ Grid cap) | $\sum_{s, t} \binom{\text{EVs active at } t}{2}$ terms |
| Different EVs, Different Stations, Same Slot | $x_{e_1,s_1,t} \leftrightarrow x_{e_2,s_2,t}$ | $+2w_{\text{stress}} (+ \lambda_{\text{grid}}) = +0.5$ (or $+20.5$) | Grid stress (+ Grid cap if $G_t=1$) | Varies with window overlaps |
| Different EVs, Different Slots | $x_{e_1,s_1,t_1} \leftrightarrow x_{e_2,s_2,t_2}$ | **0 (Always zero)** | Independent time slots | 0 terms |

### Sparsity Density Finding
Because different EVs only interact when their time windows overlap at the **exact same time slot** $t$, the QUBO matrix exhibits a **block-banded sparsity pattern** organized by time slots, coupled globally only by the station variables $y_s$ and EV-level demand constraints.

---

## 13. QUBO to Ising Transformation

Implemented in `evcore/qubo.py:276-301` (`QUBOModel.to_ising`) and `evcore/qaoa_solver.py:289-298`:

### Transformation Mapping
$$z_i = \frac{1 - s_i}{2}, \quad s_i \in \{-1, +1\}$$
Substituting into $z^T Q_{\text{sym}} z + \text{offset}$:

### 1. Quadratic Coupling Matrix $J$ (Symmetric, Zero Diagonal)
$$J_{ij} = \frac{1}{4} Q_{\text{sym}, ij} \quad (i \neq j), \quad J_{ii} = 0$$

### 2. Linear Magnetic Field Vector $h$
$$h_i = -\frac{1}{2} \sum_{j=0}^{N-1} Q_{\text{sym}, ij}$$

### 3. Constant Energy Shift $c_{\text{ising}}$
$$c_{\text{ising}} = \text{offset} + \frac{1}{4} \sum_{i=0}^{N-1} \sum_{j=0}^{N-1} Q_{\text{sym}, ij} + \frac{1}{4} \text{Tr}(Q_{\text{sym}})$$

*Verified in test suite:* `test_qubo_ising_energy_consistency` confirms that for any binary state $z \in \{0, 1\}^N$ and corresponding spin configuration $s = 1 - 2z \in \{-1, 1\}^N$:
$$\left| E_{\text{QUBO}}(z) - \left( s^T J s + h^T s + c_{\text{ising}} \right) \right| < 10^{-10}$$

---

## 14. Simulated Annealing (SA) Solver Audit

Implemented in `evcore/solver_sa.py` (`SimulatedAnnealingSolver`):

* **Initial State:** Uniformly random bitstring $z \in \{0, 1\}^N$ via `np.random.RandomState(seed).randint(0, 2, size=n_vars)`.
* **Restarts:** Configurable independent restarts (`restarts`, default 5 or 8).
* **Step Generation:** Single bit flip at each step: index $i \sim \text{Uniform}(0, N-1)$.
* **Incremental Delta Energy Evaluation ($O(N)$ running field):**
  Maintains running vector $h_i = \sum_j Q_{\text{sym}, ij} z_j$.
  * If flipping $0 \to 1$: $\Delta E = Q_{\text{sym}, ii} + 2 h_i$
  * If flipping $1 \to 0$: $\Delta E = Q_{\text{sym}, ii} - 2 h_i$
  * If accepted: $z_i \leftarrow 1 - z_i$, $E \leftarrow E + \Delta E$, $h \leftarrow h + Q_{\text{sym}}[:, i] \cdot \Delta z_i$.
  * Avoids $O(N^2)$ matrix-vector product per iteration.
* **Acceptance Rule (Metropolis-Hastings):**
  * If $\Delta E \le 0$: Accepted unconditionally.
  * If $\Delta E > 0$: Accepted if $\text{rand}() < \exp(-\Delta E / T)$ (with safety clamp $T \ge 10^{-9}$, $-\Delta E / T > -700.0$).
* **Cooling Schedules:**
  * Geometric: $T_{k+1} = T_k \cdot \left(\frac{T_f}{T_0}\right)^{1 / (M-1)}$ (default)
  * Exponential: $T_k = T_0 \exp\left(-\frac{\ln(T_0/T_f)}{M-1} k\right)$
  * Linear: $T_k = T_0 - \frac{k}{M-1}(T_0 - T_f)$
* **Local Quench:** At the end of each restart, performs up to 10 greedy zero-temperature passes flipping any bit with $\Delta E < -10^{-9}$.

---

## 15. QAOA Implementation Audit

Implemented in `evcore/qaoa_solver.py` (`QAOASolver`):

* **Ansatz Initial State:** $|+\rangle^{\otimes N} = \prod_{i=0}^{N-1} H |0\rangle_i$.
* **Cost Hamiltonian Layer ($e^{-i \gamma H_C}$):**
  * Two-qubit ZZ interaction: For all $i < j$ where $|J_{ij}| > 10^{-6}$:
    `qc.rzz(4.0 * gamma_l * J[i, j], i, j)`
  * Single-qubit Z rotation: For all $i$ where $|h_i| > 10^{-6}$:
    `qc.rz(2.0 * gamma_l * h[i], i)`
* **Mixer Hamiltonian Layer ($e^{-i \beta H_M}$):**
  * Standard transverse field mixer: $H_M = \sum_{i=0}^{N-1} X_i$.
  * For all $i$: `qc.rx(2.0 * beta_l, i)`.
* **Classical Parameter Optimizer:**
  * Optimizer: SciPy `minimize` using `COBYLA` (constrained optimization by linear approximation).
  * Initial parameters: $\gamma_0 = \dots = \gamma_{p-1} = 0.4$, $\beta_0 = \dots = \beta_{p-1} = 0.4$.
  * Objective function in optimizer: Expectation energy $\langle E \rangle = \frac{\sum_{\text{bitstring}} E(z) \cdot \text{count}}{\sum \text{count}}$ evaluated with shots capped at 512.
* **Simulation Guard:** If $N > 24$, execution is intercepted, immediately returning `status: "unsupported_size"`.

---

## 16. QAOA Scaling with Depth $p$

When depth $p$ increases from 1 to $p$:

1. **Variational Parameters:** Exactly $2p$ parameters ($\gamma_1, \dots, \gamma_p, \beta_1, \dots, \beta_p$).
2. **Cost Unitary Layers:** $p$ repetitions of the cost Hamiltonian circuit.
3. **Mixer Unitary Layers:** $p$ repetitions of the mixer layer ($N$ `rx` gates per layer).
4. **Two-Qubit Gates ($R_{zz}$):** Exactly $p \times M_{2Q}$, where $M_{2Q}$ is the number of nonzero pairs in $J$.
5. **Single-Qubit Rotations:**
   * $N$ initial Hadamard gates.
   * $p \times M_{1Q}$ `rz` gates (where $M_{1Q}$ is nonzero entries in $h$).
   * $p \times N$ `rx` gates.
6. **Total Algorithmic Gates (excluding measurements):**
   $$G_{\text{total}}(p) = N + p \cdot \left( M_{2Q} + M_{1Q} + N \right)$$

---

## 17. Bitstring Measurement & Endianness Trace

The end-to-end trace of measurement data through Qiskit and the decoder:

```text
Qiskit Aer Quantum Circuit Measurement
    ↓
counts = {'001001': 142, '100010': 85, ...}
    ↓ (Qiskit string index 0 is Qubit N-1, last index is Qubit 0)
Reversal in Python: rev_bitstr = bitstr[::-1]
    ↓ (rev_bitstr[0] corresponds to Qubit 0 = y_0; rev_bitstr[i] corresponds to Qubit i)
z = [int(c) for c in rev_bitstr]
    ↓
QUBO Energy Evaluation: E = z @ Q_sym @ z + offset
    ↓
decode_solution(rev_bitstr, model)
    ↓ (Iterates idx from 0 to N-1; if z[idx] == 1, triggers meta['type'] decision)
Physical Solution Object
```

* **Sample Definition:** One "sample" corresponds to 1 measurement shot.
* **Distinct Samples:** Number of unique bitstrings observed in `counts.keys()`.

---

## 18. Bitstring-to-Variable Mapping (Concrete 6-Qubit Example)

For instance `e2e-small-2x2x2` ($n_{ev}=2, n_{st}=2, n_t=2, W_0=[0], W_1=[1]$):
Variables: $y_0, y_1, x_{0,0,0}, x_{0,1,0}, x_{1,0,1}, x_{1,1,1}$ ($N=6$).

Suppose Qiskit outputs raw bitstring: `"100101"` (from right to left: qubit 0 is `'1'`, qubit 1 is `'0'`, ...).
1. Python reverses the string: `"101001"`.
2. Variable mapping:
   * Bit index `0`: `1` $\implies y_0 = 1$ (Station 1 Opened)
   * Bit index `1`: `0` $\implies y_1 = 0$ (Station 2 Closed)
   * Bit index `2`: `1` $\implies x_{0,0,0} = 1$ (EV 1 charges at Station 1 at Slot 1)
   * Bit index `3`: `0` $\implies x_{0,1,0} = 0$
   * Bit index `4`: `0` $\implies x_{1,0,1} = 0$
   * Bit index `5`: `1` $\implies x_{1,1,1} = 1$ (EV 2 charges at Station 2 at Slot 2)
3. Decoder checks coupling: EV 2 assigned to Station 2, but $y_1 = 0$!
   Decoder records: `"Coupling violation: EV 1 assigned to closed station 1 at slot 1"`. Solution is marked **Infeasible**.

---

## 19. Decoder Logic Trace

Implemented in `evcore/decoder.py` (`decode_solution`):

1. **Input Validation:** Verifies length matches `model.n_vars`.
2. **Assignment Extraction:**
   Iterates through bit array `z_bits`:
   * If `z_bits[i] == 1` and `var_meta[i]["type"] == "station"`: `stations_open[s] = True`.
   * If `z_bits[i] == 1` and `var_meta[i]["type"] == "assignment"`: records dictionary `{"ev": e, "station": s, "slot": t, ...}`.
3. **Load Profile Calculation:**
   Initializes `load = [0] * n_t`. For each active assignment, increments `load[a["slot"]] += 1`.
4. **Feasibility Validation:** Evaluates all 6 constraint rules.
5. **Cost Calculation:** Computes itemized breakdown and sums $f_{\text{physical}}$.

---

## 20. Decoder Validation Rules & Violation Message Formats

| Check # | Rule | Condition Triggering Violation | Exact String Format Generated |
|---|---|---|---|
| 1 | EV Demand | `ev_slots[e] != demand[e]` | `"Demand violation: EV {e} received {ev_slots[e]} slots (requires {demand[e]})"` |
| 2 | Time Window | `a["slot"] not in window[a["ev"]]` | `"Window violation: EV {a['ev']} scheduled at slot {a['slot']} outside allowed window {window[a['ev']] }"` |
| 3 | Simultaneous Charging | `count(ev, slot) > 1` | `"Simultaneous charging violation: EV {a['ev']} scheduled at multiple stations at slot {a['slot']}"` |
| 4 | Station Charger Capacity | `count(station, slot) > 1` | `"Station capacity violation: Station {a['station']} serves multiple EVs at slot {a['slot']}"` |
| 5 | Station Opening Coupling | `not stations_open[a["station"]]` | `"Coupling violation: EV {a['ev']} assigned to closed station {a['station']} at slot {a['slot']}"` |
| 6 | Grid Substation Capacity | `load[t] > grid_cap[t]` | `"Grid capacity violation: Slot {t} load {load[t]} exceeds grid limit {grid_cap[t]}"` |

*Notice:* EV indices in messages are **0-indexed** (`EV 0`, `EV 1`, `EV 2`).

---

## 21. Opened-but-Unused Station Audit

* **Is an opened station required to be used?** **NO.**
* **Does QUBO penalize an opened but unused station?** **NO penalty term exists.**
* **Does the decoder flag an unused open station as a violation?** **NO.**
* **Consequence of $y_s = 1$ and all $x_{e,s,t} = 0$:**
  The solution is **100% FEASIBLE**. The only effect is economic: it incurs the station capital opening cost $O_s$ in $C_{\text{infra}}$. If the solver finds that opening an unused station does not violate constraints, it only suffers higher physical objective.

---

## 22. QAOA Candidate Selection Logic

* **Selection Criterion:** Selected strictly by **minimum QUBO energy** across all observed measurement bitstrings (`qaoa_solver.py:202-206`):
  ```python
  for bitstr, cnt in final_counts.items():
      z = np.array([int(c) for c in bitstr[::-1]], dtype=float)
      e = float(z @ Q_sym @ z + off)
      if e < best_energy:
          best_energy = e
          best_bitstring = "".join(str(int(b)) for b in z)
  ```
* **Feasibility Filtering:** **NOT PERFORMED DURING SELECTION.** The solver does not filter for feasible solutions when returning `best_bitstring`. If the lowest energy state is infeasible, that infeasible state is returned as the final QAOA result.
* **Ties:** First-encountered minimum in Python dictionary traversal order is retained.

---

## 23. Physical Objective vs. QUBO Energy

* **Physical Objective:** Excludes all penalty weights ($\lambda_{\text{demand}}, \lambda_{\text{coupling}}, \lambda_{\text{conflict}}, \lambda_{\text{grid}}$). Represents true economic/operational cost.
* **QUBO Energy:**
  $$E_{\text{QUBO}}(z) = f_{\text{physical}}(z) + \sum_{\text{violations}} \text{Penalty}(z)$$
* **Relationship:**
  * When solution is **feasible**: All penalties are 0, so:
    $$E_{\text{QUBO}}(z) = f_{\text{physical}}(z)$$
  * When solution is **infeasible**:
    $$E_{\text{QUBO}}(z) > f_{\text{physical}}(z)$$

---

## 24. Exact Enumeration Solver Audit

* **Search Space:** Evaluates all $2^N$ states using binary Gray code.
* **Evaluation Method:** $O(1)$ scalar updates per state using running field vector $h_i$.
* **Tractability Bound:** Enforces $N \le 20$ ($2^{20} = 1,048,576$ states).
* **Ground-Truth Objective:** Guaranteed global minimum QUBO energy and global minimum feasible objective.
* **Optimality Gap Formula:**
  $$\text{Gap} = \frac{\text{Candidate Obj} - \text{Ground Truth Obj}}{|\text{Ground Truth Obj}|} \times 100\%$$

---

## 25. Result Metrics Inventory

| Metric Key | Metric Meaning | Source Solver |
|---|---|---|
| `objective` | Physical cost $C_{\text{infra}} + C_{\text{elec}} + C_{\text{detour}} + C_{\text{stress}}$ | All Solvers |
| `feasible` | Boolean feasibility indicator | All Solvers |
| `violations` | List of constraint violation strings | All Solvers |
| `cost_breakdown` | Itemized dict of 4 cost components | All Solvers |
| `evaluations` | Number of candidate states evaluated | SA (step count), Exact ($2^N$), QAOA (optimizer evals) |
| `runtime_s` | Execution duration in seconds | All Solvers |
| `optimality_gap` | Percentage gap relative to Exact ground truth | SA, QAOA (when $N \le 20$) |
| `qubo_energy` | Scalar value $z^T Q z + \text{offset}$ | All Solvers |
| `feasible_sample_count` | Number of measurement shots yielding feasible bitstrings | QAOA |
| `feasible_sample_probability` | `feasible_sample_count / shots` | QAOA |
| `distinct_samples` | Unique bitstrings measured in sampling stage | QAOA |
| `best_sample_frequency` | Shot frequency of the returned candidate | QAOA |
| `best_feasible_frequency` | Shot frequency of the best feasible state | QAOA |
| `optimal_parameters` | Dict of optimized $\gamma$ and $\beta$ angle vectors | QAOA |
| `qubits` | Active logical qubits ($N$) | QAOA, SA, Exact |
| `depth` | Algorithmic circuit depth | QAOA |
| `total_gates` | Total gate count (excluding measurements) | QAOA |
| `two_qubit_gates` | Number of $R_{zz}$ or CX operations | QAOA |
| `transpiled_depth` | Circuit depth after basis gate transpilation | QAOA |
| `transpiled_cx_gates` | CX gate count after transpilation | QAOA |
| `hamiltonian_terms` | Total Pauli terms ($1 + M_{1Q} + M_{2Q}$) | QAOA, Estimator |

---

## 26. Resource Measurement Classification

| Metric | Category | Source Location | Determination Method |
|---|---|---|---|
| Logical Qubits ($N$) | **CALCULATED** | `qubo.py:100` | `len(self.var_names)` |
| Hamiltonian Pauli Terms | **CALCULATED** | `qaoa_solver.py:84` | Nonzero entries in $J$ and $h$ + identity |
| Algorithmic QAOA Depth | **MEASURED** | `qaoa_solver.py:234` | `final_qc.depth()` on Qiskit circuit |
| Algorithmic Total Gates | **MEASURED** | `qaoa_solver.py:235` | `sum(final_qc.count_ops().values())` |
| Algorithmic 2-Qubit Gates ($R_{zz}$) | **MEASURED** | `qaoa_solver.py:236` | `final_qc.count_ops().get("rzz", 0)` |
| Heavy-Hex Transpiled Depth | **MEASURED** | `qaoa_resources.py:228` | `t_ibm.depth()` using Qiskit CouplingMap |
| Heavy-Hex Transpiled CX Gates | **MEASURED** | `qaoa_resources.py:230` | `t_ibm.count_ops().get("cx", 0)` |
| Physical Qubits Required | **MEASURED** | `qaoa_resources.py:234` | Active physical qubits in transpiled circuit |
| Device Capacity (127 / 133) | **HARDCODED** | `qaoa_resources.py:17-50` | Device architecture configuration table |
| Statevector Memory Bytes | **CALCULATED** | `qaoa_resources.py:98` | Exact formula: $16 \times 2^N$ bytes |
| Aer Simulation Feasibility Badge | **CALCULATED** | `qaoa_resources.py:106-125` | Rules: $N \le 20$ (practical), $21 \le N \le 24$ (high-memory), $N > 24$ (not practical) |
| Curated Scaling Curve Data | **PRECOMPUTED** | `ibm_demo_data.py:246-255` | Verified precomputed benchmarks across 6 instances |

---

## 27. Aer Simulation Execution Mechanics

Implemented using Qiskit Aer (`qiskit_aer.AerSimulator`):
* **Statevector Memory Demand:** Double-precision complex statevector ($2^N$ amplitudes $\times$ 16 bytes).
  * $N = 10$: 16.4 KB
  * $N = 20$: 16.8 MB
  * $N = 22$ (Baseline): 67.1 MB
  * $N = 24$: 268.4 MB
  * $N = 30$: 17.2 GB
  * $N = 62$: 73.8 EB
* **Execution Flow:**
  1. Circuit compiled into Qiskit `QuantumCircuit`.
  2. Executed via `sim.run(qc, shots=shots, seed_simulator=seed)`.
  3. Result sampled from statevector counts dictionary.
* **Computational Cost Factors:**
  * Runtime scales exponentially with $N$ ($O(2^N)$ statevector size).
  * Runtime scales linearly with depth $p$ (gate applications).
  * Runtime scales linearly with COBYLA evaluations ($N_{\text{eval}} \le \text{max\_iter}$).

---

## 28. Current Scaling & Resource Estimation Logic

1. **Estimate Resources Page (`/api/estimate-resources`):**
   * Synthesizes the exact QUBO and circuit ansatz for any arbitrary $(N_{EV}, N_{ST}, N_T)$.
   * Does **not** run classical optimization or parameter searches.
   * If $N \le 127$: Directly calls Qiskit `CouplingMap.from_heavy_hex(distance=7)` and transpile level 1 to obtain concrete heavy-hex routing overhead.
   * If $N > 127$: Analytical symbolic scaling models $O(N + p M)$ gate expansion.
2. **Scaling & IBM Hardware Tab (`/api/scaling/ibm-demo`):**
   * Uses structured dataset of 6 curated instances (10Q, 14Q, 22Q, 30Q, 45Q, 54Q).
   * Renders 4 SVG line graphs in Section A across problem sizes.
   * Displays interactive hardware demonstration in Section B.

---

## 29. IBM Hardware Execution Status

**IBM Quantum hardware execution is NOT IMPLEMENTED in the current codebase.**

* **No live hardware submission:** No active connections to IBM Quantum physical backends or Qiskit Runtime Service exist.
* **Transpilation:** Transpilation to IBM Heavy-Hex device topologies (`ibm_brisbane`, `ibm_kyoto`, `ibm_sherbrooke`, `ibm_torino`) is **real and measured** locally using Qiskit's `CouplingMap.from_heavy_hex`.
* **Execution Endpoint (`/api/ibm/execute`):** Contains a short-timeout credentials check; when no live IBM token is present, it returns verified **precomputed hardware benchmark results** labeled `PRECOMPUTED IBM HARDWARE RESULT`.

---

## 30. Current Experiments & Result Data Files

* **Curated Instances (`evcore/ibm_demo_data.py`):**
  1. `demo-inst-1`: 2 EV × 2 St × 2 Slots (10Q, Bitstring `1010000100`, Obj: 4.70, Feasible: True)
  2. `demo-inst-2`: 3 EV × 2 St × 3 Slots (14Q, Bitstring `10010001001000`, Obj: 6.75, Feasible: True)
  3. `demo-inst-3`: 3 EV × 2 St × 4 Slots Baseline (22Q, Bitstring `1110000000010100010000`, Obj: 10.10, Feasible: True)
  4. `demo-inst-4`: 4 EV × 2 St × 4 Slots (30Q, Bitstring `110000000011000000000100001000`, Obj: 10.70, Feasible: False)
  5. `demo-inst-5`: 4 EV × 3 St × 4 Slots (45Q, Bitstring `111000100000101000000000000001000000000000001`, Obj: 13.95, Feasible: True)
  6. `demo-inst-6`: 5 EV × 3 St × 4 Slots (54Q, Bitstring `110000100000000011000001000000000100000000000001100000`, Obj: 20.25, Feasible: True)
* **Standalone Diagnostic Scripts:**
  * `diagnose_qaoa_sampling.py`: Demonstrates that for baseline 22Q, shallow QAOA ($p=1$, 512 shots) samples 117 distinct bitstrings with low feasible probability ($P(\text{feas}) \approx 2.5\%$), and selects an infeasible demand-violating candidate with low QUBO energy.
  * `run_control_experiments.py`: Demonstrates that increasing shots to 4096 and $p$ to 2 improves feasible discovery on baseline.

---

## 31. Implementation-to-Mathematics Traceability Table

| Computational Quantity | Exact Equation / Logic Reconstructed from Code | Source File | Function / Class | Implementation Status | Notes |
|---|---|---|---|---|---|
| Normalized Demand | $d_e = \max(1, \text{round}(\text{demand}[e]))$ | `qubo.py` | `normalize_instance` | IMPLEMENTED | Clamped to positive integers |
| Normalized Window | $W_e = \text{sorted}(\{t \in \text{window}[e] \mid 0 \le t < n_t\})$ | `qubo.py` | `normalize_instance` | IMPLEMENTED | Pruned to valid slot bounds |
| Binary Variables $N$ | $N = n_{st} + \sum_{e} n_{st} \|W_e\|$ | `qubo.py` | `_build_variable_index` | IMPLEMENTED | Closed-form exact count |
| Infrastructure Cost | $\sum_s O_s y_s$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Added to $Q_{ss}$ |
| Electricity Cost | $\sum_{e,s,t} p_t x_{e,s,t}$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Added to $Q_{xx}$ |
| Detour Cost | $\sum_{e,s,t} D_{es} x_{e,s,t}$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Added to $Q_{xx}$ |
| Grid Stress Cost | $w_{\text{stress}} \sum_t L_t^2$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | $Q_{ii} += w$, $Q_{ij} += 2w$ |
| Demand Penalty | $\lambda_{\text{demand}} (\sum x - d_e)^2$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Offset $+\lambda d_e^2$, Diag $+\lambda(1-2d_e)$, Off-diag $+2\lambda$ |
| Coupling Penalty | $\lambda_{\text{coupling}} (x_{e,s,t} - x_{e,s,t} y_s)$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Diag $+\lambda$, Off-diag $-\lambda$ |
| Simultaneous Conflict | $\lambda_{\text{conflict}} \sum_{s_1 < s_2} x_{e,s_1,t} x_{e,s_2,t}$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Off-diag $+\lambda$ |
| Charger Capacity | $\lambda_{\text{conflict}} \sum_{e_1 < e_2} x_{e_1,s,t} x_{e_2,s,t}$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | Off-diag $+\lambda$ |
| Grid Capacity Penalty | $\lambda_{\text{grid}} \sum_{i < j} x_i x_j \quad (\text{if } G_t == 1)$ | `qubo.py` | `_build_matrix` | IMPLEMENTED | **Conditional:** Only applied when $G_t = 1$ |
| Ising Coupling $J$ | $J_{ij} = \frac{1}{4} Q_{\text{sym}, ij} \quad (i \neq j), \ J_{ii} = 0$ | `qubo.py` | `to_ising` | IMPLEMENTED | Derived from $z = (1-s)/2$ |
| Ising Local Field $h$ | $h_i = -\frac{1}{2} \sum_j Q_{\text{sym}, ij}$ | `qubo.py` | `to_ising` | IMPLEMENTED | Linear Pauli Z term |
| Ising Constant $c$ | $\text{offset} + \frac{1}{4} \sum Q_{\text{sym}} + \frac{1}{4} \text{Tr}(Q_{\text{sym}})$ | `qubo.py` | `to_ising` | IMPLEMENTED | Constant energy shift |
| SA Delta Energy | $\Delta E = Q_{\text{sym}, ii} \pm 2 h_i$ | `solver_sa.py` | `SimulatedAnnealingSolver.solve` | IMPLEMENTED | Incremental $O(N)$ evaluation |
| QAOA Cost Unitary | $\prod_{i < j} R_{zz}(4\gamma J_{ij}) \prod_i R_z(2\gamma h_i)$ | `qaoa_solver.py` | `build_circuit` | IMPLEMENTED | Equivalence to $e^{-i\gamma H_C}$ verified |
| QAOA Mixer Unitary | $\prod_i R_x(2\beta)$ | `qaoa_solver.py` | `build_circuit` | IMPLEMENTED | Transverse field mixer |
| Statevector Memory | $16 \times 2^N$ bytes | `qaoa_resources.py`| `estimate_qaoa_resources` | IMPLEMENTED | Double-precision complex amplitudes |
| Optimality Gap | $\frac{\text{cand} - \text{opt}}{\|\text{opt}\|} \times 100\%$ | `exact_solver.py` | `calculate_optimality_gap` | IMPLEMENTED | Relative percentage |

---

## 32. Scaling-Analysis Dependency Map

Reconstructed strictly from the implementation dependencies:

```text
Problem Input Dimensions (N_E, N_S, N_T, Windows W_e)
    │
    ├── (Exact closed form: N_S + N_S * \sum |W_e|)
    ▼
Logical Decision Variables N
    │
    ├── (Combinatorics of overlapping time slots & same-EV pairs)
    ▼
QUBO Quadratic Nonzeros M_2Q
    │
    ├── (Ising conversion: J_ij = 0.25 Q_sym,ij)
    ▼
Ising Cost Hamiltonian Terms (1 + M_1Q + M_2Q)
    │
    ├── (QAOA depth p multiplication)
    ▼
Ideal Algorithmic QAOA Circuit:
    ├── Qubits = N
    ├── 2-Qubit Gates = p * M_2Q
    ├── Total Gates = N + p * (M_2Q + M_1Q + N)
    └── Depth = O(p * max_qubit_degree)
    │
    ├── (Heavy-Hex Topology Transpilation via Qiskit CouplingMap)
    ▼
Physical Hardware Circuit Metrics:
    ├── Physical Qubits Required <= 127
    ├── Transpiled CX Gates = M_2Q * Routing_Overhead_Factor
    └── Transpiled Depth = Algorithmic_Depth * Congestion_Factor
```

---

## 33. Information Needed for the Four Future Scaling Graphs

To derive mathematically defensible relationships for the Scaling & Resources section in subsequent tasks, the following implementation facts are established:

### Graph 1: Logical Qubits ($N$) vs. Problem Size ($N_E \times N_S \times N_T$)
* **Exact relationship from code:**
  $$N = n_{st} + \sum_{e=0}^{n_{ev}-1} n_{st} |W_e|$$
* **If full windows are used ($|W_e| = n_t$):**
  $$N = n_{st} + n_{st} n_{ev} n_t = n_{st} (1 + \text{Problem Size})$$
* **Non-closed-form factor:** Window pruning $|W_e| < n_t$ reduces $N$ linearly by $n_{st} (n_t - |W_e|)$ per EV.

### Graph 2: Circuit Depth vs. Binary Variables ($N$)
* **Ideal Aer Depth:**
  * Lower bound: $p + 1$ (if all commuting $R_{zz}$ terms could execute in parallel).
  * Upper bound: $1 + p(M_{2Q} + 2)$ (serial execution).
  * Actual depth depends on the **edge-coloring / vertex degree** of the QUBO interaction graph.
* **IBM Heavy-Hex Transpiled Depth:**
  * Empirical/heuristic transpiler dependency: determined by SWAP insertion networks across the distance-7 heavy-hex lattice.
  * Measured empirically on the 6 curated instances as scaling from depth 99 ($N=10$) to depth 1106 ($N=54$).

### Graph 3: Total Gate Count vs. Binary Variables ($N$)
* **Ideal Aer Total Gates (Exact closed form):**
  $$G_{\text{ideal}}(N, p) = N + p \cdot \left( M_{2Q} + M_{1Q} + N \right)$$
* **IBM Transpiled Total Gates:**
  * Native basis gates: `['rz', 'sx', 'x', 'cx']`.
  * Each SWAP gate required by non-local coupling introduces 3 CX gates and local single-qubit rotations.
  * Measured empirically on curated instances scaling from 226 gates ($N=10$) to 5134 gates ($N=54$).

### Graph 4: 2-Qubit Gate Count vs. Binary Variables ($N$)
* **Ideal Aer 2-Qubit Gates ($R_{zz}$):**
  $$\text{Gates}_{2Q,\text{ideal}} = p \cdot M_{2Q}$$
* **IBM Transpiled CX Gates:**
  $$\text{Gates}_{CX,\text{transpiled}} = \text{Overhead}(N) \cdot \left( 2 \cdot p \cdot M_{2Q} \right)$$
  Where $\text{Overhead}(N)$ represents routing overhead due to heavy-hex planar degree-3 connectivity (empirically measured between $4.2\times$ and $7.5\times$ on the curated benchmark instances).

---

## 34. Unexpected Implementation Details & Quirks

During the audit, the following implementation details were uncovered that differ from standard textbook assumptions:

1. **Conditional Grid Capacity Penalty in QUBO (`qubo.py:263`):**
   * The hard quadratic penalty for grid capacity exceedance is **only added when `grid_cap[t] == 1`**.
   * If `grid_cap[t] > 1`, the QUBO does not add a hard penalty for grid capacity, relying purely on the soft quadratic grid stress penalty $w_{\text{stress}} (L_t)^2$. The hard limit is only enforced during post-solution validation in `decoder.py`.
2. **Window Pruning Occurs Before Variable Indexing (`qubo.py:124`):**
   * Disallowed time slots ($t \notin W_e$) are completely omitted from the variable vector. They are not assigned variables fixed to zero.
3. **QAOA Candidate Selection Selects Minimum QUBO Energy, Not Feasibility (`qaoa_solver.py:202`):**
   * When QAOA finishes sampling, it selects the bitstring with lowest $z^T Q z + \text{offset}$.
   * It does **not** filter for feasible bitstrings during candidate selection. If penalties fail to sufficiently elevate an infeasible state's energy above a feasible state, the infeasible bitstring is returned as the primary solution.
4. **EV Indices in Decoder Violations are 0-Indexed (`decoder.py:92`):**
   * Violation strings report `EV 0`, `EV 1`, etc., while the frontend UI tables label them `EV1`, `EV2` (1-indexed).
5. **Transpilation in Estimator vs. Solver:**
   * In `qaoa_solver.py:239`, transpilation uses basic all-to-all basis gates `['u', 'cx']` without a coupling map.
   * In `qaoa_resources.py:220`, transpilation uses the full `CouplingMap.from_heavy_hex(distance=7)` reflecting physical hardware topology.

---

## 35. Missing, Not Implemented & Partial Features

* **IBM Quantum Hardware Live Execution:** **NOT IMPLEMENTED.** No live quantum device jobs are submitted.
* **Mixed-Integer Linear Programming (MILP):** **NOT IMPLEMENTED.** Simulated Annealing is the sole primary classical solver.
* **QAOA Slack Variables for Inequality Constraints:** **NOT IMPLEMENTED.** All inequality constraints are converted to quadratic penalties without slack qubits.
* **Post-Measurement Classical Feasibility Repair / Post-Processing:** **NOT IMPLEMENTED.** The raw bitstring from QAOA is decoded directly without post-hoc greedy repair.

---

## 36. Information Not Determined from Current Implementation

```text
NOT DETERMINED FROM CURRENT IMPLEMENTATION:
1. Analytical closed-form routing overhead factor for Heavy-Hex transpilation as an explicit function of N (this is an empirical output of the Qiskit heuristic SABRE/Stochastic swap router).
2. Physical quantum noise / error fidelity models on live hardware (no live calibration data or noise models are present in the repository).
3. Runtime scaling of live IBM Quantum cloud execution queues.
```

---

## 37. Final Source Inventory

### Source Files Inspected
* `evcore/qubo.py`
* `evcore/decoder.py`
* `evcore/solver_sa.py`
* `evcore/qaoa_solver.py`
* `evcore/exact_solver.py`
* `evcore/qaoa_resources.py`
* `evcore/pipeline.py`
* `evcore/ibm_demo_data.py`
* `evcore/mock.py`
* `server/app.py`
* `server/__main__.py`
* `server/static/app.js`
* `server/static/index.html`
* `server/static/styles.css`

### Test Files Inspected
* `tests/test_api.py`
* `tests/test_classical_sa.py`
* `tests/test_qubo_and_exact.py`
* `tests/test_qaoa.py`
* `tests/test_scaling_and_estimate.py`
* `tests/test_live_server_frontend.py`

### Scripts Inspected
* `diagnose_qaoa_sampling.py`
* `run_control_experiments.py`
* `verify_scenarios.py`
* `run_tests.py`

### Documentation Files Inspected
* `docs/ARCHITECTURE.md`
* `docs/CHANGELOG.md`
* `docs/DECISIONS.md`
* `docs/PROJECT_PROGRESS.md`
* `docs/README.md`
* `docs/TODO.md`

---

## 38. Final Code-Integrity Verification

A full cryptographic SHA-256 integrity verification was conducted across all pre-existing project files. Every file matches its pre-audit hash byte-for-byte.

```text
CODE MODIFICATION STATUS:
NONE — READ-ONLY AUDIT
```
