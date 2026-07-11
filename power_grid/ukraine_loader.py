"""
Ukraine power grid data loader.

Loads Ukraine's high-voltage transmission network data from standard
power system formats (JSON, CSV, Matpower, PyPSA) and adapts to the
project's internal grid dict schema.

Expected data sources
---------------------
The loader is designed to work with Ukraine's power grid data from:

1. **ENTSO-E Transparency Platform** (https://transparency.entsoe.eu/)
   - Transmission system data, generation, and load time series
   - Can be exported as CSV or accessed via API

2. **GridKit / OpenStreetMap extraction**
   - Ukraine power grid extracted from OpenStreetMap
   - Typically in JSON format with bus/line topology

3. **PyPSA-Earth / PyPSA data**
   - Open-source energy system model with Ukraine network data
   - Format: .nc (NetCDF) or CSV

4. **Manual data files**
   - Custom JSON/CSV files following the standard grid dict schema

Usage
-----
    from power_grid.ukraine_loader import load_ukraine_grid

    grid_data = load_ukraine_grid("path/to/ukraine_grid.json")
    # Returns standard grid dict:
    # {
    #     "name": "Ukraine Power Grid",
    #     "buses": [...],
    #     "lines": [...],
    #     "generators": [...],
    #     "loads": [...],
    #     "base_mva": 100.0
    # }

Ukraine Grid Characteristics
----------------------------
- ~330 kV, 220 kV, 110 kV transmission network
- Interconnected with neighboring countries (Moldova, Romania, Poland,
  Slovakia, Hungary, Belarus, Russia)
- Synchronized with ENTSO-E continental Europe grid since March 2022
- Major power plants: nuclear (Zaporizhzhia, Rivne, Khmelnytskyi,
  South Ukraine), thermal (coal/gas), hydro (Dnipro cascade)
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import numpy as np

from .importer import (
    _default_grid,
    load_json,
    load_csv,
    load_matpower,
    load_pypsa,
    load_grid,
)


def load_ukraine_grid(path: str) -> dict:
    """Load Ukraine power grid data from a file.

    Auto-detects format by file extension:
        .json  → JSON format
        .csv   → CSV format (prefix_buses.csv, prefix_lines.csv, etc.)
        .m     → Matpower format
        .nc    → PyPSA format

    Parameters
    ----------
    path : str
        Path to the grid data file.

    Returns
    -------
    dict
        Standardized grid dictionary.
    """
    return load_grid(path)


def load_ukraine_json(path: str) -> dict:
    """Load Ukraine grid data from a JSON file.

    Expected JSON structure (custom format for Ukraine grid):
    {
        "name": "Ukraine Grid",
        "buses": [
            {
                "id": 0,
                "name": "Zaporizhzhia NPP",
                "x": 35.1,       # longitude
                "y": 47.5,        # latitude
                "v_nom": 330.0,   # nominal voltage (kV)
                "substation": "Zaporizhzhia",
                "region": "Zaporizhia"
            },
            ...
        ],
        "lines": [
            {
                "id": 0,
                "name": "Zaporizhzhia-Dniprovska",
                "from_bus": 0,
                "to_bus": 1,
                "x": 0.05,         # reactance (p.u.)
                "r": 0.005,        # resistance (p.u.)
                "rate": 500,       # thermal rating (MVA)
                "length_km": 120,  # line length (optional)
                "voltage": 330     # voltage level (kV)
            },
            ...
        ],
        "generators": [...],
        "loads": [...],
        "base_mva": 100.0
    }

    Parameters
    ----------
    path : str
        Path to JSON file.

    Returns
    -------
    dict
        Standardized grid dict.
    """
    return load_json(path)


def load_ukraine_csv(
    buses_path: str,
    lines_path: str,
    gens_path: Optional[str] = None,
    loads_path: Optional[str] = None,
) -> dict:
    """Load Ukraine grid data from CSV files.

    CSV column format:
        buses: id, name, x, y, v_nom, substation, region
        lines: id, name, from_bus, to_bus, x, r, rate, length_km, voltage

    Parameters
    ----------
    buses_path : str
    lines_path : str
    gens_path : str, optional
    loads_path : str, optional

    Returns
    -------
    dict
        Standardized grid dict.
    """
    return load_csv(buses_path, lines_path, gens_path, loads_path)


def load_ukraine_entsoe_csv(path: str) -> dict:
    """Load Ukraine grid data from ENTSO-E format CSV.

    ENTSO-E Transparency data has a specific CSV format with columns:
        - MapCode, Year, Month, Day, ...
        - Generation, Load, Cross-border flows, etc.

    This parser extracts grid topology from ENTSO-E format data.

    Note: This is a partial implementation. ENTSO-E data primarily
    contains time series, not topology. For full topology data,
    use JSON or PyPSA formats.

    Parameters
    ----------
    path : str
        Path to ENTSO-E CSV file.

    Returns
    -------
    dict
        Standardized grid dict (may be minimal).
    """
    import csv

    g = _default_grid()
    g["name"] = "Ukraine Grid (ENTSO-E)"

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # ENTSO-E format varies; this is a basic extraction
            # Actual implementation depends on specific ENTSO-E export format
            pass

    return g


def load_ukraine_detailed(
    buses_path: str,
    lines_path: str,
    substations_path: Optional[str] = None,
    generators_path: Optional[str] = None,
    loads_path: Optional[str] = None,
    voltage_levels: Optional[list[float]] = None,
) -> dict:
    """Load Ukraine grid data with detailed substation information.

    This loader supports the detailed structure of Ukraine's
    transmission network, including:
      - Multi-voltage level buses (330 kV, 220 kV, 110 kV)
      - Substation names and geographic regions
      - Generator types (nuclear, thermal, hydro, renewable)

    Parameters
    ----------
    buses_path : str
        CSV file with bus/substation data.
    lines_path : str
        CSV file with transmission line data.
    substations_path : str, optional
        Additional substation metadata.
    generators_path : str, optional
        Generator unit data.
    loads_path : str, optional
        Load data.
    voltage_levels : list of float, optional
        Filter by voltage levels (e.g., [330.0, 220.0]).

    Returns
    -------
    dict
        Standardized grid dict.
    """
    import csv

    g = _default_grid()
    g["name"] = "Ukraine Power Grid (Detailed)"

    # Load buses
    bus_id_map: dict[int, int] = {}  # original_id → sequential index
    with open(buses_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            v_nom = float(row.get("v_nom", 330.0))
            if voltage_levels and v_nom not in voltage_levels:
                continue

            bus_id = int(row["id"])
            sequential_id = len(g["buses"])
            bus_id_map[bus_id] = sequential_id

            g["buses"].append({
                "id": sequential_id,
                "name": row.get("name", f"B{bus_id}"),
                "x": float(row.get("x", 0.0)),
                "y": float(row.get("y", 0.0)),
                "v_nom": v_nom,
            })

    # Load lines
    with open(lines_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            from_id = int(row["from_bus"])
            to_id = int(row["to_bus"])

            # Skip if buses were filtered out
            if from_id not in bus_id_map or to_id not in bus_id_map:
                continue

            g["lines"].append({
                "id": len(g["lines"]),
                "name": row.get("name", f"L{len(g['lines'])}"),
                "from_bus": bus_id_map[from_id],
                "to_bus": bus_id_map[to_id],
                "x": float(row.get("x", 0.1)),
                "r": float(row.get("r", 0.0)),
                "rate": float(row.get("rate", 9999.0)),
            })

    # Load generators (optional)
    if generators_path and os.path.exists(generators_path):
        with open(generators_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                bus_id = int(row["bus"])
                if bus_id in bus_id_map:
                    g["generators"].append({
                        "bus": bus_id_map[bus_id],
                        "p_mw": float(row.get("p_mw", 0.0)),
                        "name": row.get("name", f"Gen_{bus_id}"),
                    })

    # Load loads (optional)
    if loads_path and os.path.exists(loads_path):
        with open(loads_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                bus_id = int(row["bus"])
                if bus_id in bus_id_map:
                    g["loads"].append({
                        "bus": bus_id_map[bus_id],
                        "p_mw": float(row.get("p_mw", 0.0)),
                        "name": row.get("name", f"Load_{bus_id}"),
                    })

    return g


def get_sample_ukraine_grid() -> dict:
    """Return a sample Ukraine grid segment for testing.

    This is a simplified 6-bus segment of Ukraine's 330 kV network
    around the Dnipro region, including Zaporizhzhia NPP.

    This is for testing purposes only. Real data should be loaded
    from external files.

    Returns
    -------
    dict
        Sample grid dict.
    """
    return {
        "name": "Ukraine Grid Sample (Dnipro Region)",
        "buses": [
            {"id": 0, "name": "Zaporizhzhia NPP", "x": 350, "y": 200, "v_nom": 330.0},
            {"id": 1, "name": "Dniprovska",       "x": 300, "y": 350, "v_nom": 330.0},
            {"id": 2, "name": "Dnipro",            "x": 450, "y": 250, "v_nom": 330.0},
            {"id": 3, "name": "Zaporizhzhia",      "x": 350, "y": 300, "v_nom": 330.0},
            {"id": 4, "name": "Kakhovka",          "x": 250, "y": 400, "v_nom": 330.0},
            {"id": 5, "name": "Melitopol",         "x": 150, "y": 350, "v_nom": 330.0},
        ],
        "lines": [
            {"id": 0, "name": "Z-NPP-Dniprovska",  "from_bus": 0, "to_bus": 1, "x": 0.04, "r": 0.004, "rate": 600},
            {"id": 1, "name": "Z-NPP-Dnipro",      "from_bus": 0, "to_bus": 2, "x": 0.05, "r": 0.005, "rate": 600},
            {"id": 2, "name": "Z-NPP-Zaporizhzhia", "from_bus": 0, "to_bus": 3, "x": 0.03, "r": 0.003, "rate": 600},
            {"id": 3, "name": "Dnipro-Dniprovska",  "from_bus": 2, "to_bus": 1, "x": 0.06, "r": 0.006, "rate": 400},
            {"id": 4, "name": "Dniprovska-Kakhovka", "from_bus": 1, "to_bus": 4, "x": 0.07, "r": 0.007, "rate": 400},
            {"id": 5, "name": "Dniprovska-Zaporizhzhia", "from_bus": 1, "to_bus": 3, "x": 0.05, "r": 0.005, "rate": 400},
            {"id": 6, "name": "Kakhovka-Melitopol", "from_bus": 4, "to_bus": 5, "x": 0.08, "r": 0.008, "rate": 300},
        ],
        "generators": [
            {"bus": 0, "p_mw": 6000, "name": "Zaporizhzhia NPP"},
            {"bus": 2, "p_mw": 500, "name": "Dnipro HPP"},
        ],
        "loads": [
            {"bus": 3, "p_mw": 400, "name": "Zaporizhzhia Load"},
            {"bus": 4, "p_mw": 300, "name": "Kakhovka Load"},
            {"bus": 5, "p_mw": 200, "name": "Melitopol Load"},
        ],
        "base_mva": 100.0,
    }

