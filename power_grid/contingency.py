"""
N-1 Contingency Analysis for power grid vulnerability.

For each line (edge) in the grid:
  1. Remove the line (simulate outage)
  2. Re-solve AC power flow
  3. Check for violations:
     a. **Line overload**: flow on any remaining line > rate (thermal limit)
     b. **Voltage violation**: bus voltage outside [V_min, V_max] (power deficiency)
     c. **Islanding**: graph becomes disconnected (some buses isolated)

Vulnerability criteria (documented in README.md):
  - A line is "vulnerable" if its removal causes any of:
    1. At least one other line overloaded (>100% of rate)
    2. At least one bus with voltage magnitude < V_min or > V_max
    3. The grid becomes islanded (multiple connected components)

Usage
-----
    from power_grid.contingency import N1ContingencyAnalyzer
    analyzer = N1ContingencyAnalyzer(grid_data)
    result = analyzer.analyze()
    # result["vulnerable_edges"] : list of (line_id, line_name, violations)
    # result["violation_details"] : dict of line_id -> violation info
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .ac_power_flow import ACPowerFlow, DCPowerFlow


class N1ContingencyAnalyzer:
    """N-1 contingency analysis for power grid vulnerability.

    Removes each line one at a time and checks for:
      - Line overloads
      - Voltage violations
      - Islanding

    Uses AC power flow as primary solver (always converges).
    Falls back to DC if AC power flow does not converge.
    """

    def __init__(
        self,
        grid_data: dict,
        v_min: float = 0.9,
        v_max: float = 1.1,
        overload_threshold: float = 1.0,
        slack_bus: int = 0,
        use_dc_fallback: bool = True,
    ):
        """
        Parameters
        ----------
        grid_data : dict
            Standard power grid data dict with keys:
            - buses: list of bus dicts
            - lines: list of line dicts (with 'from_bus', 'to_bus', 'x', 'r', 'rate')
            - generators: list of gen dicts (with 'bus', 'p_mw')
            - loads: list of load dicts (with 'bus', 'p_mw')
            - base_mva: float
        v_min : float
            Minimum allowable voltage (p.u.). Default 0.9.
        v_max : float
            Maximum allowable voltage (p.u.). Default 1.1.
        overload_threshold : float
            Fraction of rate that constitutes overload. Default 1.0 (100%).
        slack_bus : int
            Index of the slack bus.
        use_dc_fallback : bool
            If True, fall back to DC power flow when AC does not converge.
            If False, only AC power flow is used (may give unreliable results
            for grids where AC does not converge).
        """
        self.grid = grid_data
        self.v_min = v_min
        self.v_max = v_max
        self.overload_threshold = overload_threshold
        self.slack_bus = slack_bus
        self.use_dc_fallback = use_dc_fallback

        # Extract grid data
        self.n_bus = len(grid_data["buses"])
        self.lines = grid_data["lines"]
        self.n_line = len(self.lines)
        self.generators = grid_data.get("generators", [])
        self.loads = grid_data.get("loads", [])
        self.base_mva = grid_data.get("base_mva", 100.0)

        # Build bus_pairs, r_list, x_list, rate_list
        self.bus_pairs = [(l["from_bus"], l["to_bus"]) for l in self.lines]
        self.r_list = [l.get("r", 0.0) for l in self.lines]
        self.x_list = [l.get("x", 0.1) for l in self.lines]
        self.rate_list = [l.get("rate", 9999.0) for l in self.lines]

        # Net power injections
        self.p_inj = self._compute_net_injections()

        # PV buses: buses with generators (except slack)
        gen_buses = set(g["bus"] for g in self.generators)
        self.pv_buses = sorted([b for b in gen_buses if b != slack_bus])

    def _compute_net_injections(self) -> NDArray:
        """Compute net active power injection at each bus (generation - load)."""
        p_inj = np.zeros(self.n_bus, dtype=np.float64)
        for g in self.generators:
            p_inj[g["bus"]] += g["p_mw"]
        for ld in self.loads:
            p_inj[ld["bus"]] -= ld["p_mw"]
        return p_inj

    def _run_power_flow(self, bus_pairs, r_list, x_list):
        """Run power flow with continuation fallback and DC fallback.

        Strategy:
          1. Try AC power flow with continuation (scales up from 0 → 100% loading)
          2. If continuation converged at 100% loading → use AC result
          3. If continuation partially converged (loading_scale < 1.0) → still use
             AC result but flag the partial loading in `loading_scale`
          4. If AC completely fails (loading_scale = 0) → fall back to DC

        Returns
        -------
        result : dict with keys: V, theta, converged, branch_flows,
                 method, loading_scale
        """
        # Try AC power flow first with continuation
        ac_solver = ACPowerFlow(
            self.n_bus, bus_pairs, r_list, x_list, self.base_mva
        )
        result = ac_solver.run_power_flow(
            self.p_inj, slack_bus=self.slack_bus, pv_buses=self.pv_buses,
        )

        loading_scale = result.get("loading_scale", 0.0)

        # Case 1: Full convergence at 100% loading
        if result["converged"] and loading_scale >= 1.0 - 1e-6:
            result["method"] = "ac"
            result["partial_load"] = False
            return result

        # Case 2: Partial convergence (continuation reached some loading level)
        if loading_scale > 0.0:
            result["method"] = "ac_partial"
            result["partial_load"] = True
            # Keep the result as-is; converged flag may be False but we still
            # have a useful partial solution
            return result

        # Case 3: AC completely failed — fall back to DC
        if self.use_dc_fallback:
            dc_solver = DCPowerFlow(
                self.n_bus, bus_pairs, x_list, self.base_mva
            )
            dc_result = dc_solver.run_power_flow(
                self.p_inj, slack_bus=self.slack_bus,
            )
            dc_result["method"] = "dc"
            dc_result["ac_converged"] = False
            dc_result["loading_scale"] = 1.0
            dc_result["partial_load"] = False
            return dc_result

        # No fallback — return AC result as-is
        result["method"] = "ac"
        result["partial_load"] = True
        return result

    def _check_connectivity(
        self,
        removed_line_idx: int,
    ) -> tuple[bool, list[set[int]]]:
        """Check if the grid remains connected after removing a line.

        Returns
        -------
        is_connected : bool
            True if the grid is still connected.
        components : list of set of int
            Connected components of the graph.
        """
        n = self.n_bus
        # Build adjacency list excluding the removed line
        adj = [[] for _ in range(n)]
        for l, (f, t) in enumerate(self.bus_pairs):
            if l == removed_line_idx:
                continue
            adj[f].append(t)
            adj[t].append(f)

        # BFS from bus 0
        visited = set()
        stack = [0]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    stack.append(neighbor)

        # Find all components
        all_visited = set()
        components = []
        for start in range(n):
            if start in all_visited:
                continue
            comp = set()
            stack = [start]
            while stack:
                node = stack.pop()
                if node in comp:
                    continue
                comp.add(node)
                for neighbor in adj[node]:
                    if neighbor not in comp:
                        stack.append(neighbor)
            all_visited |= comp
            components.append(comp)

        is_connected = len(visited) == n
        return is_connected, components

    def analyze(self) -> dict:
        """Run N-1 contingency analysis on all lines.

        Returns
        -------
        result : dict with keys:
            - n_bus: int
            - n_line: int
            - base_mva: float
            - vulnerable_edges: list of (line_id, line_name, [violation_types])
            - vulnerable_edge_ids: set of int (line IDs that are vulnerable)
            - violation_details: dict of line_id -> dict with violation info
            - n_vulnerable: int
            - total_edges: int
            - vulnerability_ratio: float (n_vulnerable / total_edges)
            - base_case: dict with base case power flow results
            - baseline_method: str (ac / dc / ac_partial)
            - baseline_loading_scale: float
            - n_partial_load: int (number of contingencies with partial AC load)
            - n_dc_fallback: int (number of contingencies that fell back to DC)
            - partial_load_warning: bool
        """
        # Base case power flow
        base_result = self._run_power_flow(
            self.bus_pairs, self.r_list, self.x_list
        )
        base_flows = base_result["branch_flows"]

        # Store base case loadings for comparison
        base_loadings = np.zeros(self.n_line, dtype=np.float64)
        base_overloaded = set()
        for l_idx in range(self.n_line):
            rate = self.rate_list[l_idx]
            if rate > 0:
                base_loadings[l_idx] = abs(base_flows[l_idx]) / rate
                if abs(base_flows[l_idx]) > rate * self.overload_threshold:
                    base_overloaded.add(l_idx)

        vulnerable_edges = []
        violation_details = {}
        vulnerable_edge_ids = set()
        n_partial_load = 0
        n_dc_fallback = 0

        for line_idx, line in enumerate(self.lines):
            line_id = line["id"]
            line_name = line.get("name", f"L{line_id}")
            violations = []

            # Check islanding first (fast, no power flow needed)
            is_connected, components = self._check_connectivity(line_idx)
            if not is_connected:
                violations.append("islanding")

            # Build reduced system (exclude the outaged line)
            reduced_pairs = [
                p for l, p in enumerate(self.bus_pairs) if l != line_idx
            ]
            reduced_r = [
                r for l, r in enumerate(self.r_list) if l != line_idx
            ]
            reduced_x = [
                x for l, x in enumerate(self.x_list) if l != line_idx
            ]
            reduced_rate = [
                rate for l, rate in enumerate(self.rate_list) if l != line_idx
            ]

            # Skip power flow if too few lines remain
            if len(reduced_pairs) < self.n_bus - 1:
                if "islanding" not in violations:
                    violations.append("islanding")
                violation_details[line_id] = {
                    "line_name": line_name,
                    "violations": violations,
                    "overloaded_lines": [],
                    "voltage_violations": [],
                    "components": [list(c) for c in components],
                    "converged": False,
                    "method": "none",
                    "loading_scale": 0.0,
                    "partial_load": False,
                }
                if violations:
                    vulnerable_edges.append((line_id, line_name, violations))
                    vulnerable_edge_ids.add(line_id)
                continue

            # Run power flow without the outaged line
            pf_result = self._run_power_flow(reduced_pairs, reduced_r, reduced_x)

            # Track method usage
            method = pf_result.get("method", "unknown")
            loading_scale = pf_result.get("loading_scale", 1.0)
            partial_load = pf_result.get("partial_load", False)
            if method == "dc":
                n_dc_fallback += 1
            elif partial_load or method == "ac_partial":
                n_partial_load += 1

            # Initialize variables that may be set inside the if block
            overloaded_lines = []
            voltage_violations = []

            # Only check overloads and voltage violations if power flow converged
            if pf_result["converged"]:
                # Check for voltage violations
                voltage_violations = []
                V = pf_result["V"]
                for bus_idx in range(self.n_bus):
                    if V[bus_idx] < self.v_min:
                        voltage_violations.append({
                            "bus": bus_idx,
                            "type": "undervoltage",
                            "V": float(V[bus_idx]),
                        })
                    elif V[bus_idx] > self.v_max:
                        voltage_violations.append({
                            "bus": bus_idx,
                            "type": "overvoltage",
                            "V": float(V[bus_idx]),
                        })
                if voltage_violations:
                    violations.append("voltage_violation")

                # Check for line overloads — only flag NEW overloads not present in base case
                overloaded_lines = []
                branch_flows = pf_result["branch_flows"]
                for l_idx in range(len(reduced_pairs)):
                    flow_abs = abs(branch_flows[l_idx])
                    rate = reduced_rate[l_idx]
                    if rate > 0 and flow_abs > rate * self.overload_threshold:
                        # Map reduced line index back to original line index
                        orig_idx = -1
                        cnt = -1
                        for oi in range(self.n_line):
                            if oi != line_idx:
                                cnt += 1
                                if cnt == l_idx:
                                    orig_idx = oi
                                    break
                        # Only flag as NEW overload if not already overloaded in base case
                        if orig_idx not in base_overloaded:
                            overloaded_lines.append({
                                "line_idx": l_idx,
                                "orig_line_idx": orig_idx,
                                "flow_mw": float(flow_abs),
                                "rate_mva": float(rate),
                                "loading_pct": float(flow_abs / rate * 100),
                                "base_loading_pct": float(base_loadings[orig_idx] * 100),
                            })
                if overloaded_lines:
                    violations.append("overload")

            violation_details[line_id] = {
                "line_name": line_name,
                "violations": violations,
                "overloaded_lines": overloaded_lines if pf_result["converged"] else [],
                "voltage_violations": voltage_violations if pf_result["converged"] else [],
                "components": [list(c) for c in components] if not is_connected else [],
                "converged": pf_result["converged"],
                "method": method,
                "loading_scale": loading_scale,
                "partial_load": partial_load,
                "iterations": pf_result.get("iterations", 0),
                "mismatch": pf_result.get("mismatch", 0.0),
            }

            if violations:
                vulnerable_edges.append((line_id, line_name, violations))
                vulnerable_edge_ids.add(line_id)

        # ── Include baseline overloaded lines as vulnerable ────
                # Lines that are already overloaded in the intact grid are themselves
                # vulnerability points, even without any contingency.
                baseline_method = base_result.get("method", "ac")
                baseline_loading_scale = base_result.get("loading_scale", 1.0)
                baseline_partial_load = base_result.get("partial_load", False)
        
                for l_idx in base_overloaded:
                    lid = self.lines[l_idx]["id"]
                    if lid not in vulnerable_edge_ids:
                        vulnerable_edge_ids.add(lid)
                        violations = ["baseline_overload"]
                        vulnerable_edges.append((lid, self.lines[l_idx].get("name", f"L{lid}"), violations))
                        if lid not in violation_details:
                            violation_details[lid] = {
                                "line_name": self.lines[l_idx].get("name", f"L{lid}"),
                                "violations": violations,
                                "overloaded_lines": [],
                                "voltage_violations": [],
                                "components": [],
                                "converged": base_result.get("converged", False),
                                "method": baseline_method,
                                "loading_scale": baseline_loading_scale,
                                "partial_load": baseline_partial_load,
                                "baseline_loading_pct": float(base_loadings[l_idx] * 100),
                            }
                        else:
                            # Append to existing violation details
                            violation_details[lid]["violations"].append("baseline_overload")
                            violation_details[lid]["baseline_loading_pct"] = float(base_loadings[l_idx] * 100)
        
                # Check if baseline also had convergence issues
        baseline_method = base_result.get("method", "ac")
        baseline_loading_scale = base_result.get("loading_scale", 1.0)
        baseline_partial_load = base_result.get("partial_load", False)
        partial_load_warning = (
            baseline_partial_load
            or n_partial_load > 0
            or n_dc_fallback > 0
        )

        return {
            "n_bus": self.n_bus,
            "n_line": self.n_line,
            "base_mva": self.base_mva,
            "vulnerable_edges": vulnerable_edges,
            "vulnerable_edge_ids": vulnerable_edge_ids,
            "violation_details": violation_details,
            "n_vulnerable": len(vulnerable_edge_ids),
            "total_edges": self.n_line,
            "vulnerability_ratio": len(vulnerable_edge_ids) / max(self.n_line, 1),
                    "baseline_overloaded": {self.lines[i]["id"] for i in base_overloaded},
            "baseline_method": baseline_method,
            "baseline_loading_scale": baseline_loading_scale,
            "baseline_converged": base_result.get("converged", False),
            "n_partial_load": n_partial_load,
            "n_dc_fallback": n_dc_fallback,
            "partial_load_warning": partial_load_warning,
            "base_case": {
                "converged": base_result["converged"],
                "method": baseline_method,
                "loading_scale": baseline_loading_scale,
                "partial_load": baseline_partial_load,
                "iterations": base_result.get("iterations", 0),
                "mismatch": base_result.get("mismatch", 0.0),
                "V": base_result["V"].tolist(),
                "theta": base_result["theta"].tolist(),
                "branch_flows": base_result["branch_flows"].tolist(),
            },
        }


def analyze_grid_vulnerability(grid_data: dict, **kwargs) -> dict:
    """Convenience function for one-shot grid vulnerability analysis.

    Parameters
    ----------
    grid_data : dict
        Standard power grid data dict.
    **kwargs : passed to N1ContingencyAnalyzer

    Returns
    -------
    result : dict from N1ContingencyAnalyzer.analyze()
    """
    analyzer = N1ContingencyAnalyzer(grid_data, **kwargs)
    return analyzer.analyze()


def get_cycle_edges_from_vr(
    distance_matrix: NDArray,
    bus_pairs: list[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Extract edges that belong to H1 cycles from persistence homology.

    Uses the Vietoris-Rips complex to find edges that participate in
    persistent H1 cycles. These are candidates for homology-based
    vulnerability detection.

    The algorithm:
      1. For each persistent H1 pair (birth, death):
         a. Build the graph at threshold = birth + epsilon
         b. Find the 2-core (vertices with degree >= 2)
         c. Remove bridges from the 2-core to find actual cycle edges
      2. Intersect cycle edges with the grid's bus_pairs topology

    Parameters
    ----------
    distance_matrix : np.ndarray, shape (n_bus, n_bus)
        Electrical distance matrix.
    bus_pairs : list of (int, int)
        Grid line connections.

    Returns
    -------
    cycle_edges : set of (int, int)
        Set of (from_bus, to_bus) tuples that are in H1 cycles.
    """
    from tda.vr_core import VRComplex

    vr = VRComplex(distance_matrix)
    _, h1_pairs = vr.persistence_pairs()

    if not h1_pairs:
        return set()

    n = distance_matrix.shape[0]
    max_dist = vr.max_distance
    infinity = max_dist * 1.5 if max_dist > 0 else 1.0

    # Build grid adjacency from bus_pairs for topology filtering
    grid_adj = [set() for _ in range(n)]
    for f, t in bus_pairs:
        grid_adj[f].add(t)
        grid_adj[t].add(f)

    cycle_edges = set()

    for birth, death in h1_pairs:
        # Skip infinite persistence (essential cycles)
        if death >= infinity:
            continue

        # Use threshold at birth + small epsilon
        threshold = birth + 1e-10

        # Build adjacency at this threshold
        adj = [set() for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if distance_matrix[i, j] <= threshold:
                    adj[i].add(j)
                    adj[j].add(i)

        # Find 2-core (vertices with degree >= 2)
        degree = [len(a) for a in adj]
        changed = True
        while changed:
            changed = False
            for i in range(n):
                if 0 <= degree[i] < 2:
                    degree[i] = -1
                    for j in list(adj[i]):
                        if degree[j] >= 0:
                            degree[j] -= 1
                            changed = True

        # Collect vertices in the 2-core
        core_vertices = {i for i in range(n) if degree[i] >= 2}

        # Find edges that are in actual cycles (not bridges) within the 2-core
        # A bridge is an edge whose removal disconnects the core
        core_edges = set()
        for i in core_vertices:
            for j in adj[i]:
                if j in core_vertices and i < j:
                    core_edges.add((i, j))

        # Collect edges in the 2-core that are also in the grid topology
        candidate_edges = set()
        for i in core_vertices:
            for j in adj[i]:
                if j in core_vertices and i < j and j in grid_adj[i]:
                    candidate_edges.add((i, j))

        # Check if each candidate edge is part of a cycle in the GRID topology.
        # An edge (u,v) is in a cycle if there is an alternative path
        # between u and v in the grid that doesn't use (u,v).
        def is_grid_bridge(u: int, v: int) -> bool:
            """Check if edge (u,v) is a bridge in the grid topology."""
            # BFS from u without using edge (u,v)
            visited = {u}
            stack = [u]
            while stack:
                node = stack.pop()
                for neighbor in grid_adj[node]:
                    if (node == u and neighbor == v) or (node == v and neighbor == u):
                        continue
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            return v not in visited

        for i, j in candidate_edges:
            if not is_grid_bridge(i, j):
                cycle_edges.add((i, j))

    return cycle_edges


def compute_alignment_score(
    vulnerable_edges: set[int],
    cycle_edge_ids: set[int],
    total_edges: int,
) -> dict:
    """Compute alignment between homology-detected and N-1 vulnerable edges.

    Parameters
    ----------
    vulnerable_edges : set of int
        Line IDs that are vulnerable by N-1 contingency analysis.
    cycle_edge_ids : set of int
        Line IDs that are in H1 cycles (homology candidates).
    total_edges : int
        Total number of edges in the grid.

    Returns
    -------
    result : dict with keys:
        - vulnerable_edges: set of int
        - cycle_edge_ids: set of int
        - intersection: set of int (edges in both sets)
        - true_positives: int
        - false_positives: int
        - false_negatives: int
        - true_negatives: int
        - alignment_score: float = |intersection| / total_edges
        - precision: float = TP / (TP + FP) if TP+FP > 0 else 0
        - recall: float = TP / (TP + FN) if TP+FN > 0 else 0
        - specificity: float = TN / (TN + FP) if TN+FP > 0 else 0
    """
    intersection = vulnerable_edges & cycle_edge_ids
    tp = len(intersection)
    fp = len(cycle_edge_ids - vulnerable_edges)
    fn = len(vulnerable_edges - cycle_edge_ids)
    tn = total_edges - tp - fp - fn

    alignment = tp / max(total_edges, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    specificity = tn / max(tn + fp, 1)

    return {
        "vulnerable_edges": vulnerable_edges,
        "cycle_edge_ids": cycle_edge_ids,
        "intersection": intersection,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "alignment_score": alignment,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
    }

