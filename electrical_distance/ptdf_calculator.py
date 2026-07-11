"""
PTDF (Power Transfer Distribution Factor) & LODF (Line Outage Distribution Factor)
calculation core.

All computations assume the DC power flow model:
    P = B' · θ
    PTDF = diag(b) · C · (B')⁻¹

where:
    - B'   : n_bus × n_bus susceptance matrix (DC近似)
    - C    : n_line × n_bus incidence matrix
    - b    : n_line vector of line susceptances
    - PTDF : n_line × n_bus matrix
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from typing import Optional


def build_incidence_matrix(n_bus: int, bus_pairs: list[tuple[int, int]]) -> NDArray:
    """
    Build the line-to-bus incidence matrix C (n_line × n_bus).

    C[l, k] =  1  if bus k is the 'from' end of line l
               -1 if bus k is the 'to'   end of line l
                0 otherwise

    Parameters
    ----------
    n_bus : int
        Number of buses (nodes) in the grid.
    bus_pairs : list of (int, int)
        Each element is (from_bus_idx, to_bus_idx).

    Returns
    -------
    C : np.ndarray, shape (n_line, n_bus)
    """
    n_line = len(bus_pairs)
    C = np.zeros((n_line, n_bus), dtype=np.float64)
    for l, (f, t) in enumerate(bus_pairs):
        C[l, f] = 1.0
        C[l, t] = -1.0
    return C


def build_b_prime_matrix(
    n_bus: int,
    bus_pairs: list[tuple[int, int]],
    susceptances: list[float],
    slack_bus: int = 0,
) -> NDArray:
    """
    Build the DC power flow susceptance matrix B' (n_bus × n_bus).

    B'[i, i] =  Σ b_k   (sum of susceptances of lines incident to bus i)
    B'[i, j] = -b_{ij}  (negative susceptance of line between i and j)

    The slack bus row/column is then removed for inversion.

    Parameters
    ----------
    n_bus : int
        Number of buses.
    bus_pairs : list of (int, int)
        (from, to) for each line.
    susceptances : list of float
        Susceptance (b = 1 / x) for each line.
    slack_bus : int
        Index of the slack/reference bus.

    Returns
    -------
    B_prime : np.ndarray, shape (n_bus - 1, n_bus - 1)
        Reduced B' matrix (slack bus excluded).
    """
    B_full = np.zeros((n_bus, n_bus), dtype=np.float64)
    for l, (f, t) in enumerate(bus_pairs):
        b = susceptances[l]
        B_full[f, f] += b
        B_full[t, t] += b
        B_full[f, t] -= b
        B_full[t, f] -= b

    # Remove slack bus (row and col)
    mask = np.ones(n_bus, dtype=bool)
    mask[slack_bus] = False
    B_prime = B_full[np.ix_(mask, mask)]
    return B_prime


def compute_ptdf(
    n_bus: int,
    bus_pairs: list[tuple[int, int]],
    susceptances: list[float],
    slack_bus: int = 0,
) -> NDArray:
    """
    Compute the PTDF matrix (n_line × n_bus).

    Implements: PTDF = diag(b) · C · (B'_reduced)⁻¹ · expansion

    Steps:
    1. Build incidence matrix C
    2. Build reduced B' matrix
    3. Invert B'
    4. Multiply: PTDF = diag(b) @ C_reduced @ B'_inv

    The expansion step adds back the slack column (zeros).

    Parameters
    ----------
    n_bus : int
    bus_pairs : list of (int, int)
    susceptances : list of float
    slack_bus : int

    Returns
    -------
    PTDF : np.ndarray, shape (n_line, n_bus)
    """
    n_line = len(bus_pairs)

    # Incidence matrix (n_line × n_bus)
    C = build_incidence_matrix(n_bus, bus_pairs)

    # Reduced B' (n_bus - 1 × n_bus - 1)
    B_prime = build_b_prime_matrix(n_bus, bus_pairs, susceptances, slack_bus)

    # Check condition number
    cond = np.linalg.cond(B_prime)
    if cond > 1e12:
        raise ValueError(
            f"B' matrix is near-singular (condition number: {cond:.2e}). "
            "Check for disconnected buses or redundant lines."
        )

    B_prime_inv = np.linalg.inv(B_prime)

    # b vector as diagonal matrix (n_line × n_line)
    b_diag = np.diag(np.array(susceptances, dtype=np.float64))

    # Remove slack bus column from C → C_reduced (n_line × (n_bus - 1))
    mask = np.ones(n_bus, dtype=bool)
    mask[slack_bus] = False
    C_reduced = C[:, mask]

    # PTDF_reduced = diag(b) · C_reduced · (B')⁻¹  →  (n_line × (n_bus - 1))
    PTDF_reduced = b_diag @ C_reduced @ B_prime_inv

    # Insert slack bus column (all zeros)
    PTDF = np.zeros((n_line, n_bus), dtype=np.float64)
    PTDF[:, mask] = PTDF_reduced

    return PTDF


def compute_lodf(
    PTDF: NDArray,
    bus_pairs: list[tuple[int, int]],
) -> NDArray:
    """
    Compute the LODF (Line Outage Distribution Factor) matrix.

    LODF_{l, k} = change in flow on line l when line k is outaged.

    Formula:
        Δ_k = e_from(k) - e_to(k)   (bus injection shift vector)
        num = PTDF[l, :] · Δ_k
        den = 1 - PTDF[k, :] · Δ_k
        LODF_{l, k} = num / den

    Bridge / leaf-line handling
    ---------------------------
    When a line is the only connection between a bus and the rest of
    the grid (e.g. a radial line), its outage causes islanding and the
    denominator becomes zero.  In this case LODF is not defined by the
    standard formula, but for practical computation we set:

        LODF[l, k] = 0  for l ≠ k

    which means "the outage of this bridge line does not affect flow
    on other lines in the remaining connected grid".  This is a
    standard approximation in contingency analysis for radial lines.

    Parameters
    ----------
    PTDF : np.ndarray, shape (n_line, n_bus)
    bus_pairs : list of (int, int)
        (from, to) for each line.

    Returns
    -------
    LODF : np.ndarray, shape (n_line, n_line)
        LODF[l, k] is the impact on line l when line k is outaged.
        Diagonal is -1 (a line cannot monitor itself).
    """
    n_line = len(bus_pairs)
    LODF = np.zeros((n_line, n_line), dtype=np.float64)

    for k in range(n_line):
        f_k, t_k = bus_pairs[k]

        # PTDF sensitivity for outage of line k
        # ΔP_l_on_k_outage = PTDF[l, f_k] - PTDF[l, t_k]
        delta_k = PTDF[:, f_k] - PTDF[:, t_k]

        # Denominator: 1 - PTDF[k, f_k] + PTDF[k, t_k]
        denom = 1.0 - (PTDF[k, f_k] - PTDF[k, t_k])

        if abs(denom) < 1e-12:
            # Bridge / leaf line: outage causes islanding.
            # Standard LODF is undefined; set to 0 (no effect on other lines).
            LODF[:, k] = 0.0
        else:
            LODF[:, k] = delta_k / denom

        # A line cannot be monitored by itself
        LODF[k, k] = -1.0

    return LODF


def compute_effective_resistance_matrix(
    n_bus: int,
    bus_pairs: list[tuple[int, int]],
    susceptances: list[float],
) -> NDArray:
    """
    Compute the effective resistance matrix (n_bus × n_bus).

    Formula:
        R_eff(i, j) = (e_i - e_j)ᵀ · L⁺ · (e_i - e_j)
    where L is the weighted Laplacian (L = Cᵀ · diag(b) · C).

    Note: Effective resistance is a *metric* (symmetric, triangle ineq. holds)
    and represents the "electrical distance" between two buses.

    Parameters
    ----------
    n_bus : int
    bus_pairs : list of (int, int)
    susceptances : list of float

    Returns
    -------
    R : np.ndarray, shape (n_bus, n_bus)
        Symmetric matrix of effective resistances.
        Diagonal is 0.
    """
    C = build_incidence_matrix(n_bus, bus_pairs)
    b_diag = np.diag(np.array(susceptances, dtype=np.float64))

    # Weighted Laplacian: L = Cᵀ · diag(b) · C
    L = C.T @ b_diag @ C

    # Moore-Penrose pseudo-inverse
    L_pinv = np.linalg.pinv(L)

    # Compute R_eff(i, j) for all pairs
    R = np.zeros((n_bus, n_bus), dtype=np.float64)
    for i in range(n_bus):
        for j in range(i + 1, n_bus):
            diff = np.zeros(n_bus, dtype=np.float64)
            diff[i] = 1.0
            diff[j] = -1.0
            r = diff @ L_pinv @ diff
            R[i, j] = r
            R[j, i] = r

    return R


def compute_ptdf_vector_distance(
    PTDF: NDArray,
    p_norm: float = 2.0,
) -> NDArray:
    """
    Compute bus-to-bus distance using PTDF vector differences.

    d(i, j) = ||PTDF[:, i] - PTDF[:, j]||_p

    The intuition: two buses are "electrically close" if injecting
    power at either bus causes similar flow patterns on all lines.

    Parameters
    ----------
    PTDF : np.ndarray, shape (n_line, n_bus)
    p_norm : float
        Norm order (default: 2 = Euclidean).

    Returns
    -------
    D : np.ndarray, shape (n_bus, n_bus)
        Distance matrix. Diagonal is 0.
    """
    n_bus = PTDF.shape[1]
    D = np.zeros((n_bus, n_bus), dtype=np.float64)

    for i in range(n_bus):
        for j in range(i + 1, n_bus):
            diff = PTDF[:, i] - PTDF[:, j]
            dist = np.linalg.norm(diff, ord=p_norm)
            D[i, j] = dist
            D[j, i] = dist

    return D


def compute_bus_lodf_sensitivity(
    PTDF: NDArray,
    LODF: NDArray,
    bus_pairs: list[tuple[int, int]],
) -> NDArray:
    """
    Compute a bus-level distance based on LODF sensitivity.

    For each bus i, compute a vector v_i where:
        v_i[k] = Σ_{l incident to bus i} PTDF[l, i] · LODF[l, k]

    This weights each incident line's LODF outage impact by the PTDF
    sensitivity of that line at bus i. Intuitively:
        "When line k goes out, how does the flow change on lines
         incident to bus i, weighted by bus i's injection influence
         on those lines?"

    The PTDF weighting breaks the symmetry that pure LODF aggregation
    (sum of |LODF|) exhibits on symmetric grids, where symmetric buses
    produce identical sensitivity vectors.

    Then d(i, j) = ||v_i - v_j||₂.

    Parameters
    ----------
    PTDF : np.ndarray, shape (n_line, n_bus)
    LODF : np.ndarray, shape (n_line, n_line)
    bus_pairs : list of (int, int)

    Returns
    -------
    D : np.ndarray, shape (n_bus, n_bus)
    """
    n_line, n_bus = PTDF.shape

    # For each bus, compute which lines are incident to it
    bus_to_lines: list[list[int]] = [[] for _ in range(n_bus)]
    for l, (f, t) in enumerate(bus_pairs):
        bus_to_lines[f].append(l)
        bus_to_lines[t].append(l)

    # Build bus sensitivity vectors using PTDF-weighted signed LODF.
    # Using PTDF[l,i] as weight breaks the symmetry that pure |LODF|
    # aggregation exhibits on symmetric grids, since PTDF vectors are
    # unique per bus even in symmetric configurations.
    v = np.zeros((n_bus, n_line), dtype=np.float64)
    for i in range(n_bus):
        incident = bus_to_lines[i]
        if incident:
            for l in incident:
                v[i, :] += PTDF[l, i] * LODF[l, :]

    # Distance matrix
    D = np.zeros((n_bus, n_bus), dtype=np.float64)
    for i in range(n_bus):
        for j in range(i + 1, n_bus):
            dist = np.linalg.norm(v[i, :] - v[j, :])
            D[i, j] = dist
            D[j, i] = dist

    return D

