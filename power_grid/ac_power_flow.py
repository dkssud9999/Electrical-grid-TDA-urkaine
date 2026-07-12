"""
AC Power Flow Solver (Newton-Raphson in polar coordinates).

Pure numpy implementation — no external dependencies beyond numpy.

Solves the power flow equations:
    P_i = V_i Σ_j V_j (G_ij cos(θ_ij) + B_ij sin(θ_ij))
    Q_i = V_i Σ_j V_j (G_ij sin(θ_ij) - B_ij cos(θ_ij))

Bus types:
  - Slack (ref): V and θ specified (θ = 0)
  - PV: P and V specified
  - PQ: P and Q specified

Usage
-----
    solver = ACPowerFlow(n_bus, bus_pairs, r_list, x_list)
    result = solver.run_power_flow(
        p_inj=[...],         # net active power injection at each bus
        q_inj=[...],         # net reactive power injection at each bus
        slack_bus=0,
        pv_buses=[1],
    )
    # result["V"]  : voltage magnitudes
    # result["theta"] : voltage angles
    # result["iterations"] : number of iterations
    # result["converged"] : bool
    # result["branch_flows"] : active power flows on each line
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class ACPowerFlow:
    """Newton-Raphson AC power flow solver."""

    def __init__(
        self,
        n_bus: int,
        bus_pairs: list[tuple[int, int]],
        r_list: list[float],
        x_list: list[float],
        base_mva: float = 100.0,
    ):
        self.n_bus = n_bus
        self.bus_pairs = bus_pairs
        self.n_line = len(bus_pairs)
        self.base_mva = base_mva

        # Build admittance matrix Ybus = G + jB
        self._build_ybus(r_list, x_list)

    def _build_ybus(self, r_list: list[float], x_list: list[float]):
        """Build the bus admittance matrix Ybus = G + jB."""
        n = self.n_bus
        Ybus = np.zeros((n, n), dtype=np.complex128)

        for l, (f, t) in enumerate(self.bus_pairs):
            r = r_list[l]
            x = x_list[l]
            if abs(r) < 1e-12 and abs(x) < 1e-12:
                continue
            # Series admittance: y = 1 / (r + jx)
            y = 1.0 / complex(r, x)
            Ybus[f, f] += y
            Ybus[t, t] += y
            Ybus[f, t] -= y
            Ybus[t, f] -= y

        self.Ybus = Ybus
        self.G = Ybus.real
        self.B = Ybus.imag

    def _compute_mismatch(
        self,
        V: NDArray,
        theta: NDArray,
        p_sched: NDArray,
        q_sched: NDArray,
        pv_mask: NDArray,
        pq_mask: NDArray,
    ) -> tuple[NDArray, NDArray]:
        """Compute active and reactive power mismatches."""
        n = self.n_bus
        # Compute injected power at each bus
        p_calc = np.zeros(n)
        q_calc = np.zeros(n)

        for i in range(n):
            for j in range(n):
                theta_ij = theta[i] - theta[j]
                g_ij = self.G[i, j]
                b_ij = self.B[i, j]
                v_iv_j = V[i] * V[j]
                p_calc[i] += v_iv_j * (g_ij * np.cos(theta_ij) + b_ij * np.sin(theta_ij))
                q_calc[i] += v_iv_j * (g_ij * np.sin(theta_ij) - b_ij * np.cos(theta_ij))

        # Mismatches
        n_pv_pq = np.sum(pv_mask | pq_mask)
        n_pq = np.sum(pq_mask)

        # Active power mismatch for non-slack buses
        delta_p = np.zeros(n_pv_pq)
        idx = 0
        for i in range(n):
            if pv_mask[i] or pq_mask[i]:
                delta_p[idx] = p_sched[i] - p_calc[i]
                idx += 1

        # Reactive power mismatch for PQ buses
        delta_q = np.zeros(n_pq)
        idx = 0
        for i in range(n):
            if pq_mask[i]:
                delta_q[idx] = q_sched[i] - q_calc[i]
                idx += 1

        return delta_p, delta_q

    def _build_jacobian(
        self,
        V: NDArray,
        theta: NDArray,
        pv_mask: NDArray,
        pq_mask: NDArray,
    ) -> NDArray:
        """Build the Jacobian matrix for Newton-Raphson.

        J = [J1  J2]
            [J3  J4]

        J1 = ∂P/∂θ  (size: (n_pv+n_pq) × (n_pv+n_pq))
        J2 = ∂P/∂V  (size: (n_pv+n_pq) × n_pq)
        J3 = ∂Q/∂θ  (size: n_pq × (n_pv+n_pq))
        J4 = ∂Q/∂V  (size: n_pq × n_pq)

        Standard formulas (Kundur, Power System Stability and Control):
          i≠j:
            ∂Pi/∂θj = Vi·Vj·(Gij·sinθij - Bij·cosθij)
            ∂Pi/∂Vj = Vi·(Gij·cosθij + Bij·sinθij)
            ∂Qi/∂θj = -Vi·Vj·(Gij·cosθij + Bij·sinθij)
            ∂Qi/∂Vj = Vi·(Gij·sinθij - Bij·cosθij)
          i=j:
            ∂Pi/∂θi = -Qi - Bii·Vi²
            ∂Pi/∂Vi =  Pi/Vi + Gii·Vi
            ∂Qi/∂θi =  Pi - Gii·Vi²
            ∂Qi/∂Vi =  Qi/Vi - Bii·Vi
        """
        n = self.n_bus
        n_pv_pq = np.sum(pv_mask | pq_mask)
        n_pq = np.sum(pq_mask)

        J1 = np.zeros((n_pv_pq, n_pv_pq))
        J2 = np.zeros((n_pv_pq, n_pq))
        J3 = np.zeros((n_pq, n_pv_pq))
        J4 = np.zeros((n_pq, n_pq))

        # Map bus index to position in PV+PQ list
        bus_to_pvpq = {}
        idx = 0
        for i in range(n):
            if pv_mask[i] or pq_mask[i]:
                bus_to_pvpq[i] = idx
                idx += 1

        # Map bus index to position in PQ list
        bus_to_pq = {}
        idx = 0
        for i in range(n):
            if pq_mask[i]:
                bus_to_pq[i] = idx
                idx += 1

        # Precompute P and Q for diagonal formulas
        P_calc = np.zeros(n)
        Q_calc = np.zeros(n)
        for i in range(n):
            for j in range(n):
                theta_ij = theta[i] - theta[j]
                v_iv_j = V[i] * V[j]
                P_calc[i] += v_iv_j * (self.G[i, j] * np.cos(theta_ij)
                                        + self.B[i, j] * np.sin(theta_ij))
                Q_calc[i] += v_iv_j * (self.G[i, j] * np.sin(theta_ij)
                                        - self.B[i, j] * np.cos(theta_ij))

        for i in range(n):
            if not (pv_mask[i] or pq_mask[i]):
                continue
            i_pvpq = bus_to_pvpq[i]

            for j in range(n):
                if not (pv_mask[j] or pq_mask[j]):
                    continue
                j_pvpq = bus_to_pvpq[j]

                theta_ij = theta[i] - theta[j]
                g_ij = self.G[i, j]
                b_ij = self.B[i, j]

                if i == j:
                    # Diagonal: ∂Pi/∂θi = -Qi - Bii·Vi²
                    J1[i_pvpq, j_pvpq] = -Q_calc[i] - b_ij * V[i]**2

                    # J2 diagonal: ∂Pi/∂Vi = Pi/Vi + Gii·Vi
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        if abs(V[i]) > 1e-12:
                            J2[i_pvpq, i_pq] = P_calc[i] / V[i] + g_ij * V[i]
                        else:
                            J2[i_pvpq, i_pq] = g_ij * V[i]

                    # J3 diagonal: ∂Qi/∂θi = Pi - Gii·Vi²
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        J3[i_pq, j_pvpq] = P_calc[i] - g_ij * V[i]**2

                    # J4 diagonal: ∂Qi/∂Vi = Qi/Vi - Bii·Vi
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        if abs(V[i]) > 1e-12:
                            J4[i_pq, i_pq] = Q_calc[i] / V[i] - b_ij * V[i]
                        else:
                            J4[i_pq, i_pq] = -b_ij * V[i]

                else:
                    # Off-diagonal: ∂Pi/∂θj
                    J1[i_pvpq, j_pvpq] = V[i] * V[j] * (
                        g_ij * np.sin(theta_ij) - b_ij * np.cos(theta_ij)
                    )

                    # Off-diagonal: ∂Pi/∂Vj
                    if pq_mask[j]:
                        j_pq = bus_to_pq[j]
                        J2[i_pvpq, j_pq] = V[i] * (
                            g_ij * np.cos(theta_ij) + b_ij * np.sin(theta_ij)
                        )

                    # Off-diagonal: ∂Qi/∂θj
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        J3[i_pq, j_pvpq] = -V[i] * V[j] * (
                            g_ij * np.cos(theta_ij) + b_ij * np.sin(theta_ij)
                        )

                    # Off-diagonal: ∂Qi/∂Vj
                    if pq_mask[i] and pq_mask[j]:
                        i_pq = bus_to_pq[i]
                        j_pq = bus_to_pq[j]
                        J4[i_pq, j_pq] = V[i] * (
                            g_ij * np.sin(theta_ij) - b_ij * np.cos(theta_ij)
                        )

        # Assemble full Jacobian
        top = np.hstack([J1, J2])
        bottom = np.hstack([J3, J4])
        J = np.vstack([top, bottom])
        return J

    def _solve_nr_step(
            self,
            V: NDArray,
            theta: NDArray,
            p_sched: NDArray,
            q_sched: NDArray,
            pv_mask: NDArray,
            pq_mask: NDArray,
            v_min: float = 0.3,
            v_max: float = 1.7,
        ) -> tuple[NDArray, NDArray, NDArray, float]:
            """Perform one damped Newton-Raphson iteration.
    
            Returns (V, theta, mismatch, converged_flag).
            converged_flag is 0=not converged, 1=converged.
            """
            n = pv_mask.shape[0] if hasattr(pv_mask, 'shape') else len(pv_mask)
            delta_p, delta_q = self._compute_mismatch(V, theta, p_sched, q_sched, pv_mask, pq_mask)
            mismatch = np.max(np.abs(np.concatenate([delta_p, delta_q])))
    
            J = self._build_jacobian(V, theta, pv_mask, pq_mask)
            try:
                delta_x = np.linalg.solve(J, np.concatenate([delta_p, delta_q]))
            except np.linalg.LinAlgError:
                delta_x = np.linalg.lstsq(J, np.concatenate([delta_p, delta_q]), rcond=None)[0]
    
            n_pv_pq = np.sum(pv_mask | pq_mask)
            n_pq = np.sum(pq_mask)
            delta_theta_full = delta_x[:n_pv_pq]
            delta_v_full = delta_x[n_pv_pq:]
    
            # Backtracking line search
            best_alpha = 1.0
            best_mismatch = mismatch
            for alpha in [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]:
                V_test = V.copy()
                theta_test = theta.copy()
                idx = 0
                for i in range(n):
                    if pv_mask[i] or pq_mask[i]:
                        theta_test[i] += alpha * delta_theta_full[idx]
                        idx += 1
                idx = 0
                for i in range(n):
                    if pq_mask[i]:
                        V_test[i] *= (1.0 + alpha * delta_v_full[idx])
                        V_test[i] = max(v_min, min(v_max, V_test[i]))
                        idx += 1
    
                dp, dq = self._compute_mismatch(V_test, theta_test, p_sched, q_sched, pv_mask, pq_mask)
                m = np.max(np.abs(np.concatenate([dp, dq])))
                if m < best_mismatch:
                    best_mismatch = m
                    best_alpha = alpha
                    break
    
            # Apply step with best damping
            idx = 0
            for i in range(n):
                if pv_mask[i] or pq_mask[i]:
                    theta[i] += best_alpha * delta_theta_full[idx]
                    idx += 1
            idx = 0
            for i in range(n):
                if pq_mask[i]:
                    V[i] *= (1.0 + best_alpha * delta_v_full[idx])
                    V[i] = max(v_min, min(v_max, V[i]))
                    idx += 1
    
            return V, theta, mismatch, 1.0 if mismatch < 1e-6 else 0.0

    def run_power_flow(
        self,
        p_inj: list[float] | NDArray,
        q_inj: list[float] | NDArray | None = None,
        slack_bus: int = 0,
        pv_buses: list[int] | None = None,
        v_setpoints: list[float] | None = None,
        max_iter: int = 20,
        tolerance: float = 1e-8,
        use_continuation: bool = True,
    ) -> dict:
        """Run Newton-Raphson AC power flow with optional continuation fallback.

        Parameters
        ----------
        p_inj : array-like, shape (n_bus,)
            Net active power injection (generation - load) at each bus, in MW.
        q_inj : array-like, shape (n_bus,), optional
            Net reactive power injection at each bus, in MVAr.
            If None, assumes Q=0 for all buses.
        slack_bus : int
            Index of the slack/reference bus.
        pv_buses : list of int, optional
            Indices of PV buses (P and V specified).
        v_setpoints : list of float, optional
            Voltage setpoints for PV buses. Default: 1.0 p.u. for all.
        max_iter : int
            Maximum Newton-Raphson iterations per stage.
        tolerance : float
            Convergence tolerance for power mismatches.
        use_continuation : bool
            If True, use continuation (homotopy) method when standard NR fails.
            Gradually scales up injection from 0 to target.

        Returns
        -------
        result : dict
            - V: voltage magnitudes (n_bus,)
            - theta: voltage angles in radians (n_bus,)
            - converged: bool
            - iterations: int
            - mismatch: float
            - branch_flows: active power flow on each line (n_line,)
            - loading_scale: float (1.0 if fully converged, <1 if continuation)
        """
        n = self.n_bus
        p_inj = np.asarray(p_inj, dtype=np.float64)
        if q_inj is None:
            q_inj = np.zeros(n, dtype=np.float64)
        else:
            q_inj = np.asarray(q_inj, dtype=np.float64)

        if pv_buses is None:
            pv_buses = []

        # Bus type masks
        slack_mask = np.zeros(n, dtype=bool)
        slack_mask[slack_bus] = True
        pv_mask = np.zeros(n, dtype=bool)
        for b in pv_buses:
            if b != slack_bus:
                pv_mask[b] = True
        pq_mask = ~(slack_mask | pv_mask)

        # Voltage setpoints
        V = np.ones(n, dtype=np.float64)
        if v_setpoints is not None:
            for i, v in enumerate(v_setpoints):
                if pv_mask[i]:
                    V[i] = v

        theta = np.zeros(n, dtype=np.float64)

        # Scheduled injections (per unit on system base)
        base = self.base_mva
        p_sched_full = p_inj / base
        q_sched_full = q_inj / base

        # ── Step 1: Try standard Newton-Raphson ────────────────
        V_nr = V.copy()
        theta_nr = theta.copy()
        mismatch = float("inf")
        converged_nr = False

        for iteration in range(max_iter):
            delta_p, delta_q = self._compute_mismatch(
                V_nr, theta_nr, p_sched_full, q_sched_full, pv_mask, pq_mask,
            )
            mismatch = np.max(np.abs(np.concatenate([delta_p, delta_q])))
            if mismatch < tolerance:
                converged_nr = True
                branch_flows = self._compute_branch_flows(V_nr, theta_nr)
                return {
                    "V": V_nr, "theta": theta_nr,
                    "converged": True, "iterations": iteration,
                    "mismatch": float(mismatch),
                    "branch_flows": branch_flows,
                    "loading_scale": 1.0,
                }

            V_nr, theta_nr, mismatch, _ = self._solve_nr_step(
                V_nr, theta_nr, p_sched_full, q_sched_full,
                pv_mask, pq_mask,
            )

        # ── Step 2: Continuation (homotopy) NR ─────────────────
        if use_continuation:
            n_steps = 20  # 5% increments
            V_cont = np.ones(n, dtype=np.float64)
            theta_cont = np.zeros(n, dtype=np.float64)
            last_converged_scale = 0.0

            for step in range(1, n_steps + 1):
                scale = step / n_steps
                p_sched = p_sched_full * scale
                q_sched = q_sched_full * scale

                converged_step = False
                for iteration in range(max_iter):
                    dp, dq = self._compute_mismatch(
                        V_cont, theta_cont, p_sched, q_sched, pv_mask, pq_mask,
                    )
                    mm = np.max(np.abs(np.concatenate([dp, dq])))
                    if mm < tolerance:
                        converged_step = True
                        last_converged_scale = scale
                        break

                    V_cont, theta_cont, mm, _ = self._solve_nr_step(
                        V_cont, theta_cont, p_sched, q_sched,
                        pv_mask, pq_mask,
                    )

                if not converged_step:
                    # Continuation diverged — use last good solution
                    branch_flows = self._compute_branch_flows(V_cont, theta_cont)
                    return {
                        "V": V_cont, "theta": theta_cont,
                        "converged": False,
                        "iterations": max_iter,
                        "mismatch": float(mm),
                        "branch_flows": branch_flows,
                        "loading_scale": last_converged_scale,
                    }

            # Continuation succeeded for all steps
            branch_flows = self._compute_branch_flows(V_cont, theta_cont)
            return {
                "V": V_cont, "theta": theta_cont,
                "converged": True, "iterations": n_steps * max_iter,
                "mismatch": float(mm),
                "branch_flows": branch_flows,
                "loading_scale": 1.0,
            }

        # ── Did not converge ───────────────────────────────────
        branch_flows = self._compute_branch_flows(V_nr, theta_nr)
        return {
            "V": V_nr, "theta": theta_nr,
            "converged": False, "iterations": max_iter,
            "mismatch": float(mismatch),
            "branch_flows": branch_flows,
            "loading_scale": 0.0,
        }

    def _compute_branch_flows(self, V: NDArray, theta: NDArray) -> NDArray:
        """Compute active power flow on each line.

        P_{ij} = V_i² G_ij - V_i V_j (G_ij cos(θ_ij) + B_ij sin(θ_ij))

        Returns flow from 'from' bus to 'to' bus direction.
        """
        n_line = self.n_line
        flows = np.zeros(n_line, dtype=np.float64)

        for l, (f, t) in enumerate(self.bus_pairs):
            g = self.G[f, t]
            b = self.B[f, t]
            theta_ft = theta[f] - theta[t]

            # Power flow from f to t
            p_ft = V[f]**2 * g - V[f] * V[t] * (
                g * np.cos(theta_ft) + b * np.sin(theta_ft)
            )
            flows[l] = p_ft * self.base_mva  # Convert to MW

        return flows


class DCPowerFlow:
    """DC power flow solver (linear approximation).

    DC power flow assumes:
      - Flat voltage profile (V ≈ 1.0 p.u.)
      - Small angle differences (sin(θ) ≈ θ, cos(θ) ≈ 1)
      - Negligible resistance (r ≪ x)
      - Reactive power ignored

    Under these assumptions: P = B' * θ
    where B' is the susceptance matrix (imaginary part of Ybus).

    DC power flow is linear and always converges, making it suitable
    for contingency analysis where AC power flow may diverge.

    Usage
    -----
        solver = DCPowerFlow(n_bus, bus_pairs, x_list, base_mva=100.0)
        result = solver.run_power_flow(p_inj, slack_bus=0)
        # result["theta"]   : voltage angles (radians)
        # result["branch_flows"] : active power flows (MW)
    """

    def __init__(
        self,
        n_bus: int,
        bus_pairs: list[tuple[int, int]],
        x_list: list[float],
        base_mva: float = 100.0,
    ):
        self.n_bus = n_bus
        self.bus_pairs = bus_pairs
        self.n_line = len(bus_pairs)
        self.base_mva = base_mva
        self.x_list = x_list

        # Build B' matrix (DC susceptance matrix)
        self._build_bprime(x_list)

    def _build_bprime(self, x_list: list[float]):
        """Build the DC power flow B' matrix.

        B'[i,i] = sum of 1/x_ij for all lines connected to bus i
        B'[i,j] = -1/x_ij for line between bus i and j
        """
        n = self.n_bus
        Bprime = np.zeros((n, n), dtype=np.float64)

        for l, (f, t) in enumerate(self.bus_pairs):
            x = x_list[l]
            if abs(x) < 1e-12:
                continue
            b = 1.0 / x  # susceptance
            Bprime[f, f] += b
            Bprime[t, t] += b
            Bprime[f, t] -= b
            Bprime[t, f] -= b

        self.Bprime = Bprime

    def run_power_flow(
        self,
        p_inj: list[float] | NDArray,
        slack_bus: int = 0,
    ) -> dict:
        """Run DC power flow (linear, always converges).

        Parameters
        ----------
        p_inj : array-like, shape (n_bus,)
            Net active power injection (generation - load) at each bus, in MW.
        slack_bus : int
            Index of the slack/reference bus (θ = 0).

        Returns
        -------
        result : dict
            - theta: voltage angles in radians (n_bus,)
            - converged: always True for DC power flow
            - iterations: 1 (direct solve)
            - mismatch: 0.0
            - branch_flows: active power flow on each line (n_line,)
            - V: flat voltage profile (all 1.0)
        """
        n = self.n_bus
        p_inj = np.asarray(p_inj, dtype=np.float64)

        # Convert to per unit
        p_pu = p_inj / self.base_mva

        # Remove slack bus row/column
        non_slack = [i for i in range(n) if i != slack_bus]
        n_ns = len(non_slack)

        Bprime_reduced = np.zeros((n_ns, n_ns), dtype=np.float64)
        p_reduced = np.zeros(n_ns, dtype=np.float64)

        for i_idx, i in enumerate(non_slack):
            p_reduced[i_idx] = p_pu[i]
            for j_idx, j in enumerate(non_slack):
                Bprime_reduced[i_idx, j_idx] = self.Bprime[i, j]

        # Solve B' * θ = P
        try:
            theta_ns = np.linalg.solve(Bprime_reduced, p_reduced)
        except np.linalg.LinAlgError:
            theta_ns = np.linalg.lstsq(Bprime_reduced, p_reduced, rcond=None)[0]

        # Build full theta vector
        theta = np.zeros(n, dtype=np.float64)
        for idx, bus_idx in enumerate(non_slack):
            theta[bus_idx] = theta_ns[idx]

        # Compute branch flows: P_ij = (θ_i - θ_j) / x_ij  (in MW)
        branch_flows = np.zeros(self.n_line, dtype=np.float64)
        for l, (f, t) in enumerate(self.bus_pairs):
            x_val = self.x_list[l]
            if abs(x_val) > 1e-12:
                branch_flows[l] = (theta[f] - theta[t]) * self.base_mva / x_val
            else:
                branch_flows[l] = 0.0

        return {
            "V": np.ones(n, dtype=np.float64),
            "theta": theta,
            "converged": True,
            "iterations": 1,
            "mismatch": 0.0,
            "branch_flows": branch_flows,
        }

