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


def get_ukraine_330kv_grid() -> dict:
    """
    Return a comprehensive 18-bus model of Ukraine's 330 kV backbone.

    This model captures the major transmission corridors, nuclear power
    plants, and load centers of Ukraine's high-voltage grid:

    **Regions & Buses:**
      - **North**: Pivnichna (0), Kyiv (1), Chornobyl (2)
      - **Northwest**: Rivne NPP (3), Khmelnytskyi NPP (4)
      - **West**: Burshtyn TES (5), Lviv (6)
      - **Southwest**: Dniester PSPP (7), Vinnytsia (8), Mohyliv-Podilskyi (9)
      - **South**: Pivdennoukrainska NPP (10), Odessa (11), Mykolaiv (12)
      - **Southeast**: Zaporizhzhia NPP (13), Zaporizhzhia (14)
      - **Center/East**: Kryvyi Rih (15), Dnipro (16), Kharkiv (17)

    **Topology:**
    ```
                 Chornobyl(2) -- Pivnichna(0) -- Rivne NPP(3) -- Lviv(6)
                       |              |               |             |
                      Kyiv(1)    KhNP(4) -- Burshtyn(5)            |
                       |           |                               |
                     Dnipro(16)  Vinnytsia(8)                     |
                       |        /    |    \\                        |
                   Poltava   Dniester(7) Mohyliv(9)              |
                       |         |                                |
                    Kharkiv(17)  |                                |
                              SUNPP(10) -------------------------+
                              /    |    \\
                         Odessa(11) Mykolaiv(12)
                                      |
                                   Kryvyi Rih(15)
                                      |
                                 ZNPP(13) -- Zaporizhzhia(14)
    ```

    Returns
    -------
    dict
        Standardized grid dict with 18 buses, 25 lines.
    """
    return {
        "name": "Ukraine 330 kV Backbone (18-bus)",
        "buses": [
            {"id": 0,  "name": "Pivnichna",              "x": 370, "y": 100, "v_nom": 330.0},
            {"id": 1,  "name": "Kyiv",                   "x": 370, "y": 160, "v_nom": 330.0},
            {"id": 2,  "name": "Chornobyl",              "x": 320, "y": 80,  "v_nom": 330.0},
            {"id": 3,  "name": "Rivne NPP",              "x": 200, "y": 140, "v_nom": 330.0},
            {"id": 4,  "name": "Khmelnytskyi NPP",       "x": 210, "y": 220, "v_nom": 330.0},
            {"id": 5,  "name": "Burshtyn TES",           "x": 120, "y": 270, "v_nom": 330.0},
            {"id": 6,  "name": "Lviv",                   "x": 100, "y": 180, "v_nom": 330.0},
            {"id": 7,  "name": "Dniester PSPP",          "x": 220, "y": 320, "v_nom": 330.0},
            {"id": 8,  "name": "Vinnytsia",              "x": 280, "y": 270, "v_nom": 330.0},
            {"id": 9,  "name": "Mohyliv-Podilskyi",      "x": 270, "y": 350, "v_nom": 330.0},
            {"id": 10, "name": "Pivdennoukrainska NPP",  "x": 370, "y": 400, "v_nom": 330.0},
            {"id": 11, "name": "Odessa",                 "x": 350, "y": 480, "v_nom": 330.0},
            {"id": 12, "name": "Mykolaiv",               "x": 420, "y": 430, "v_nom": 330.0},
            {"id": 13, "name": "Zaporizhzhia NPP",       "x": 510, "y": 330, "v_nom": 330.0},
            {"id": 14, "name": "Zaporizhzhia",           "x": 510, "y": 380, "v_nom": 330.0},
            {"id": 15, "name": "Kryvyi Rih",             "x": 440, "y": 300, "v_nom": 330.0},
            {"id": 16, "name": "Dnipro",                 "x": 530, "y": 250, "v_nom": 330.0},
            {"id": 17, "name": "Kharkiv",                "x": 640, "y": 190, "v_nom": 330.0},
        ],
        "lines": [
            # ── Northern ring ────────────────────────────────────
            {"id": 0,  "name": "Pivnichna-Kyiv",            "from_bus": 0,  "to_bus": 1,  "x": 0.025, "r": 0.0025, "rate": 800},
            {"id": 1,  "name": "Pivnichna-Chornobyl",       "from_bus": 0,  "to_bus": 2,  "x": 0.030, "r": 0.0030, "rate": 600},
            {"id": 2,  "name": "Chornobyl-Kyiv",            "from_bus": 2,  "to_bus": 1,  "x": 0.040, "r": 0.0040, "rate": 600},

            # ── Northwest corridor ──────────────────────────────
            {"id": 3,  "name": "Pivnichna-Rivne NPP",       "from_bus": 0,  "to_bus": 3,  "x": 0.110, "r": 0.011, "rate": 600},
            {"id": 4,  "name": "Rivne NPP-Khmelnytskyi NPP","from_bus": 3,  "to_bus": 4,  "x": 0.030, "r": 0.003, "rate": 800},
            {"id": 5,  "name": "Rivne NPP-Lviv",            "from_bus": 3,  "to_bus": 6,  "x": 0.060, "r": 0.006, "rate": 500},

            # ── Western region ──────────────────────────────────
            {"id": 6,  "name": "Lviv-Burshtyn TES",         "from_bus": 6,  "to_bus": 5,  "x": 0.060, "r": 0.006, "rate": 500},
            {"id": 7,  "name": "Burshtyn TES-Khmelnytskyi","from_bus": 5,  "to_bus": 4,  "x": 0.080, "r": 0.008, "rate": 500},

            # ── Southwest ───────────────────────────────────────
            {"id": 8,  "name": "Khmelnytskyi NPP-Vinnytsia","from_bus": 4,  "to_bus": 8,  "x": 0.050, "r": 0.005, "rate": 600},
            {"id": 9,  "name": "Vinnytsia-Dniester PSPP",   "from_bus": 8,  "to_bus": 7,  "x": 0.060, "r": 0.006, "rate": 500},
            {"id": 10, "name": "Vinnytsia-Mohyliv",         "from_bus": 8,  "to_bus": 9,  "x": 0.030, "r": 0.003, "rate": 400},
            {"id": 11, "name": "Dniester PSPP-Mohyliv",     "from_bus": 7,  "to_bus": 9,  "x": 0.015, "r": 0.0015,"rate": 400},

            # ── Central spine ───────────────────────────────────
            {"id": 12, "name": "Kyiv-Vinnytsia",            "from_bus": 1,  "to_bus": 8,  "x": 0.060, "r": 0.006, "rate": 600},
            {"id": 13, "name": "Kyiv-Dnipro",               "from_bus": 1,  "to_bus": 16, "x": 0.140, "r": 0.014, "rate": 600},

            # ── South ───────────────────────────────────────────
            {"id": 14, "name": "Vinnytsia-SUNPP",           "from_bus": 8,  "to_bus": 10, "x": 0.060, "r": 0.006, "rate": 500},
            {"id": 15, "name": "SUNPP-Odessa",              "from_bus": 10, "to_bus": 11, "x": 0.060, "r": 0.006, "rate": 500},
            {"id": 16, "name": "SUNPP-Mykolaiv",            "from_bus": 10, "to_bus": 12, "x": 0.030, "r": 0.003, "rate": 500},
            {"id": 17, "name": "Mykolaiv-Odessa",           "from_bus": 12, "to_bus": 11, "x": 0.040, "r": 0.004, "rate": 400},
            {"id": 18, "name": "Mykolaiv-Zaporizhzhia",     "from_bus": 12, "to_bus": 14, "x": 0.080, "r": 0.008, "rate": 500},

            # ── East / Dnipro region ────────────────────────────
            {"id": 19, "name": "ZNPP-Zaporizhzhia",         "from_bus": 13, "to_bus": 14, "x": 0.015, "r": 0.0015,"rate": 800},
            {"id": 20, "name": "ZNPP-Kryvyi Rih",           "from_bus": 13, "to_bus": 15, "x": 0.050, "r": 0.005, "rate": 600},
            {"id": 21, "name": "Zaporizhzhia-Dnipro",       "from_bus": 14, "to_bus": 16, "x": 0.025, "r": 0.0025,"rate": 600},
            {"id": 22, "name": "Kryvyi Rih-Dnipro",         "from_bus": 15, "to_bus": 16, "x": 0.050, "r": 0.005, "rate": 500},
            {"id": 23, "name": "Kryvyi Rih-SUNPP",          "from_bus": 15, "to_bus": 10, "x": 0.080, "r": 0.008, "rate": 500},
            {"id": 24, "name": "Dnipro-Kharkiv",            "from_bus": 16, "to_bus": 17, "x": 0.090, "r": 0.009, "rate": 600},
        ],
        "generators": [
            {"bus": 3,  "p_mw": 2000, "name": "Rivne NPP"},
            {"bus": 4,  "p_mw": 2000, "name": "Khmelnytskyi NPP"},
            {"bus": 5,  "p_mw": 2300, "name": "Burshtyn TES"},
            {"bus": 7,  "p_mw": 1200, "name": "Dniester PSPP"},
            {"bus": 10, "p_mw": 3000, "name": "Pivdennoukrainska NPP"},
            {"bus": 13, "p_mw": 6000, "name": "Zaporizhzhia NPP"},
            {"bus": 15, "p_mw": 3000, "name": "Kryvyi Rih TPP"},
            {"bus": 16, "p_mw": 500,  "name": "Dnipro HPP"},
        ],
        "loads": [
            {"bus": 1,  "p_mw": 2000, "name": "Kyiv Load"},
            {"bus": 6,  "p_mw": 500,  "name": "Lviv Load"},
            {"bus": 11, "p_mw": 800,  "name": "Odessa Load"},
            {"bus": 12, "p_mw": 400,  "name": "Mykolaiv Load"},
            {"bus": 14, "p_mw": 800,  "name": "Zaporizhzhia Load"},
            {"bus": 15, "p_mw": 2000, "name": "Kryvyi Rih Industrial"},
            {"bus": 16, "p_mw": 1000, "name": "Dnipro Load"},
            {"bus": 17, "p_mw": 1500, "name": "Kharkiv Load"},
        ],
        "base_mva": 100.0,
    }


def get_large_ukraine_grid() -> dict:
    """
    Return a larger 28-bus Ukraine grid model with additional 220 kV
    substations and regional detail.

    Extends the 18-bus 330 kV backbone with:
      - **West**: Ternopil, Ivano-Frankivsk, Uzhhorod
      - **Center**: Cherkasy, Kropyvnytskyi, Poltava
      - **East**: Sumy, Donbas (Pokrovsk)
      - **South**: Kherson, Izmail

    Returns
    -------
    dict
        Standardized grid dict with 28 buses, 36 lines.
    """
    g = get_ukraine_330kv_grid()

    # Extend with additional buses
    extra_buses = [
        {"id": 18, "name": "Ternopil",          "x": 180, "y": 190, "v_nom": 220.0},
        {"id": 19, "name": "Ivano-Frankivsk",   "x": 140, "y": 240, "v_nom": 220.0},
        {"id": 20, "name": "Uzhhorod",          "x": 60,  "y": 150, "v_nom": 220.0},
        {"id": 21, "name": "Cherkasy",          "x": 420, "y": 200, "v_nom": 220.0},
        {"id": 22, "name": "Kropyvnytskyi",     "x": 400, "y": 320, "v_nom": 220.0},
        {"id": 23, "name": "Poltava",           "x": 520, "y": 200, "v_nom": 220.0},
        {"id": 24, "name": "Sumy",              "x": 600, "y": 130, "v_nom": 220.0},
        {"id": 25, "name": "Pokrovsk",          "x": 680, "y": 250, "v_nom": 220.0},
        {"id": 26, "name": "Kherson",           "x": 420, "y": 480, "v_nom": 220.0},
        {"id": 27, "name": "Izmail",            "x": 310, "y": 530, "v_nom": 220.0},
    ]
    g["buses"].extend(extra_buses)

    extra_lines = [
        # West connections
        {"id": 25, "name": "Ternopil-Khmelnytskyi", "from_bus": 18, "to_bus": 4,  "x": 0.035, "r": 0.0035, "rate": 300},
        {"id": 26, "name": "Ternopil-Lviv",         "from_bus": 18, "to_bus": 6,  "x": 0.040, "r": 0.004,  "rate": 300},
        {"id": 27, "name": "Ivano-Frankivsk-Burshtyn","from_bus": 19, "to_bus": 5, "x": 0.020, "r": 0.002,  "rate": 300},
        {"id": 28, "name": "Uzhhorod-Lviv",         "from_bus": 20, "to_bus": 6,  "x": 0.070, "r": 0.007,  "rate": 200},

        # Center connections
        {"id": 29, "name": "Cherkasy-Kyiv",         "from_bus": 21, "to_bus": 1,  "x": 0.040, "r": 0.004,  "rate": 300},
        {"id": 30, "name": "Cherkasy-Dnipro",       "from_bus": 21, "to_bus": 16, "x": 0.050, "r": 0.005,  "rate": 300},
        {"id": 31, "name": "Kropyvnytskyi-Vinnytsia","from_bus": 22, "to_bus": 8,  "x": 0.055, "r": 0.0055, "rate": 300},
        {"id": 32, "name": "Kropyvnytskyi-Kryvyi Rih","from_bus": 22, "to_bus": 15, "x": 0.040, "r": 0.004,  "rate": 300},
        {"id": 33, "name": "Poltava-Dnipro",        "from_bus": 23, "to_bus": 16, "x": 0.035, "r": 0.0035, "rate": 300},

        # East connections
        {"id": 34, "name": "Sumy-Kharkiv",          "from_bus": 24, "to_bus": 17, "x": 0.050, "r": 0.005,  "rate": 300},
        {"id": 35, "name": "Pokrovsk-Kharkiv",      "from_bus": 25, "to_bus": 17, "x": 0.070, "r": 0.007,  "rate": 300},

        # South connections
        {"id": 36, "name": "Kherson-Mykolaiv",      "from_bus": 26, "to_bus": 12, "x": 0.030, "r": 0.003,  "rate": 300},
        {"id": 37, "name": "Izmail-Odessa",         "from_bus": 27, "to_bus": 11, "x": 0.060, "r": 0.006,  "rate": 200},
    ]
    g["lines"].extend(extra_lines)

    extra_generators = [
        {"bus": 25, "p_mw": 1000, "name": "Donbas Thermal"},
        {"bus": 26, "p_mw": 200,  "name": "Kherson Thermal"},
    ]
    g["generators"].extend(extra_generators)

    extra_loads = [
        {"bus": 18, "p_mw": 200, "name": "Ternopil Load"},
        {"bus": 20, "p_mw": 150, "name": "Uzhhorod Load"},
        {"bus": 21, "p_mw": 300, "name": "Cherkasy Load"},
        {"bus": 22, "p_mw": 250, "name": "Kropyvnytskyi Load"},
        {"bus": 23, "p_mw": 300, "name": "Poltava Load"},
        {"bus": 24, "p_mw": 300, "name": "Sumy Load"},
        {"bus": 25, "p_mw": 500, "name": "Donbas Load"},
        {"bus": 26, "p_mw": 300, "name": "Kherson Load"},
    ]
    g["loads"].extend(extra_loads)

    g["name"] = "Ukraine 330/220 kV Grid (28-bus)"
    return g


def get_sample_ukraine_grid() -> dict:
    """
    Return a sample Ukraine grid segment for testing (Dnipro region).

    Deprecated: Use `get_ukraine_330kv_grid()` for a comprehensive model.
    """
    return get_ukraine_330kv_grid()

