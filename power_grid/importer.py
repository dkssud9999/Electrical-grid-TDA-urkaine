"""
Power grid data importer.

Supports multiple input formats:
  1. JSON / dict format (native)
  2. CSV files (buses.csv, lines.csv)
  3. Matpower .m case files (basic parsing)
  4. PyPSA (optional, if installed)

All formats return a standard dict:
    {
        "name": str,
        "buses": [
            {"id": int, "name": str, "x": float, "y": float, "v_nom": float}
        ],
        "lines": [
            {
                "id": int, "name": str,
                "from_bus": int, "to_bus": int,
                "x": float,         # reactance (p.u.)
                "r": float,         # resistance (p.u.)
                "rate": float       # thermal limit (MVA)
            }
        ],
        "generators": [
            {"bus": int, "p_mw": float, "name": str}
        ],
        "loads": [
            {"bus": int, "p_mw": float, "name": str}
        ],
        "base_mva": 100.0
    }
"""

from __future__ import annotations

import csv
import json
import math
import os
from typing import Any, Optional

import numpy as np


def _default_grid() -> dict:
    return {
        "name": "unnamed",
        "buses": [],
        "lines": [],
        "generators": [],
        "loads": [],
        "base_mva": 100.0,
    }


# ─── JSON / dict loader ───────────────────────────────────────


def load_json(path: str) -> dict:
    """Load a power grid from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return _validate_grid(data)


def load_dict(data: dict) -> dict:
    """Load a power grid from a Python dict."""
    return _validate_grid(data)


def _validate_grid(data: dict) -> dict:
    g = _default_grid()
    g["name"] = data.get("name", "unnamed")
    g["base_mva"] = float(data.get("base_mva", 100.0))

    for b in data.get("buses", []):
        g["buses"].append({
            "id": int(b["id"]),
            "name": str(b.get("name", f"B{b['id']}")),
            "x": float(b.get("x", 0.0)),
            "y": float(b.get("y", 0.0)),
            "v_nom": float(b.get("v_nom", 1.0)),
        })

    for l in data.get("lines", []):
        g["lines"].append({
            "id": int(l["id"]),
            "name": str(l.get("name", f"L{l['id']}")),
            "from_bus": int(l["from_bus"]),
            "to_bus": int(l["to_bus"]),
            "x": float(l.get("x", 0.1)),
            "r": float(l.get("r", 0.0)),
            "rate": float(l.get("rate", 9999.0)),
        })

    for gen in data.get("generators", []):
        g["generators"].append({
            "bus": int(gen["bus"]),
            "p_mw": float(gen.get("p_mw", 0.0)),
            "name": str(gen.get("name", "")),
        })

    for ld in data.get("loads", []):
        g["loads"].append({
            "bus": int(ld["bus"]),
            "p_mw": float(ld.get("p_mw", 0.0)),
            "name": str(ld.get("name", "")),
        })

    return g


# ─── CSV loader ───────────────────────────────────────────────


def load_csv(buses_path: str, lines_path: str,
             gens_path: Optional[str] = None,
             loads_path: Optional[str] = None) -> dict:
    """Load a power grid from CSV files."""
    g = _default_grid()

    with open(buses_path, newline="") as f:
        for row in csv.DictReader(f):
            g["buses"].append({
                "id": int(row["id"]),
                "name": row.get("name", f"B{row['id']}"),
                "x": float(row.get("x", 0.0)),
                "y": float(row.get("y", 0.0)),
                "v_nom": float(row.get("v_nom", 1.0)),
            })

    with open(lines_path, newline="") as f:
        for row in csv.DictReader(f):
            g["lines"].append({
                "id": int(row["id"]),
                "name": row.get("name", f"L{row['id']}"),
                "from_bus": int(row["from_bus"]),
                "to_bus": int(row["to_bus"]),
                "x": float(row.get("x", 0.1)),
                "r": float(row.get("r", 0.0)),
                "rate": float(row.get("rate", 9999.0)),
            })

    if gens_path:
        with open(gens_path, newline="") as f:
            for row in csv.DictReader(f):
                g["generators"].append({
                    "bus": int(row["bus"]),
                    "p_mw": float(row.get("p_mw", 0.0)),
                    "name": row.get("name", ""),
                })

    if loads_path:
        with open(loads_path, newline="") as f:
            for row in csv.DictReader(f):
                g["loads"].append({
                    "bus": int(row["bus"]),
                    "p_mw": float(row.get("p_mw", 0.0)),
                    "name": row.get("name", ""),
                })

    return g


# ─── Matpower .m parser (basic) ──────────────────────────────


def load_matpower(path: str) -> dict:
    """Parse a basic Matpower case file (.m).

    Supports only standard MPC format with:
      - bus data (columns 1-13)
      - branch data (columns 1-11)
      - gen data (columns 1-6)

    Returns None on parse error.
    """
    with open(path) as f:
        text = f.read()

    g = _default_grid()
    g["name"] = os.path.splitext(os.path.basename(path))[0]

    # Heuristic: find mpc.bus / mpc.branch / mpc.gen matrix definitions
    def _parse_matrix_block(txt: str, keyword: str) -> list[list[float]]:
        import re
        # Find "mpc.{keyword} = [" ... "];"
        pattern = rf"mpc\.{keyword}\s*=\s*\[(.*?)\];"
        m = re.search(pattern, txt, re.DOTALL)
        if not m:
            return []
        body = m.group(1)
        rows = []
        for line in body.strip().split("\n"):
            line = line.strip()
            # Skip comments
            if "%" in line:
                line = line.split("%")[0]
            if not line:
                continue
            nums = [float(x) for x in line.split() if x.strip()]
            if nums:
                rows.append(nums)
        return rows

    bus_data = _parse_matrix_block(text, "bus")
    branch_data = _parse_matrix_block(text, "branch")
    gen_data = _parse_matrix_block(text, "gen")

    # Matpower bus columns (1-indexed):
    # 1: bus_i, 2: type, 3: Pd, 4: Qd, 5: Gs, 6: Bs, 7: area,
    # 8: Vm, 9: Va, 10: baseKV, 11: zone, 12: Vmax, 13: Vmin

    if bus_data:
        for row in bus_data:
            bid = int(row[0])
            g["buses"].append({
                "id": bid,
                "name": f"B{bid}",
                "x": 0.0,  # layout positions—user can override
                "y": 0.0,
                "v_nom": float(row[9]) if len(row) > 9 else 1.0,
            })
            # Add load
            pd = float(row[2]) if len(row) > 2 else 0.0
            if pd > 0:
                g["loads"].append({
                    "bus": bid, "p_mw": pd, "name": f"Load_{bid}",
                })

    # Matpower branch columns:
    # 1: fbus, 2: tbus, 3: r, 4: x, 5: b, 6: rateA, 7: rateB,
    # 8: rateC, 9: ratio, 10: angle, 11: status

    if branch_data:
        for i, row in enumerate(branch_data):
            status = int(row[10]) if len(row) > 10 else 1
            if status != 1:
                continue
            x_pu = float(row[3]) if len(row) > 3 else 0.1
            r_pu = float(row[2]) if len(row) > 2 else 0.0
            rate = float(row[5]) if len(row) > 5 else 9999.0
            g["lines"].append({
                "id": int(row[0]) if i == 0 else i + 1,  # fallback
                "name": f"L{i + 1}",
                "from_bus": int(row[0]),
                "to_bus": int(row[1]),
                "x": max(x_pu, 1e-6),
                "r": r_pu,
                "rate": rate,
            })

    # Matpower gen columns:
    # 1: bus, 2: Pg, 3: Qg, 4: Qmax, 5: Qmin, 6: Vg, 7: mBase, ...

    if gen_data:
        for i, row in enumerate(gen_data):
            g["generators"].append({
                "bus": int(row[0]),
                "p_mw": float(row[1]) if len(row) > 1 else 0.0,
                "name": f"Gen_{int(row[0])}_{i}",
            })

    # Assign sequential IDs if missing
    if g["lines"] and g["lines"][0]["id"] == 1 and len(g["lines"]) > 1:
        # Check if IDs are sequential; if not reassign
        ids = [l["id"] for l in g["lines"]]
        if len(set(ids)) != len(ids):
            for i, l in enumerate(g["lines"]):
                l["id"] = i + 1

    return g


# ─── Optional PyPSA loader ───────────────────────────────────


def load_pypsa(path: str) -> dict:
    """Load a power grid using PyPSA (if installed).

    Falls back to a descriptive error if PyPSA is not available.
    """
    try:
        import pypsa
    except ImportError:
        raise ImportError(
            "PyPSA is not installed. Install with: pip install pypsa\n"
            "Alternatively, use JSON/CSV/Matpower format."
        )

    net = pypsa.Network(path)

    g = _default_grid()
    g["name"] = os.path.splitext(os.path.basename(path))[0]

    # Buses
    for bid, row in net.buses.iterrows():
        g["buses"].append({
            "id": int(bid) if isinstance(bid, (int, np.integer)) else len(g["buses"]),
            "name": str(row.get("name", f"B{bid}")),
            "x": float(row.get("x", 0.0)) if "x" in net.buses.columns else 0.0,
            "y": float(row.get("y", 0.0)) if "y" in net.buses.columns else 0.0,
            "v_nom": float(row.get("v_nom", 1.0)),
        })

    # Build bus index mapping (PyPSA often uses string indices)
    bus_ids = list(net.buses.index)
    bus_id_map = {name: i for i, name in enumerate(bus_ids)}

    # Lines
    for lid, row in net.lines.iterrows():
        g["lines"].append({
            "id": len(g["lines"]) + 1,
            "name": str(row.get("name", f"L{lid}")),
            "from_bus": bus_id_map.get(row["bus0"], int(row["bus0"]) if isinstance(row["bus0"], (int, np.integer)) else 0),
            "to_bus": bus_id_map.get(row["bus1"], int(row["bus1"]) if isinstance(row["bus1"], (int, np.integer)) else 0),
            "x": float(row.get("x", 0.1)),
            "r": float(row.get("r", 0.0)),
            "rate": float(row.get("s_nom", 9999.0)),
        })

    # Generators
    for _, row in net.generators.iterrows():
        g["generators"].append({
            "bus": bus_id_map.get(row["bus"], int(row["bus"]) if isinstance(row["bus"], (int, np.integer)) else 0),
            "p_mw": float(row.get("p_nom", 0.0)),
            "name": str(row.get("name", "")),
        })

    # Loads
    for _, row in net.loads.iterrows():
        g["loads"].append({
            "bus": bus_id_map.get(row["bus"], int(row["bus"]) if isinstance(row["bus"], (int, np.integer)) else 0),
            "p_mw": float(row.get("p_set", 0.0)),
            "name": str(row.get("name", "")),
        })

    return g


# ─── Auto-detect loader ──────────────────────────────────────


def load_grid(path: str) -> dict:
    """Auto-detect format and load the grid.

    Supports: .json, .csv (prefix), .m (Matpower), .nc/.h5 (PyPSA)
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        return load_json(path)
    elif ext == ".m":
        return load_matpower(path)
    elif ext in (".nc", ".h5", ".hdf5"):
        return load_pypsa(path)
    elif ext == ".csv":
        # For CSV, path should be a directory or base name
        base = os.path.splitext(path)[0]
        buses_csv = base + "_buses.csv"
        lines_csv = base + "_lines.csv"
        gens_csv = base + "_generators.csv"
        loads_csv = base + "_loads.csv"
        return load_csv(
            buses_csv if os.path.exists(buses_csv) else path,
            lines_csv if os.path.exists(lines_csv) else path,
            gens_csv if os.path.exists(gens_csv) else None,
            loads_csv if os.path.exists(loads_csv) else None,
        )
    else:
        raise ValueError(f"Unknown grid file format: {ext}")


# ─── Built-in test grids ─────────────────────────────────────


def get_test_grid_3bus() -> dict:
    """A simple 3-bus test system."""
    return {
        "name": "3-bus test",
        "buses": [
            {"id": 0, "name": "Slack", "x": 0, "y": 200, "v_nom": 1.0},
            {"id": 1, "name": "PV", "x": 150, "y": 0, "v_nom": 1.0},
            {"id": 2, "name": "PQ", "x": 300, "y": 200, "v_nom": 1.0},
        ],
        "lines": [
            {"id": 0, "name": "L0-1", "from_bus": 0, "to_bus": 1, "x": 0.1, "r": 0.01, "rate": 100},
            {"id": 1, "name": "L1-2", "from_bus": 1, "to_bus": 2, "x": 0.15, "r": 0.02, "rate": 100},
            {"id": 2, "name": "L0-2", "from_bus": 0, "to_bus": 2, "x": 0.2, "r": 0.03, "rate": 100},
        ],
        "generators": [
            {"bus": 0, "p_mw": 100, "name": "G_Slack"},
        ],
        "loads": [
            {"bus": 2, "p_mw": 100, "name": "Load"},
        ],
        "base_mva": 100.0,
    }


def get_test_grid_5bus() -> dict:
    """A 5-bus meshed test system (simple loop)."""
    return {
        "name": "5-bus loop",
        "buses": [
            {"id": 0, "name": "B0", "x": 0, "y": 0, "v_nom": 1.0},
            {"id": 1, "name": "B1", "x": 200, "y": 0, "v_nom": 1.0},
            {"id": 2, "name": "B2", "x": 400, "y": 0, "v_nom": 1.0},
            {"id": 3, "name": "B3", "x": 200, "y": 200, "v_nom": 1.0},
            {"id": 4, "name": "B4", "x": 400, "y": 200, "v_nom": 1.0},
        ],
        "lines": [
            {"id": 0, "name": "L0-1", "from_bus": 0, "to_bus": 1, "x": 0.1, "r": 0.01, "rate": 100},
            {"id": 1, "name": "L1-2", "from_bus": 1, "to_bus": 2, "x": 0.1, "r": 0.01, "rate": 100},
            {"id": 2, "name": "L0-3", "from_bus": 0, "to_bus": 3, "x": 0.15, "r": 0.02, "rate": 100},
            {"id": 3, "name": "L3-4", "from_bus": 3, "to_bus": 4, "x": 0.15, "r": 0.02, "rate": 100},
            {"id": 4, "name": "L1-3", "from_bus": 1, "to_bus": 3, "x": 0.12, "r": 0.015, "rate": 100},
            {"id": 5, "name": "L2-4", "from_bus": 2, "to_bus": 4, "x": 0.12, "r": 0.015, "rate": 100},
        ],
        "generators": [
            {"bus": 0, "p_mw": 200, "name": "G0"},
        ],
        "loads": [
            {"bus": 2, "p_mw": 100, "name": "Load_2"},
            {"bus": 4, "p_mw": 100, "name": "Load_4"},
        ],
        "base_mva": 100.0,
    }

