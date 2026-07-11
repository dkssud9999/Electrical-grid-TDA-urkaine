"""
Vietoris-Rips complex computation core.

Given a distance matrix D (n × n), computes:
  - H₀ persistence pairs (connected components)
  - H₁ persistence pairs (cycles)
  - Betti curves β₀(α), β₁(α) for any threshold α

Pure numpy — no scipy needed.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class VRComplex:
    """
    Vietoris-Rips complex from a distance matrix.

    Usage:
        vr = VRComplex(distance_matrix)
        h0, h1 = vr.persistence_pairs()
        b0, b1 = vr.betti_numbers(alpha=0.5)
    """

    def __init__(self, distance_matrix: NDArray):
        self.D = np.asarray(distance_matrix, dtype=np.float64)
        self.n = self.D.shape[0]
        assert self.D.shape == (self.n, self.n)
        assert np.allclose(self.D, self.D.T), "Distance matrix must be symmetric"

        # Pre-compute sorted unique distances
        triu = np.triu_indices(self.n, k=1)
        self._all_dists = np.sort(np.unique(self.D[triu]))
        if len(self._all_dists) == 0:
            self._all_dists = np.array([0.0])

        # Sorted pairs (d, i, j)
        pairs = []
        for i in range(self.n):
            for j in range(i + 1, self.n):
                pairs.append((self.D[i, j], i, j))
        pairs.sort(key=lambda x: x[0])
        self._sorted_pairs = pairs

        self._max_dist = float(self._all_dists[-1]) if len(self._all_dists) > 0 else 0.0
        self._h0_pairs: list | None = None
        self._h1_pairs: list | None = None

    @property
    def unique_thresholds(self) -> NDArray:
        return self._all_dists

    @property
    def max_distance(self) -> float:
        return self._max_dist

    # ── Union-Find helpers ──────────────────────────────────

    @staticmethod
    def _make_uf(n: int) -> tuple[list[int], list[int]]:
        return list(range(n)), list(range(n))

    @staticmethod
    def _uf_find(parent: list[int], x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    @staticmethod
    def _uf_union(parent: list[int], x: int, y: int):
        px = VRComplex._uf_find(parent, x)
        py = VRComplex._uf_find(parent, y)
        if px != py:
            parent[px] = py

    # ── Persistence ─────────────────────────────────────────

    def persistence_pairs(self) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """
        H₀ and H₁ persistence via union-find over increasing distance.

        Computes H₁ deaths properly by tracking when triangles (2-simplices)
        are completed in the Vietoris-Rips complex. A triangle [i,j,k] is
        present at distance α when all three edges have distance ≤ α.
        When a triangle is completed, it kills the H₁ cycle created by the
        most recently added edge among its three edges.

        Returns
        -------
        h0_pairs : list of (birth, death)
        h1_pairs : list of (birth, death)
        """
        if self._h0_pairs is not None:
            return self._h0_pairs, self._h1_pairs

        infinity = self._max_dist * 1.5 if self._max_dist > 0 else 1.0

        parent = list(range(self.n))
        comp_birth = [0.0] * self.n
        h0, h1 = [], []

        # Track existing edges for triangle detection
        edge_exists: dict[tuple[int, int], float] = {}

        # Track active H₁ cycles: list of (birth_distance, edge_tuple)
        active_cycles: list[tuple[float, tuple[int, int]]] = []

        for d, i, j in self._sorted_pairs:
            pi = self._uf_find(parent, i)
            pj = self._uf_find(parent, j)

            if pi != pj:
                # ── H₀: components merge ──
                if comp_birth[pi] <= comp_birth[pj]:
                    dying, surviving = pj, pi
                else:
                    dying, surviving = pi, pj
                h0.append((comp_birth[dying], d))
                comp_birth[surviving] = min(comp_birth[surviving], comp_birth[dying])
                self._uf_union(parent, i, j)
            else:
                # ── H₁: cycle born ──
                active_cycles.append((d, (i, j)))

            # Record edge
            edge_exists[(i, j)] = d
            edge_exists[(j, i)] = d

            # ── Check triangles: find k such that (i,k) and (j,k) also exist ──
            for k in range(self.n):
                if k == i or k == j:
                    continue
                if (i, k) in edge_exists and (j, k) in edge_exists:
                    d_ik = edge_exists[(i, k)]
                    d_jk = edge_exists[(j, k)]

                    # The triangle is completed when the last edge is added:
                    triangle_complete_at = max(d, d_ik, d_jk)

                    # The three edges of this triangle, sorted by distance
                    # descending (youngest / most recently added edge first)
                    tri_edges = [(d, i, j), (d_ik, i, k), (d_jk, j, k)]
                    tri_edges.sort(key=lambda x: -x[0])

                    # Find the youngest edge that still has an active H₁ cycle.
                    # This implements the standard "youngest edge rule" for
                    # Vietoris-Rips persistence.
                    killed = False
                    for _, ei, ej in tri_edges:
                        for ci, (bd, (cei, cej)) in enumerate(active_cycles):
                            if (ei, ej) == (cei, cej) or (ei, ej) == (cej, cei):
                                h1.append((bd, triangle_complete_at))
                                active_cycles.pop(ci)
                                killed = True
                                break
                        if killed:
                            break

        # Remaining active cycles survive to infinity
        for bd, _ in active_cycles:
            h1.append((bd, infinity))

        survivors = set(self._uf_find(parent, i) for i in range(self.n))
        for s in survivors:
            h0.append((comp_birth[s], infinity))

        self._h0_pairs, self._h1_pairs = h0, h1
        return h0, h1

    def betti_numbers(self, alpha: float) -> tuple[int, int]:
        """β₀ and β₁ at threshold α."""
        parent, _ = self._make_uf(self.n)
        edge_count = 0
        for d, i, j in self._sorted_pairs:
            if d > alpha:
                break
            self._uf_union(parent, i, j)
            edge_count += 1
        components = set(self._uf_find(parent, i) for i in range(self.n))
        b0 = len(components)
        b1 = edge_count - self.n + b0
        return b0, max(b1, 0)

    def betti_curves(self) -> tuple[NDArray, NDArray, NDArray]:
        """Thresholds, β₀ values, β₁ values for all unique thresholds."""
        thr = self._all_dists
        b0v = np.zeros_like(thr, dtype=int)
        b1v = np.zeros_like(thr, dtype=int)
        for idx, a in enumerate(thr):
            b0v[idx], b1v[idx] = self.betti_numbers(float(a))
        return thr, b0v, b1v

