"""QUBO construction for coupled EV charger siting and scheduling.

Translates an EV problem instance into a binary Quadratic Unconstrained
Binary Optimization (QUBO) problem:
    min z^T Q z + offset
where z in {0, 1}^N.

Pipeline stage:
    Problem Instance -> QUBO Construction -> Binary QUBO
"""

from typing import Any, Dict, List, Tuple
import numpy as np


def normalize_instance(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures all instance attributes are well-formed and consistent."""
    inst = dict(instance)
    n_ev = int(inst.get("n_ev", 3))
    n_st = int(inst.get("n_st", 2))
    n_t = int(inst.get("n_t", 4))

    demand_raw = list(inst.get("demand", [1] * n_ev))[:n_ev]
    while len(demand_raw) < n_ev:
        demand_raw.append(1)
    demand = [max(1, int(round(d))) for d in demand_raw]

    window_raw = list(inst.get("window", [list(range(n_t)) for _ in range(n_ev)]))[:n_ev]
    window = []
    for i in range(n_ev):
        w = [int(t) for t in window_raw[i] if 0 <= int(t) < n_t] if i < len(window_raw) else list(range(n_t))
        if not w:
            w = list(range(n_t))
        window.append(sorted(list(set(w))))

    price_raw = list(inst.get("price", [1.0] * n_t))[:n_t]
    while len(price_raw) < n_t:
        price_raw.append(1.0)
    price = [float(p) for p in price_raw]

    grid_cap_raw = list(inst.get("grid_cap", [n_ev] * n_t))[:n_t]
    while len(grid_cap_raw) < n_t:
        grid_cap_raw.append(n_ev)
    grid_cap = [max(1, int(g)) for g in grid_cap_raw]

    open_cost_raw = list(inst.get("open_cost", [1.0] * n_st))[:n_st]
    while len(open_cost_raw) < n_st:
        open_cost_raw.append(1.0)
    open_cost = [float(c) for c in open_cost_raw]

    detour_raw = inst.get("detour", [[0.0] * n_st for _ in range(n_ev)])
    detour = []
    for e in range(n_ev):
        row = detour_raw[e][:n_st] if e < len(detour_raw) else [0.0] * n_st
        while len(row) < n_st:
            row.append(0.0)
        detour.append([float(x) for x in row])

    stress_w = float(inst.get("stress_w", 0.25))
    seed = int(inst.get("seed", 42))

    return {
        **inst,
        "n_ev": n_ev,
        "n_st": n_st,
        "n_t": n_t,
        "demand": demand,
        "window": window,
        "price": price,
        "grid_cap": grid_cap,
        "open_cost": open_cost,
        "detour": detour,
        "stress_w": stress_w,
        "seed": seed,
    }


class QUBOModel:
    """Represents a compiled binary QUBO model for an EV optimization instance."""

    def __init__(
        self,
        instance: Dict[str, Any],
        penalty_demand: float = 20.0,
        penalty_coupling: float = 15.0,
        penalty_conflict: float = 20.0,
        penalty_grid: float = 20.0,
    ):
        self.instance = normalize_instance(instance)
        self.penalty_demand = penalty_demand
        self.penalty_coupling = penalty_coupling
        self.penalty_conflict = penalty_conflict
        self.penalty_grid = penalty_grid

        self.var_names: List[str] = []
        self.var_map: Dict[str, int] = {}
        self.var_meta: List[Dict[str, Any]] = []

        self._build_variable_index()
        self.n_vars = len(self.var_names)
        self.Q = np.zeros((self.n_vars, self.n_vars), dtype=float)
        self.offset = 0.0

        self._build_matrix()
        self.Q_sym = 0.5 * (self.Q + self.Q.T)

    def _build_variable_index(self):
        """Builds contiguous variable indices:

        1. Station variables y_s (s in 0..n_st-1)
        2. Charging variables x_{e,s,t} (e in 0..n_ev-1, s in 0..n_st-1, t in window[e])
        """
        # Station opening variables y_s
        for s in range(self.instance["n_st"]):
            name = f"y_{s}"
            idx = len(self.var_names)
            self.var_names.append(name)
            self.var_map[name] = idx
            self.var_meta.append({"type": "station", "station": s})

        # Charging assignment variables x_{e,s,t}
        for e in range(self.instance["n_ev"]):
            for s in range(self.instance["n_st"]):
                for t in self.instance["window"][e]:
                    name = f"x_{e}_{s}_{t}"
                    idx = len(self.var_names)
                    self.var_names.append(name)
                    self.var_map[name] = idx
                    self.var_meta.append({
                        "type": "assignment",
                        "ev": e,
                        "station": s,
                        "slot": t,
                    })

    def _build_matrix(self):
        """Populates the upper-triangular QUBO matrix Q and constant offset."""
        inst = self.instance
        n_ev = inst["n_ev"]
        n_st = inst["n_st"]
        n_t = inst["n_t"]
        demand = inst["demand"]
        window = inst["window"]
        price = inst["price"]
        grid_cap = inst["grid_cap"]
        open_cost = inst["open_cost"]
        detour = inst["detour"]
        stress_w = inst["stress_w"]

        # ---------------------------------------------------------
        # 1. Objective: Infrastructure opening cost sum_s O_s y_s
        # ---------------------------------------------------------
        for s in range(n_st):
            y_idx = self.var_map[f"y_{s}"]
            self.Q[y_idx, y_idx] += open_cost[s]

        # ---------------------------------------------------------
        # 2. Objective: Electricity + Detour cost
        #    sum_{e,s,t} (price[t] + detour[e][s]) * x_{e,s,t}
        # ---------------------------------------------------------
        for e in range(n_ev):
            for s in range(n_st):
                for t in window[e]:
                    x_idx = self.var_map[f"x_{e}_{s}_{t}"]
                    self.Q[x_idx, x_idx] += price[t] + detour[e][s]

        # ---------------------------------------------------------
        # 3. Objective: Grid stress penalty: stress_w * sum_t (load_t)^2
        #    load_t = sum_{e, s: t in window[e]} x_{e,s,t}
        #    (sum x)^2 = sum x + 2 sum_{i < j} x_i x_j
        # ---------------------------------------------------------
        for t in range(n_t):
            vars_at_t = [
                self.var_map[f"x_{e}_{s}_{t}"]
                for e in range(n_ev)
                if t in window[e]
                for s in range(n_st)
            ]
            for i, vi in enumerate(vars_at_t):
                self.Q[vi, vi] += stress_w
                for j in range(i + 1, len(vars_at_t)):
                    vj = vars_at_t[j]
                    row, col = min(vi, vj), max(vi, vj)
                    self.Q[row, col] += 2.0 * stress_w

        # ---------------------------------------------------------
        # 4. Constraint: EV demand satisfaction
        #    penalty_demand * (sum_{s, t in W_e} x_{e,s,t} - demand[e])^2
        # ---------------------------------------------------------
        for e in range(n_ev):
            ev_vars = [
                self.var_map[f"x_{e}_{s}_{t}"]
                for s in range(n_st)
                for t in window[e]
            ]
            de = demand[e]
            self.offset += self.penalty_demand * (de ** 2)
            for i, vi in enumerate(ev_vars):
                self.Q[vi, vi] += self.penalty_demand * (1.0 - 2.0 * de)
                for j in range(i + 1, len(ev_vars)):
                    vj = ev_vars[j]
                    row, col = min(vi, vj), max(vi, vj)
                    self.Q[row, col] += 2.0 * self.penalty_demand

        # ---------------------------------------------------------
        # 5. Constraint: Station opening coupling
        #    x_{e,s,t} <= y_s  =>  x_{e,s,t} (1 - y_s) = 0
        #    penalty_coupling * (x_{e,s,t} - x_{e,s,t} y_s)
        # ---------------------------------------------------------
        for e in range(n_ev):
            for s in range(n_st):
                y_idx = self.var_map[f"y_{s}"]
                for t in window[e]:
                    x_idx = self.var_map[f"x_{e}_{s}_{t}"]
                    self.Q[x_idx, x_idx] += self.penalty_coupling
                    row, col = min(x_idx, y_idx), max(x_idx, y_idx)
                    self.Q[row, col] -= self.penalty_coupling

        # ---------------------------------------------------------
        # 6. Constraint: Simultaneous charging prevention
        #    Each EV can charge at at most 1 station per time slot
        #    sum_s x_{e,s,t} <= 1 => sum_{s1 < s2} x_{e,s1,t} x_{e,s2,t}
        # ---------------------------------------------------------
        for e in range(n_ev):
            for t in window[e]:
                for s1 in range(n_st):
                    for s2 in range(s1 + 1, n_st):
                        idx1 = self.var_map[f"x_{e}_{s1}_{t}"]
                        idx2 = self.var_map[f"x_{e}_{s2}_{t}"]
                        row, col = min(idx1, idx2), max(idx1, idx2)
                        self.Q[row, col] += self.penalty_conflict

        # ---------------------------------------------------------
        # 7. Constraint: Station capacity (1 charger per station candidate)
        #    sum_e x_{e,s,t} <= 1 => sum_{e1 < e2} x_{e1,s,t} x_{e2,s,t}
        # ---------------------------------------------------------
        for s in range(n_st):
            for t in range(n_t):
                vars_s_t = [
                    self.var_map[f"x_{e}_{s}_{t}"]
                    for e in range(n_ev)
                    if t in window[e]
                ]
                for i in range(len(vars_s_t)):
                    for j in range(i + 1, len(vars_s_t)):
                        vi = vars_s_t[i]
                        vj = vars_s_t[j]
                        row, col = min(vi, vj), max(vi, vj)
                        self.Q[row, col] += self.penalty_conflict

        # ---------------------------------------------------------
        # 8. Constraint: Grid capacity limit
        #    Total load at slot t <= grid_cap[t]
        # ---------------------------------------------------------
        for t in range(n_t):
            cap = grid_cap[t]
            vars_t = [
                self.var_map[f"x_{e}_{s}_{t}"]
                for e in range(n_ev)
                if t in window[e]
                for s in range(n_st)
            ]
            if cap == 1 and len(vars_t) > 1:
                for i in range(len(vars_t)):
                    for j in range(i + 1, len(vars_t)):
                        vi = vars_t[i]
                        vj = vars_t[j]
                        row, col = min(vi, vj), max(vi, vj)
                        self.Q[row, col] += self.penalty_grid

    def evaluate_energy(self, z: np.ndarray) -> float:
        """Evaluates QUBO objective: z^T Q z + offset."""
        z_arr = np.asarray(z, dtype=float)
        return float(z_arr.dot(self.Q).dot(z_arr) + self.offset)

    def to_ising(self) -> Tuple[np.ndarray, np.ndarray, float]:
        """Converts binary QUBO to Ising formulation: H = sum J_ij s_i s_j + sum h_i s_i + c_ising

        where z_i = (1 - s_i) / 2 and s_i in {-1, +1}.
        Returns:
            J (N x N symmetric matrix), h (N-vector), c_ising (float)
        """
        N = self.n_vars
        Q_sym = self.Q_sym

        # z_i = 1/2 - 1/2 s_i
        # z^T Q z = sum_i Q_ii (1/4 - 1/2 s_i + 1/4 s_i^2) + sum_{i!=j} Q_ij (1/4 - 1/4 s_i - 1/4 s_j + 1/4 s_i s_j)
        J = 0.25 * Q_sym.copy()
        np.fill_diagonal(J, 0.0)

        # linear field h_i
        h = np.zeros(N, dtype=float)
        for i in range(N):
            # from Q_ii: -1/2 Q_ii
            # from sum_{j != i} Q_ij (-1/4 s_i - 1/4 s_i) = -1/2 sum_{j} Q_ij
            h[i] = -0.5 * np.sum(Q_sym[i, :])

        # constant offset
        c_ising = float(self.offset + 0.25 * np.sum(Q_sym) + 0.25 * np.trace(Q_sym))
        return J, h, c_ising
