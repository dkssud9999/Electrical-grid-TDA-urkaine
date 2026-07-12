#!/usr/bin/env python3
"""
Batch experiment: Compare all distance metrics on a power grid.

Loads a power grid (default: Ukraine 18-bus), computes all electrical
distance metrics, runs persistence homology on each, and compares the
H1 cycle edges against N-1 contingency analysis (AC power flow based).

Outputs:
  - Formatted table to stdout
  - JSON report file (optional)
  - CSV summary file (optional)

Usage
-----
    # Ukraine 18-bus (default)
    python scripts/compare_metrics.py

    # Ukraine 28-bus
    python scripts/compare_metrics.py --grid 28

    # Custom grid with JSON export
    python scripts/compare_metrics.py --grid 18 --output report.json

    # CSV export
    python scripts/compare_metrics.py --grid 28 --csv results.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import numpy as np

# Ensure we can import from the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_grid(grid_name: str = "18") -> dict:
    """Load a Ukraine power grid by name."""
    if grid_name == "28":
        from power_grid.ukraine_loader import get_large_ukraine_grid
        return get_large_ukraine_grid()
    else:
        from power_grid.ukraine_loader import get_ukraine_330kv_grid
        return get_ukraine_330kv_grid()


def compute_all_distance_matrices(grid_data: dict) -> dict[str, np.ndarray]:
    """Compute all electrical distance matrices for a grid.

    Returns
    -------
    dict of str -> np.ndarray
        name -> distance matrix (n_bus × n_bus)
    """
    from electrical_distance.ptdf_calculator import (
        compute_ptdf,
        compute_lodf,
        compute_effective_resistance_matrix,
        compute_ptdf_vector_distance,
        compute_bus_lodf_sensitivity,
        build_incidence_matrix,
    )

    n_bus = len(grid_data["buses"])
    bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid_data["lines"]]
    susceptances = [1.0 / max(l["x"], 1e-6) for l in grid_data["lines"]]

    # Base computations shared by multiple metrics
    PTDF = compute_ptdf(n_bus, bus_pairs, susceptances)
    LODF = compute_lodf(PTDF, bus_pairs)
    LODF_pinv = np.linalg.pinv(LODF)
    C = build_incidence_matrix(n_bus, bus_pairs)

    matrices: dict[str, np.ndarray] = {}

    # 1. PTDF Vector (L2)
    matrices["PTDF Vector (L2)"] = compute_ptdf_vector_distance(PTDF, p_norm=2)

    # 2. PTDF Vector (L1)
    matrices["PTDF Vector (L1)"] = compute_ptdf_vector_distance(PTDF, p_norm=1)

    # 3. Effective Resistance
    matrices["Effective Resistance"] = compute_effective_resistance_matrix(
        n_bus, bus_pairs, susceptances
    )

    # 4. Bus LODF Sensitivity
    matrices["Bus LODF Sensitivity"] = compute_bus_lodf_sensitivity(
        PTDF, LODF, bus_pairs
    )

    # 5. PTDF Inverse
    D_ptdf_l2 = matrices["PTDF Vector (L2)"]
    matrices["PTDF Inverse"] = 1.0 / (1.0 + D_ptdf_l2)

    # 6. LODF Inverse (pseudo-inverse based)
    n_line = len(bus_pairs)
    profiles = np.zeros((n_bus, n_line), dtype=np.float64)
    for i in range(n_bus):
        profiles[i, :] = C[:, i] @ LODF_pinv
    D_lodf_inv = np.zeros((n_bus, n_bus), dtype=np.float64)
    for i in range(n_bus):
        for j in range(i + 1, n_bus):
            dist = np.linalg.norm(profiles[i] - profiles[j], ord=2)
            D_lodf_inv[i, j] = dist
            D_lodf_inv[j, i] = dist
    matrices["LODF Inverse"] = D_lodf_inv

    # 7. KCL Current Distance
    from electrical_distance.metrics import KCLCurrentDistance
    kcl = KCLCurrentDistance(p_norm=2)
    matrices["KCL Current"] = kcl.compute(n_bus, bus_pairs, susceptances)

    # 8. Geographic (Euclidean) - from bus positions
    positions = [(b.get("x", 0), b.get("y", 0)) for b in grid_data["buses"]]
    n = len(positions)
    D_geo = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            d = np.sqrt(dx * dx + dy * dy)
            D_geo[i, j] = d
            D_geo[j, i] = d
    matrices["Geographic (Euclidean)"] = D_geo

    return matrices


def compute_homology_info(
    D: np.ndarray,
) -> dict[str, Any]:
    """Compute persistence homology info for a distance matrix."""
    from tda.vr_core import VRComplex

    vr = VRComplex(D)
    h0_pairs, h1_pairs = vr.persistence_pairs()

    max_dist = vr.max_distance
    infinity = max_dist * 1.5 if max_dist > 0 else 1.0
    n_h1_persistent = sum(1 for _, d in h1_pairs if d < infinity)

    return {
        "n_h0": len(h0_pairs),
        "n_h1": len(h1_pairs),
        "n_h1_persistent": n_h1_persistent,
        "max_distance": float(max_dist),
        "h1_persistence": [
            float(d - b) if d < infinity else float("inf")
            for b, d in h1_pairs
        ],
    }


def run_experiment(
    grid_data: dict,
    grid_name: str = "Ukraine 18-bus",
) -> dict[str, Any]:
    """Run the full experiment pipeline.

    1. Compute all distance matrices
    2. Run N-1 contingency analysis
    3. For each metric: compute homology + alignment with N-1
    4. Sort metrics by alignment score
    """
    from tda.vulnerability import compare_metrics_vulnerability

    print(f"\n{'='*70}")
    print(f"  Experiment: {grid_name}")
    print(f"  Buses: {len(grid_data['buses'])}  Lines: {len(grid_data['lines'])}")
    print(f"{'='*70}")

    # Step 1: Compute all distance matrices
    print("\n[1/4] Computing distance matrices...")
    t0 = time.time()
    distance_matrices = compute_all_distance_matrices(grid_data)
    t1 = time.time()
    print(f"  → {len(distance_matrices)} metrics computed in {t1-t0:.2f}s")

    # Step 2: Run N-1 contingency analysis
    print("\n[2/4] Running N-1 contingency analysis (AC power flow)...")
    t0 = time.time()
    from power_grid.contingency import N1ContingencyAnalyzer

    analyzer = N1ContingencyAnalyzer(grid_data)
    n1_result = analyzer.analyze()
    t1 = time.time()
    print(f"  → {n1_result['n_vulnerable']}/{n1_result['total_edges']} "
          f"vulnerable edges ({n1_result['vulnerability_ratio']*100:.1f}%) "
          f"in {t1-t0:.2f}s")

    # Step 3: Compute homology + alignment for each metric
    print("\n[3/4] Computing persistence homology & alignment...")
    t0 = time.time()

    comparison = compare_metrics_vulnerability(grid_data, distance_matrices)
    t1 = time.time()
    print(f"  → Done in {t1-t0:.2f}s")

    # Step 4: Also collect homology info for each metric
    print("\n[4/4] Collecting homology details...")
    homology_info = {}
    for name, D in distance_matrices.items():
        homology_info[name] = compute_homology_info(D)

    # Build result
    result = {
        "experiment": {
            "grid_name": grid_name,
            "n_bus": comparison["n_bus"],
            "n_line": comparison["n_line"],
            "n_vulnerable": len(comparison["n1_vulnerable"]),
            "vulnerability_ratio": n1_result["vulnerability_ratio"],
        },
        "n1_vulnerable_edges": [
            int(eid) for eid in sorted(comparison["n1_vulnerable"])
        ],
        "n1_vulnerable_details": comparison["n1_vulnerable_details"],
        "metrics_sorted": comparison["metrics"],
        "results": {},
    }

    for name in comparison["metrics"]:
        r = comparison["results"][name]
        h = homology_info.get(name, {})
        result["results"][name] = {
            "alignment_score": r["alignment_score"],
            "precision": r["precision"],
            "recall": r["recall"],
            "specificity": r["specificity"],
            "n_cycle_edges": r["n_cycle_edges"],
            "n_intersection": r["n_intersection"],
            "n_h0": h.get("n_h0", 0),
            "n_h1": h.get("n_h1", 0),
            "n_h1_persistent": h.get("n_h1_persistent", 0),
            "max_distance": h.get("max_distance", 0),
        }

    return result


def print_report(result: dict[str, Any]):
    """Print formatted report to stdout."""
    exp = result["experiment"]

    print(f"\n{'='*70}")
    print(f"  REPORT: {exp['grid_name']}")
    print(f"  {exp['n_bus']} buses, {exp['n_line']} lines")
    print(f"  N-1 Vulnerable: {exp['n_vulnerable']}/{exp['n_line']} "
          f"({exp['vulnerability_ratio']*100:.1f}%)")
    print(f"{'='*70}")

    # Vulnerable edges
    if result["n1_vulnerable_details"]:
        print(f"\n  N-1 Vulnerable Edges:")
        for e in result["n1_vulnerable_details"]:
            violations = ", ".join(e["violations"])
            print(f"    L{e['id']:>3} ({e['name']:<25}): {violations}")

    # Metric ranking
    print(f"\n  {'Metric':<28} {'Align':>8} {'Prec':>8} {'Recall':>8} "
          f"{'Spec':>8} {'H1 edges':>10} {'Intersect':>10}")
    print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")

    for rank, name in enumerate(result["metrics_sorted"], 1):
        r = result["results"][name]
        print(f"  #{rank:<2} {name:<26} {r['alignment_score']:>8.4f} "
              f"{r['precision']:>8.4f} {r['recall']:>8.4f} "
              f"{r['specificity']:>8.4f} {r['n_cycle_edges']:>10} "
              f"{r['n_intersection']:>10}")

    # Best metric
    best_name = result["metrics_sorted"][0]
    best = result["results"][best_name]
    print(f"\n  ★ Best Metric: {best_name}")
    print(f"    Alignment Score: {best['alignment_score']:.4f}")
    print(f"    Precision:       {best['precision']:.4f}")
    print(f"    Recall:          {best['recall']:.4f}")

    # Homology summary
    print(f"\n  Homology Summary:")
    for name in result["metrics_sorted"]:
        r = result["results"][name]
        print(f"    {name:<26}: H0={r['n_h0']:>3}  "
              f"H1={r['n_h1']:>3}  H1_persistent={r['n_h1_persistent']:>3}  "
              f"max_d={r['max_distance']:.2f}")

    print()


def export_json(result: dict[str, Any], path: str):
    """Export result to JSON file."""
    # Convert numpy types to native Python types
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            return convert(obj)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder, ensure_ascii=False)
    print(f"  → JSON report saved to: {path}")


def export_csv(result: dict[str, Any], path: str):
    """Export metric comparison summary to CSV."""
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "Metric", "Alignment Score", "Precision", "Recall",
            "Specificity", "H1 Cycle Edges", "Intersection",
            "H0 Pairs", "H1 Pairs", "H1 Persistent", "Max Distance",
        ])
        for rank, name in enumerate(result["metrics_sorted"], 1):
            r = result["results"][name]
            writer.writerow([
                rank, name,
                f"{r['alignment_score']:.6f}",
                f"{r['precision']:.6f}",
                f"{r['recall']:.6f}",
                f"{r['specificity']:.6f}",
                r["n_cycle_edges"],
                r["n_intersection"],
                r["n_h0"],
                r["n_h1"],
                r["n_h1_persistent"],
                f"{r['max_distance']:.4f}",
            ])
    print(f"  → CSV report saved to: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare all distance metrics on a power grid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--grid", "-g",
        default="18",
        choices=["18", "28"],
        help="Ukraine grid: 18-bus (default) or 28-bus",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Export results to JSON file",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Export metric comparison to CSV file",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed report (useful with --output)",
    )

    args = parser.parse_args()

    # Load grid
    grid_name = f"Ukraine {args.grid}-bus"
    grid_data = load_grid(args.grid)

    # Run experiment
    result = run_experiment(grid_data, grid_name=grid_name)

    # Print report
    if not args.quiet:
        print_report(result)

    # Export
    if args.output:
        export_json(result, args.output)

    if args.csv:
        export_csv(result, args.csv)

    # Summary
    best = result["metrics_sorted"][0]
    best_score = result["results"][best]["alignment_score"]
    print(f"  Summary: Best metric = '{best}' (alignment={best_score:.4f})")


if __name__ == "__main__":
    main()

