"""
Unified interface for electrical distance metrics.

Provides:
    - Abstract base: ElectricalDistance
    - Concrete implementations:
        1. PTDFVectorDistance      : ||PTDF_i - PTDF_j||_p
        2. EffectiveResistance     : (e_i-e_j)ᵀ L⁺ (e_i-e_j)
        3. BusLODFDistance         : LODF sensitivity vector distance
        4. PTDFInverseDistance     : 1 / (1 + ||PTDF_i - PTDF_j||)
        5. HybridDistance          : Weighted combination of multiple metrics
        6. GeodesicElectricalHybrid: Geo + electrical weighted hybrid
        7. KCLCurrentDistance      : Current-based distance (KCL framework)
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from abc import ABC, abstractmethod

from .ptdf_calculator import (
    compute_ptdf,
    compute_lodf,
    compute_effective_resistance_matrix,
    compute_ptdf_vector_distance,
    compute_bus_lodf_sensitivity,
)


class ElectricalDistance(ABC):
    """Abstract base class for electrical distance metrics."""

    @abstractmethod
    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        """
        Compute the bus-to-bus distance matrix.

        Parameters
        ----------
        n_bus : int
        bus_pairs : list of (int, int)
        susceptances : list of float

        Returns
        -------
        D : np.ndarray, shape (n_bus, n_bus)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this metric."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of what this metric captures."""


class PTDFVectorDistance(ElectricalDistance):
    """
    Distance based on PTDF column vector differences.

    d(i,j) = ||PTDF[:,i] - PTDF[:,j]||_p

    Interpretation:
        If two buses have similar PTDF vectors, injecting power at either
        bus causes similar flow redistribution across all lines → they are
        "electrically close".
    """

    def __init__(self, p_norm: float = 2.0, slack_bus: int = 0):
        self.p_norm = p_norm
        self.slack_bus = slack_bus

    @property
    def name(self) -> str:
        return f"PTDF Vector Distance (L{self.p_norm})"

    @property
    def description(self) -> str:
        return (
            "Euclidean distance between PTDF column vectors. "
            "Captures similarity in how each bus influences line flows."
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        PTDF = compute_ptdf(n_bus, bus_pairs, susceptances, self.slack_bus)
        return compute_ptdf_vector_distance(PTDF, p_norm=self.p_norm)


class EffectiveResistanceDistance(ElectricalDistance):
    """
    Effective resistance (電氣抵抗) distance.

    R_eff(i,j) = (e_i - e_j)ᵀ · L⁺ · (e_i - e_j)

    Interpretation:
        Treats the power grid as a resistive network where each line has
        conductance b = 1/x. Effective resistance is a true metric and
        is related to the commute time of a random walk on the graph.
    """

    @property
    def name(self) -> str:
        return "Effective Resistance"

    @property
    def description(self) -> str:
        return (
            "Effective resistance between two buses in the weighted "
            "graph (weight = susceptance). A true metric."
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        return compute_effective_resistance_matrix(n_bus, bus_pairs, susceptances)


class BusLODFDistance(ElectricalDistance):
    """
    Distance based on LODF sensitivity vectors.

    For each bus i, compute v_i[k] = mean LODF of lines incident to i
    for outage of line k. Then d(i,j) = ||v_i - v_j||₂.

    Interpretation:
        Two buses are close if they respond similarly to line outages.
    """

    def __init__(self, slack_bus: int = 0):
        self.slack_bus = slack_bus

    @property
    def name(self) -> str:
        return "Bus LODF Sensitivity Distance"

    @property
    def description(self) -> str:
        return (
            "Distance based on LODF sensitivity vectors per bus. "
            "Captures similarity in outage response patterns."
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        PTDF = compute_ptdf(n_bus, bus_pairs, susceptances, self.slack_bus)
        LODF = compute_lodf(PTDF, bus_pairs)
        return compute_bus_lodf_sensitivity(PTDF, LODF, bus_pairs)


class PTDFInverseDistance(ElectricalDistance):
    """
    1 / (1 + PTDF vector distance).

    Maps unbounded PTDF distance to [0, 1].
    Useful when the VR complex needs normalized distances.

    Also includes a variant: d(i,j) = exp(-||PTDF_i - PTDF_j|| / sigma)
    """

    def __init__(self, mode: str = "inverse", sigma: float = 1.0, slack_bus: int = 0):
        """
        Parameters
        ----------
        mode : str
            'inverse' : d = 1 / (1 + norm)
            'gaussian': d = exp(-norm / sigma)
            'logistic': d = 1 / (1 + exp(norm - sigma))
        sigma : float
            Scaling factor for gaussian/logistic modes.
        """
        self.mode = mode
        self.sigma = sigma
        self.slack_bus = slack_bus

    @property
    def name(self) -> str:
        return f"PTDF Inverse ({self.mode})"

    @property
    def description(self) -> str:
        return (
            f"Transformed PTDF distance using {self.mode} function. "
            "Normalized to bounded range for VR complex stability."
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        PTDF = compute_ptdf(n_bus, bus_pairs, susceptances, self.slack_bus)
        D_raw = compute_ptdf_vector_distance(PTDF, p_norm=2.0)

        if self.mode == "inverse":
            return 1.0 / (1.0 + D_raw)
        elif self.mode == "gaussian":
            return np.exp(-D_raw / self.sigma)
        elif self.mode == "logistic":
            return 1.0 / (1.0 + np.exp(D_raw - self.sigma))
        else:
            raise ValueError(f"Unknown mode: {self.mode}")


class HybridDistance(ElectricalDistance):
    """
    Weighted combination of multiple electrical distance metrics.

    D_hybrid = w1 * D1 + w2 * D2 + ...

    This allows experimenting with mixed metrics.
    """

    def __init__(self, components: list[tuple[ElectricalDistance, float]]):
        """
        Parameters
        ----------
        components : list of (ElectricalDistance, weight)
        """
        self.components = components

    @property
    def name(self) -> str:
        names = [c.name[:8] for c, _ in self.components]
        return f"Hybrid({' + '.join(names)})"

    @property
    def description(self) -> str:
        return (
            "Weighted combination: "
            + " + ".join(f"{w}×{c.name}" for c, w in self.components)
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        D_total = None
        for component, weight in self.components:
            D = component.compute(n_bus, bus_pairs, susceptances, **kwargs)
            # Normalize each component to [0, 1] for fair weighting
            d_min, d_max = D.min(), D.max()
            if d_max > d_min:
                D_norm = (D - d_min) / (d_max - d_min)
            else:
                D_norm = D
            if D_total is None:
                D_total = weight * D_norm
            else:
                D_total += weight * D_norm
        return D_total


class GeodesicElectricalHybrid(ElectricalDistance):
    """
    Hybrid of geographic (Euclidean) distance and electrical distance.

    D = w_geo * D_geo + w_elec * D_elec

    This is useful when the grid topology matters alongside geography.
    """

    def __init__(
        self,
        bus_positions: list[tuple[float, float]],
        electrical_metric: ElectricalDistance,
        w_geo: float = 0.3,
        w_elec: float = 0.7,
    ):
        self.bus_positions = bus_positions
        self.electrical_metric = electrical_metric
        self.w_geo = w_geo
        self.w_elec = w_elec

    @property
    def name(self) -> str:
        return f"Geo-Elec Hybrid ({self.electrical_metric.name})"

    @property
    def description(self) -> str:
        return (
            f"Weighted: {self.w_geo}×Geo + {self.w_elec}×{self.electrical_metric.name}"
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        n = len(self.bus_positions)

        # Geographic distance
        D_geo = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                dx = self.bus_positions[i][0] - self.bus_positions[j][0]
                dy = self.bus_positions[i][1] - self.bus_positions[j][1]
                d = np.sqrt(dx**2 + dy**2)
                D_geo[i, j] = d
                D_geo[j, i] = d

        # Normalize geographic
        g_min, g_max = D_geo.min(), D_geo.max()
        if g_max > g_min:
            D_geo = (D_geo - g_min) / (g_max - g_min)

        # Electrical distance
        D_elec = self.electrical_metric.compute(n_bus, bus_pairs, susceptances, **kwargs)
        e_min, e_max = D_elec.min(), D_elec.max()
        if e_max > e_min:
            D_elec = (D_elec - e_min) / (e_max - e_min)

        return self.w_geo * D_geo + self.w_elec * D_elec
class KCLCurrentDistance(ElectricalDistance):
    """
    Distance based on KCL (Kirchhoff's Current Law) current vectors.

    For each bus i, solve the DC power flow with 1 p.u. injection at bus i,
    and compute the resulting line current vector I_i.
    Then d(i, j) = ||I_i - I_j||_p.

    This metric directly uses Ohm's Law and KCL:
        I = Y · V  (current = admittance × voltage)

    Key difference from PTDF distance:
        - PTDF captures power flow *sensitivity*
        - KCL Current captures actual current *distribution*
        - Can incorporate both R and X via the full admittance matrix

    Notes
    -----
    The current implementation uses the DC approximation (susceptance-only).
    When full AC data (R, X, tap ratios) becomes available, the admittance
    matrix can be extended to include all parameters.
    """

    def __init__(self, p_norm: float = 2.0, slack_bus: int = 0):
        self.p_norm = p_norm
        self.slack_bus = slack_bus

    @property
    def name(self) -> str:
        return f"KCL Current Distance (L{self.p_norm})"

    @property
    def description(self) -> str:
        return (
            "Distance based on DC power flow current vectors. "
            "For each bus, injects 1 p.u. power and measures the "
            "resulting line current distribution. "
            "Extensible to full AC via admittance matrix."
        )

    def compute(self, n_bus: int, bus_pairs: list[tuple[int, int]],
                susceptances: list[float], **kwargs) -> NDArray:
        from .ptdf_calculator import (
            build_incidence_matrix,
            build_b_prime_matrix,
        )

        n_line = len(bus_pairs)

        # Build DC power flow matrices
        C = build_incidence_matrix(n_bus, bus_pairs)  # (n_line, n_bus)
        B_prime = build_b_prime_matrix(n_bus, bus_pairs, susceptances, self.slack_bus)

        # Invert B' (reduced, slack removed)
        B_inv = np.linalg.inv(B_prime)

        # b vector (line susceptances)
        b = np.array(susceptances, dtype=np.float64)

        # Mask for non-slack buses
        mask = np.ones(n_bus, dtype=bool)
        mask[self.slack_bus] = False

        # For each bus, compute the current vector
        # I_i[l] = b[l] * (C[l, :] · θ)
        # where θ is the voltage angle solution for injection at bus i
        current_vectors = np.zeros((n_bus, n_line), dtype=np.float64)

        for i in range(n_bus):
            if i == self.slack_bus:
                # Slack bus: zero injection assumption
                continue

            # Injection vector: 1 p.u. at bus i (non-slack)
            P_inj = np.zeros(n_bus - 1)
            idx = np.where(mask)[0]
            bus_pos = list(idx).index(i)  # position of bus i in reduced system
            P_inj[bus_pos] = 1.0

            # Solve for voltage angles: θ_reduced = B_inv · P_inj
            theta_reduced = B_inv @ P_inj

            # Expand to full θ vector (slack = 0)
            theta = np.zeros(n_bus)
            theta[mask] = theta_reduced

            # Line flows: P_line[l] = b[l] * (C[l, f] * θ_f + C[l, t] * θ_t)
            # In DC approx, current I ≈ power flow P (since V ≈ 1 p.u.)
            I_line = b * (C @ theta)

            current_vectors[i, :] = I_line

        # Compute distance matrix: d(i,j) = ||I_i - I_j||_p
        D = np.zeros((n_bus, n_bus), dtype=np.float64)
        for i in range(n_bus):
            for j in range(i + 1, n_bus):
                diff = current_vectors[i, :] - current_vectors[j, :]
                dist = np.linalg.norm(diff, ord=self.p_norm)
                D[i, j] = dist
                D[j, i] = dist

        return D

