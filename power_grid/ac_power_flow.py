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
    # result["branch_loading"] : flow / rate for each line
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
                    # ── Diagonal: ∂Pi/∂θi = -Qi - Bii·Vi² ──
                    J1[i_pvpq, j_pvpq] = -Q_calc[i] - b_ij * V[i]**2

                    # ── J2 diagonal: ∂Pi/∂Vi = Pi/Vi + Gii·Vi ──
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        if abs(V[i]) > 1e-12:
                            J2[i_pvpq, i_pq] = P_calc[i] / V[i] + g_ij * V[i]
                        else:
                            J2[i_pvpq, i_pq] = g_ij * V[i]

                    # ── J3 diagonal: ∂Qi/∂θi = Pi - Gii·Vi² ──
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        J3[i_pq, j_pvpq] = P_calc[i] - g_ij * V[i]**2

                    # ── J4 diagonal: ∂Qi/∂Vi = Qi/Vi - Bii·Vi ──
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        if abs(V[i]) > 1e-12:
                            J4[i_pq, i_pq] = Q_calc[i] / V[i] - b_ij * V[i]
                        else:
                            J4[i_pq, i_pq] = -b_ij * V[i]

                else:
                    # ── Off-diagonal: ∂Pi/∂θj ──
                    J1[i_pvpq, j_pvpq] = V[i] * V[j] * (
                        g_ij * np.sin(theta_ij) - b_ij * np.cos(theta_ij)
                    )

                    # ── Off-diagonal: ∂Pi/∂Vj ──
                    if pq_mask[j]:
                        j_pq = bus_to_pq[j]
                        J2[i_pvpq, j_pq] = V[i] * (
                            g_ij * np.cos(theta_ij) + b_ij * np.sin(theta_ij)
                        )

                    # ── Off-diagonal: ∂Qi/∂θj ──
                    if pq_mask[i]:
                        i_pq = bus_to_pq[i]
                        J3[i_pq, j_pvpq] = -V[i] * V[j] * (
                            g_ij * np.cos(theta_ij) + b_ij * np.sin(theta_ij)
                        )

                    # ── Off-diagonal: ∂Qi/∂Vj ──
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

    def run_power_flow(
        self,
        p_inj: list[float] | NDArray,
        q_inj: list[float] | NDArray | None = None,
        slack_bus: int = 0,
        pv_buses: list[int] | None = None,
        v_setpoints: list[float] | None = None,
        max_iter: int = 20,
        tolerance: float = 1e-8,
    ) -> dict:
        """Run Newton-Raphson AC power flow.

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
            Default: all generator buses except slack.
        v_setpoints : list of float, optional
            Voltage setpoints for PV buses. Default: 1.0 p.u. for all.
        max_iter : int
            Maximum Newton-Raphson iterations.
        tolerance : float
            Convergence tolerance for power mismatches.

        Returns
        -------
        result : dict
            - V: voltage magnitudes (n_bus,)
            - theta: voltage angles in radians (n_bus,)
            - converged: bool
            - iterations: int
            - mismatch: final max mismatch
            - branch_flows: active power flow on each line (n_line,)
            - branch_loading: flow / rate for each line (n_line,) or None
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
        p_sched = p_inj / base
        q_sched = q_inj / base

        # Newton-Raphson iteration
        mismatch = float("inf")
        for iteration in range(max_iter):
            delta_p, delta_q = self._compute_mismatch(
                V, theta, p_sched, q_sched, pv_mask, pq_mask
            )

            mismatch = np.max(np.abs(np.concatenate([delta_p, delta_q])))
            if mismatch < tolerance:
                # Compute branch flows
                branch_flows = self._compute_branch_flows(V, theta)
                return {
                    "V": V,
                    "theta": theta,
                    "converged": True,
                    "iterations": iteration,
                    "mismatch": float(mismatch),
                    "branch_flows": branch_flows,
                }

            J = self._build_jacobian(V, theta, pv_mask, pq_mask)

            # Solve J * Δx = ΔS  (Newton-Raphson: J * Δx = -(S_calc - S_sched) = S_sched - S_calc = ΔS)
            try:
                delta_x = np.linalg.solve(J, np.concatenate([delta_p, delta_q]))
            except np.linalg.LinAlgError:
                # Jacobian singular — try pseudo-inverse
                delta_x = np.linalg.lstsq(J, np.concatenate([delta_p, delta_q]), rcond=None)[0]

            # Extract Δθ and ΔV
            n_pv_pq = np.sum(pv_mask | pq_mask)
            n_pq = np.sum(pq_mask)

            delta_theta = delta_x[:n_pv_pq]
            delta_v = delta_x[n_pv_pq:]

            # Update angles for non-slack buses
            idx = 0
            for i in range(n):
                if pv_mask[i] or pq_mask[i]:
                    theta[i] += delta_theta[idx]
                    idx += 1

            # Update voltages for PQ buses
            idx = 0
            for i in range(n):
                if pq_mask[i]:
                    V[i] *= (1.0 + delta_v[idx])
                    # Clamp voltage to reasonable range
                    V[i] = max(0.5, min(1.5, V[i]))
                    idx += 1

        # Did not converge — compute best-effort branch flows
        branch_flows = self._compute_branch_flows(V, theta)
        return {
            "V": V,
            "theta": theta,
            "converged": False,
            "iterations": max_iter,
            "mismatch": float(mismatch) if 'mismatch' in locals() else float('inf'),
            "branch_flows": branch_flows,
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

