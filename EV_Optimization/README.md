# Quantum Optimization of Coupled EV Charger Siting & Scheduling

An interactive research prototype for jointly deciding **which EV charging stations to open** and **when/where each electric vehicle should charge**, while accounting for electricity prices, travel detours, infrastructure opening costs, and grid constraints.

The project formulates the problem as a **Quadratic Unconstrained Binary Optimization (QUBO)** model and evaluates the same formulation using classical heuristics, exact enumeration, and variational quantum optimization. A Flask web dashboard enables users to configure instances, inspect the compiled formulation, execute compatible solvers, examine decoded schedules, compare solver performances, and analyze quantum resource requirements.

> **Research note:** This project is an experimental optimization workflow. Running QAOA in Qiskit Aer is a classical simulation of parameterized quantum circuits, not execution on a quantum processor and not evidence of quantum advantage. Live IBM Quantum hardware execution is a separate, optional workflow strictly restricted to supported instances.

---

## Highlights

- **Coupled siting and scheduling:** Station-opening decisions and EV charging assignments are modeled and optimized jointly rather than in isolated sequential phases.
- **Shared QUBO formulation:** Simulated Annealing, QAOA, and Exact Enumeration evaluate the identical binary objective function and use a single shared solution decoder and constraint validator.
- **Classical baseline:** Configurable Simulated Annealing (SA) with customizable geometric, exponential, or linear cooling schedules, initial/final temperatures, restarts, seed reproducibility, quench descent, and runtime/evaluation budgets.
- **QAOA simulation:** Parameterized QAOA circuits executed on Qiskit Aer (`aer_simulator`) with classical parameter optimization via COBYLA, complete with measured circuit metrics (depth, gate counts, two-qubit CX gates).
- **Small-instance ground truth:** Exact Enumeration for instances with up to 20 binary variables using Gray code bit updates to evaluate all $2^N$ states and calculate exact optimality gaps.
- **Feasibility and cost analysis:** Comprehensive solution decoding evaluating EV demand fulfillment, charging time windows, simultaneous charging prevention, station capacity, station-opening coupling, and grid capacity limits.
- **Interactive web dashboard:** Single-page Flask application with 6 panels: Problem Setup, Model, Solve, Results, Scaling & IBM Hardware, and Estimate Resources.
- **Hardware-ready and historical records:** Dedicated IBM Quantum hardware runner supporting IBM Quantum Runtime (`SamplerV2`), with saved historical execution records from real IBM Quantum hardware (`ibm_fez`) alongside precomputed demonstration datasets.

---

## Problem Formulation

### Decision Variables

The formulation defines two primary sets of binary decision variables:

1. **Station opening variables:**
   $$y_s \in \{0, 1\} \quad \forall s \in \{0, \dots, n_{st}-1\}$$
   Indicates whether candidate station $s$ is opened ($y_s = 1$) or remains closed ($y_s = 0$).

2. **Charging assignment variables:**
   $$x_{e,s,t} \in \{0, 1\} \quad \forall e \in \{0, \dots, n_{ev}-1\}, \, s \in \{0, \dots, n_{st}-1\}, \, t \in W_e$$
   Indicates whether EV $e$ is assigned to charge at station $s$ during time slot $t$, where $W_e \subseteq \{0, \dots, n_t-1\}$ is the allowed time window for EV $e$.

The total number of binary decision variables $N$ depends directly on station count and allowed EV time windows:
$$N = n_{st} + \sum_{e=0}^{n_{ev}-1} \left(n_{st} \times |W_e|\right)$$

### Objective Function

The physical objective minimizes total operational, infrastructure, and grid impact costs:

$$\min \quad \underbrace{\sum_{e, s, t} P_t x_{e,s,t}}_{\text{Electricity Cost}} + \underbrace{\sum_{e, s, t} D_{e,s} x_{e,s,t}}_{\text{EV Detour Cost}} + \underbrace{\sum_s O_s y_s}_{\text{Infrastructure Cost}} + \underbrace{\beta \sum_t (\text{load}_t)^2}_{\text{Grid Stress Penalty}}$$

where:
- $P_t$ is the electricity price at slot $t$.
- $D_{e,s}$ is the detour/travel cost for EV $e$ to reach station $s$.
- $O_s$ is the capital/opening cost for candidate station $s$.
- $\text{load}_t = \sum_{e, s: t \in W_e} x_{e,s,t}$ is the aggregate charging demand at time slot $t$.
- $\beta$ (`stress_w`) is the grid stress weighting factor.

### Constraints & QUBO Penalty Terms

Physical constraints are incorporated into the upper-triangular QUBO matrix $Q$ via quadratic penalty multipliers:

1. **EV charging demand satisfaction:**
   Each EV $e$ must receive exactly its required charging demand $d_e$:
   $$\lambda_{\text{demand}} \sum_{e} \left( \sum_{s, t \in W_e} x_{e,s,t} - d_e \right)^2 \quad (\lambda_{\text{demand}} = 20.0)$$

2. **Station-opening coupling:**
   An EV may only charge at an open station ($x_{e,s,t} \le y_s \implies x_{e,s,t}(1 - y_s) = 0$):
   $$\lambda_{\text{coupling}} \sum_{e, s, t \in W_e} \left( x_{e,s,t} - x_{e,s,t} y_s \right) \quad (\lambda_{\text{coupling}} = 15.0)$$

3. **Simultaneous charging prevention:**
   An EV can charge at at most one station during any time slot ($\sum_s x_{e,s,t} \le 1$):
   $$\lambda_{\text{conflict}} \sum_{e, t \in W_e} \sum_{s_1 < s_2} x_{e,s_1,t} x_{e,s_2,t} \quad (\lambda_{\text{conflict}} = 20.0)$$

4. **Station charger capacity limit:**
   Each candidate station is currently modeled with a single charging port ($C_s = 1$), meaning at most one EV can charge at station $s$ during slot $t$ ($\sum_e x_{e,s,t} \le 1$):
   $$\lambda_{\text{conflict}} \sum_{s, t} \sum_{e_1 < e_2} x_{e_1,s,t} x_{e_2,s,t} \quad (\lambda_{\text{conflict}} = 20.0)$$

5. **Grid capacity limit:**
   The total charging load at slot $t$ should not exceed the substation limit $\text{grid\_cap}_t$. In the current QUBO matrix construction (`evcore/qubo.py`), when $\text{grid\_cap}_t = 1$, pairwise penalty terms are added:
   $$\lambda_{\text{grid}} \sum_{i < j} x_i x_j \quad (\lambda_{\text{grid}} = 20.0)$$
   When $\text{grid\_cap}_t > 1$, the model relies on the quadratic grid stress penalty ($\beta \sum_t \text{load}_t^2$) to distribute load. The solution decoder (`evcore/decoder.py`) strictly verifies $\text{load}_t \le \text{grid\_cap}_t$ for all capacity values during feasibility validation.

### Compiled QUBO and Ising Representation

The final unconstrained optimization model is expressed as:
$$\min_{z \in \{0,1\}^N} z^\mathsf{T} Q z + c_{\text{offset}}$$

where $z = [y_0, \dots, y_{n_{st}-1}, x_{0,0,t_0}, \dots]^\mathsf{T}$, $Q$ is the upper-triangular matrix, and $c_{\text{offset}}$ is the constant scalar offset.

Using the change of variables $z_i = \frac{1 - s_i}{2}$ where $s_i \in \{-1, +1\}$ (corresponding to Pauli spin operator $Z_i$), the QUBO maps to an Ising Cost Hamiltonian:
$$H_C = \sum_{i < j} J_{ij} Z_i Z_j + \sum_i h_i Z_i + c_{\text{ising}}$$
with symmetric Ising offset:
$$c_{\text{ising}} = c_{\text{offset}} + \frac{1}{4} \sum_{i,j} Q_{\text{sym}, ij} + \frac{1}{4} \operatorname{Tr}(Q_{\text{sym}})$$
ensuring exact numerical equivalence between binary QUBO energy and Ising spin energy.

---

## Solvers

| Solver | Category | Implementation & Role | Guard / Limit |
|---|---|---|---|
| **Simulated Annealing (SA)** | Classical Heuristic | Primary classical baseline. Operates directly on the binary QUBO with Metropolis-Hastings transitions, cooling schedules, quench descent, and computational budgets. | Bounded by user configuration (up to 325 variables in custom problems). |
| **Exact Enumeration** | Classical Exact | Small-instance validation and ground-truth solver. Evaluates all $2^N$ binary states using Gray code bit flips. Computes exact optimality gaps. | Hard safety threshold: $N \le 20$ binary variables ($2^{20} \approx 1.05 \times 10^6$ states). |
| **QAOA (Qiskit Aer)** | Quantum / Hybrid (Simulated) | Parameterized $p$-layer ansatz circuit executed on Qiskit Aer (`aer_simulator`). Classical parameter optimization via COBYLA (`scipy.optimize.minimize`). | Hard simulation guard: $N \le 24$ logical qubits. If $N > 24$, returns structured `unsupported_size`. |
| **IBM Quantum Hardware** | Real Quantum Hardware / Experimental | Dedicated workflow submitting circuits to IBM Quantum backends via `qiskit_ibm_runtime` (`SamplerV2`). | Strictly scoped to Problem A (10 qubits) and Problem B (20 qubits). Requires credentials. |

### How Solver Comparisons Work

1. **Single compilation:** The problem instance is normalized and compiled once into a unified `QUBOModel`.
2. **Ground-truth baseline:** If $N \le 20$, Exact Enumeration is executed automatically to establish the true global optimum.
3. **Execution:** Selected solvers (SA, QAOA, Exact) evaluate against the common QUBO matrix.
4. **Unified decoding:** Candidate bitstrings from each solver are passed through the identical `decode_solution` function in `evcore/decoder.py`.
5. **Consistency:** Feasibility checks, cost breakdowns, and optimality gaps are evaluated consistently across all methods.

### Current Implementation Limits

- **Custom problem dimensions:** Bounded at **8 EVs, 5 candidate stations, and 8 time slots** (up to 325 QUBO binary variables). Requests exceeding these bounds are rejected at the API boundary with HTTP 400.
- **QAOA Aer simulation:** Guarded at **24 logical qubits** to prevent server/browser memory exhaustion during statevector simulation.
- **Exact Enumeration:** Guarded at **20 binary variables** due to $O(2^N)$ exponential complexity.
- **QAOA optimizer implementation:** While the frontend and solver arguments expose an "SPSA" option, the underlying parameter optimization loop in `evcore/qaoa_solver.py` currently executes **COBYLA** via SciPy `minimize(..., method="COBYLA")`. SPSA is currently an alias/placeholder.

---

## Architecture

```text
               Problem Setup (Dashboard or API)
                             │
                             ▼
              Flask API & Validation Boundary
                             │
                             ▼
             QUBO Construction (evcore/qubo.py)
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
Simulated Annealing     QAOA Simulation    Exact Enumeration
 (evcore/solver_sa.py) (evcore/qaoa_solver.py) (evcore/exact_solver.py)
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
               Shared Solution Decoder & Validator
                      (evcore/decoder.py)
                             │
                             ▼
             Feasibility, Schedules, Costs & Loads
                             │
                             ▼
                     Web Dashboard & JSON
```

### Repository Layout

```text
project_1-10-2026/
├── evcore/                               # Optimization and quantum core engine
│   ├── __init__.py                       # Package exports
│   ├── qubo.py                           # Instance normalization, QUBO matrix & Ising conversion
│   ├── solver_sa.py                      # Simulated Annealing QUBO heuristic solver
│   ├── exact_solver.py                   # Small-instance Exact Enumeration ground truth (N <= 20)
│   ├── qaoa_solver.py                    # QAOA ansatz & simulation via Qiskit Aer (N <= 24)
│   ├── decoder.py                        # Solution decoding, constraint validation & physical costs
│   ├── pipeline.py                       # Multi-solver execution and comparison pipeline
│   ├── qaoa_resources.py                 # Circuit synthesis, Heavy-Hex transpilation & resource estimation
│   ├── ibm_hardware.py                   # Dedicated IBM Quantum hardware execution module
│   ├── ibm_demo_data.py                  # Curated 6-instance scaling dataset & benchmark records
│   └── mock.py                           # Baseline reference fixture, presets & demonstration fixtures
├── server/                               # Backend application service
│   ├── __init__.py                       # Package exports
│   ├── app.py                            # Flask REST API endpoints and application controller
│   ├── __main__.py                       # Application entry point (`python -m server`)
│   ├── data/
│   │   └── custom_instances.json         # Persisted custom problem instances
│   └── static/
│       ├── index.html                    # Dashboard markup (6 panels)
│       ├── app.js                        # Frontend application logic and chart rendering
│       └── styles.css                    # Dashboard technical stylesheet
├── tests/                                # Automated test suites
│   ├── test_api.py                       # Flask API endpoints & custom problem creation tests (14 tests)
│   ├── test_classical_sa.py              # Simulated Annealing parameter, budget & pipeline tests (5 tests)
│   ├── test_qubo_and_exact.py            # QUBO compilation, Ising consistency & Exact tests (5 tests)
│   ├── test_qaoa.py                      # QAOA Aer simulation & circuit resource tests (4 tests)
│   ├── test_scaling_and_estimate.py      # Resource estimation & Heavy-Hex transpilation tests (10 tests)
│   └── test_live_ibm_hardware.py         # IBM hardware module scope, schema & mock tests (11 tests)
├── docs/                                 # Technical architecture, decisions, and progress logs
│   ├── ARCHITECTURE.md                   # System architecture specification
│   ├── DECISIONS.md                      # Log of architectural and engineering decisions
│   ├── IMPLEMENTATION_MATHEMATICAL_AUDIT.md # In-depth technical and mathematical audit
│   ├── PROJECT_PROGRESS.md               # Project milestones and status notes
│   ├── CHANGELOG.md                      # Chronological change history
│   └── TODO.md                           # Backlog and future tasks
├── results/ibm_hardware/                 # Stored IBM Quantum hardware experiment JSON records
├── run_tests.py                          # Automated test runner executing regression suites (32 tests)
├── verify_scenarios.py                   # Acceptance verification script (Tests A through E)
├── test_workflow_scenarios.py            # UI workflow, custom problem & persistence test (Workflows A through E)
├── run_control_experiments.py            # QAOA baseline control experiments across p and shots
├── run_ibm_hardware_experiment.py        # Dedicated CLI runner for IBM Quantum hardware experiments
├── diagnose_qaoa_sampling.py             # Diagnostic script analyzing QAOA sampling distribution
├── ibm_config.py                         # Configuration file for IBM Quantum credentials and backend
├── requirements.txt                      # Application dependency manifest
├── .gitignore                            # Git exclusion rules (credentials, cache, temporary files)
└── README.md                             # Project documentation and audit reference
```

---

## Getting Started

### 1. Prerequisites

- Python 3.10 to 3.12 (tested on Python 3.12).
- `pip` package manager and a virtual environment.
- A modern web browser.

> [!NOTE]
> The supplied `requirements.txt` specifies `Flask>=3.0,<4.0`. The optimization and quantum solvers additionally require NumPy, SciPy, Qiskit, and Qiskit Aer. Install all runtime dependencies explicitly as shown below.

### 2. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**Windows (Command Prompt):**
```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 3. Install Dependencies

```bash
python -m pip install "Flask>=3.0,<4.0" numpy scipy qiskit qiskit-aer
```

For live execution on IBM Quantum hardware, install the IBM Quantum Runtime package:
```bash
python -m pip install qiskit-ibm-runtime
```

### 4. Start the Dashboard

Run the server from the project root directory:

```bash
python -m server
```

Then open your browser and navigate to:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Using the Dashboard

The dashboard provides six dedicated functional panels:

1. **Problem Setup:** Select from built-in presets (Small 2×2×2, Baseline 3×2×4, Medium 4×2×4, Larger 4×3×4) or create a custom instance with bounded limits (up to 8 EVs, 5 stations, 8 slots). View the exact computed QUBO variable count $N$.
2. **Model:** Inspect the mathematical formulation, decision variable mapping, objective terms, constraint penalties, QUBO transformation, and Ising spin mapping ($x_i = \frac{1 - Z_i}{2}$).
3. **Solve:** Select any combination of Simulated Annealing, QAOA (Aer), or Exact Enumeration using multi-select cards. Compatibility badges reflect whether solvers are supported based on variable count. Adjust solver parameters (iterations, cooling schedules, QAOA depth $p$, shots).
4. **Results:** Inspect decoded charging assignments, candidate station statuses, grid-load profiles with capacity limits, cost breakdowns, and measured quantum circuit resources (logical qubits, circuit depth, total gates, two-qubit CX gates). When multiple solvers are run, inspect the side-by-side comparison table and comparative load profiles. Export the full result payload as JSON.
5. **Scaling & IBM Hardware:** Explore the 6-instance experimental scaling benchmark comparing Qiskit Aer simulation against IBM Heavy-Hex hardware transpilation. Inspect historical IBM Quantum hardware results.
6. **Estimate Resources:** Synthesize QAOA ansatz circuits and transpile to IBM Quantum Heavy-Hex architectures (e.g., IBM Brisbane, IBM Kyoto, IBM Torino) to inspect circuit depth, 2-qubit CX gates, routing overhead, and double-precision statevector memory without executing optimization loops.

---

## API Overview

The Flask backend provides REST API endpoints for instance management, solver execution, quantum resource estimation, and hardware workflows:

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Serves the main single-page web dashboard (`index.html`). |
| `GET` | `/api/health` | Health check returning service mode, primary solver, and problem/simulation limits. |
| `GET` | `/api/presets` | Retrieves built-in problem presets and saved custom problem instances. |
| `GET` | `/api/instances` | Lists all available problem instances. |
| `POST` | `/api/instances` | Validates, compiles exact QUBO variables, and persists a custom problem instance. |
| `GET` | `/api/instances/<id>` | Retrieves configuration details for a specific instance. |
| `DELETE` | `/api/instances/<id>` | Deletes a custom instance from memory and disk storage (built-in presets protected). |
| `POST` | `/api/instances/<id>/runs` | Dispatches single-solver or multi-solver optimization on the instance's QUBO. |
| `GET` | `/api/runs/<run_id>` | Retrieves execution results for a specific run ID. |
| `GET` | `/api/instances/<id>/compare` | Runs and compares compatible solvers (SA, QAOA, Exact) on the instance. |
| `GET` | `/api/results/baseline` | Retrieves the precomputed baseline reference solution (3×2×4, obj = 10.1). |
| `GET` | `/api/results/ladder` | Retrieves the demonstration scaling ladder. |
| `GET` | `/api/scaling/ibm-demo` | Retrieves curated 6-instance scaling dataset and Heavy-Hex transpilation curves. |
| `POST` | `/api/estimate-resources` | Synthesizes QAOA circuits and computes transpilation metrics for target IBM topologies. |
| `GET` | `/api/ibm/stored-result/<id>` | Retrieves stored hardware execution records for supported instances from disk. |
| `POST` | `/api/ibm/execute` | Retrieves precomputed benchmark results or stored hardware reports. |
| `POST` | `/api/ibm/hardware-run` | Executes live IBM Quantum hardware experiment or local mock simulation. |

---

## Running Tests & Verification

The repository includes automated test suites and validation scripts.

### 1. Automated Test Suite (32 Tests)

Executes unit and integration tests across API routes, Simulated Annealing, QUBO/Ising models, Exact Enumeration, QAOA simulation, and resource estimation:

```bash
python run_tests.py
```

### 2. End-to-End Scenario Verification

Validates the 5 primary system acceptance scenarios:
- **Test A:** Small custom instance solved with SA only (single schedule, no empty comparison blocks).
- **Test B:** Small custom instance solved with QAOA only (quantum metrics, single schedule).
- **Test C:** Small custom instance solved with SA + QAOA (comparative load profiles, comparison table).
- **Test D:** Maximum allowed custom instance (8 EVs, 5 stations, 8 slots = 325 QUBO vars; SA executes successfully, QAOA cleanly blocked at 24-qubit guard).
- **Test E:** Out-of-bounds custom instance (>8 EVs) rejected at API boundary with HTTP 400.

```bash
python verify_scenarios.py
```

### 3. Workflow & Persistence Verification

Verifies UI workflows, custom problem persistence across restarts, clean deletion, and 1-based indexing for UI display:

```bash
python test_workflow_scenarios.py
```

### 4. QAOA Control Experiments

Executes control experiments on the baseline 22-qubit problem across depths ($p=1, 2$) and shot counts (512 vs 4096):

```bash
python run_control_experiments.py
```

### 5. Safe Mock Hardware Experiment

Verifies the IBM Quantum hardware pipeline locally using AerSimulator in mock mode (does not connect to IBM or use credits):

```bash
python run_ibm_hardware_experiment.py --mock --instance a
```

---

## IBM Quantum Hardware Workflow & Historical Results

The repository includes a dedicated hardware module (`evcore/ibm_hardware.py`) and CLI runner (`run_ibm_hardware_experiment.py`).

### Scope and Supported Instances

Hardware execution is strictly locked to two canonical instances:
1. **Problem A:** 2 EVs × 2 Stations × 2 Slots (`instance-a-2x2x2`, 10 logical qubits).
2. **Problem B:** 3 EVs × 2 Stations × 4 Slots (`custom-1791428968536`, 20 logical qubits).

### Verified Historical Hardware Results

Real hardware experiments were executed on the IBM Quantum **`ibm_fez`** backend (156-qubit Heron architecture) and saved in `results/ibm_hardware/`:

- **Problem A (`instance-a-2x2x2`, 10 qubits, $p=2$, 2048 shots):**
  - Backend: `ibm_fez` (Job ID: `db3utbimb58s7388dti0`)
  - Transpiled depth: 463; Two-qubit CX gates: 298.
  - Feasible solution found: Yes (`1010000100`, physical objective = 4.70).
  - Feasible sample probability: $P(\text{feasible}) \approx 2.98\%$ (61 of 2048 shots).
- **Problem B (`custom-1791428968536`, 20 qubits, $p=2$, 2048 shots):**
  - Backend: `ibm_fez` (Job ID: `db3v0204qg6s73c1dae0`)
  - Transpiled depth: 1042; Two-qubit CX gates: 1478.
  - Feasible solution found: **No** (0 feasible states sampled in 2048 shots).
  - Feasible sample probability: $P(\text{feasible}) = 0.0\%$.

> [!IMPORTANT]
> The empirical drop in feasible sample probability from ~3% at 10 qubits down to 0% at 20 qubits illustrates the practical limitations of current noisy intermediate-scale quantum (NISQ) processors. As circuit depth and two-qubit gate counts grow, physical noise reduces the likelihood of sampling valid constrained schedules without error mitigation or classical post-processing.

---

## Security & Credential Management

> [!CAUTION]
> **Never commit real API keys, tokens, or private instance CRNs to Git repositories.**

1. **Exposed credentials check:** Inspect `ibm_config.py`. If active credentials or private CRNs were stored as fallback defaults, **immediately revoke the exposed API key** in the IBM Quantum platform dashboard and generate a new key.
2. **Environment variables:** Store credentials in environment variables or an untracked local `.env` file excluded by `.gitignore`:
   ```bash
   export IBM_QUANTUM_API_KEY="your-new-api-key"
   export IBM_QUANTUM_INSTANCE="your-instance-crn"
   export IBM_QUANTUM_BACKEND="ibm_fez"
   ```
   (On Windows PowerShell, use `$env:IBM_QUANTUM_API_KEY = "your-new-api-key"`).
3. **Configuration file:** Ensure `ibm_config.py` only reads from `os.environ` without hard-coded secrets.
4. **Git history:** Confirm that secret keys are removed from repository commit histories before public distribution.

---

## Known Limitations

- **Station capacity assumption:** Candidate stations are currently modeled with 1 charger each ($C_s = 1$). Multi-port stations require expanding binary variables or introducing slack variables.
- **Grid capacity penalty:** QUBO pairwise penalty encoding is constructed when $\text{grid\_cap}_t = 1$. For larger capacities, the model relies on the quadratic grid stress penalty ($\beta \sum \text{load}_t^2$) during search, while the decoder strictly validates $\text{load}_t \le \text{grid\_cap}_t$.
- **QAOA local simulation limit:** Local statevector simulation in Qiskit Aer is capped at 24 logical qubits due to classical RAM requirements ($2^{24}$ amplitudes $\approx 268$ MB for statevectors; larger counts require gigabytes to terabytes).
- **Exact enumeration limit:** Exact evaluation evaluates all $2^N$ states and is capped at 20 binary variables ($2^{20} \approx 1.05 \times 10^6$ states).
- **Variational parameter optimization:** The QAOA classical loop uses COBYLA via SciPy `minimize`. SPSA is currently not implemented as an active alternative optimizer.
- **No quantum advantage claim:** Simulated Annealing consistently finds optimal or near-optimal solutions within tens to hundreds of milliseconds. QAOA is evaluated as an exploratory hybrid workflow and does not claim quantum speedup over classical solvers.

---

## Documentation

Comprehensive architecture, mathematical specifications, and progress logs are located in the [`docs/`](docs/) directory:
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Architectural layout, solver mechanics, and pipeline flow.
- [`docs/IMPLEMENTATION_MATHEMATICAL_AUDIT.md`](docs/IMPLEMENTATION_MATHEMATICAL_AUDIT.md): Detailed mathematical audit of the objective, constraints, Ising transformation, and solvers.
- [`docs/DECISIONS.md`](docs/DECISIONS.md): Architectural decision records and trade-offs.
- [`docs/PROJECT_PROGRESS.md`](docs/PROJECT_PROGRESS.md): Milestone logs and acceptance test results.

---

## License

This project is a research prototype. If releasing publicly, add an appropriate open-source license (such as MIT or Apache 2.0).
