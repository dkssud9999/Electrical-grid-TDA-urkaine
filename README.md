# Graph Editor — Topological Data Analysis & Power Grid Toolkit

An interactive **Tkinter-based graph editor** that combines manual graph creation with **power grid analysis** and **Topological Data Analysis (TDA)**. Draw graphs visually, import real power grid data, compute electrical distance metrics (PTDF, LODF, effective resistance), and analyze topological features via Vietoris-Rips complexes, persistence diagrams, and Betti curves.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green)
![NumPy](https://img.shields.io/badge/NumPy-%3E%3D1.24-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
  - [Module Overview](#module-overview)
  - [Key Classes](#key-classes)
  - [Module Interaction Flows](#module-interaction-flows)
  - [Design Patterns](#design-patterns)
- [API Reference](#api-reference)
  - [Core (`graph_editor.py`)](#core-graph_editorpy)
  - [Electrical Distance (`electrical_distance/`)](#electrical-distance-electrical_distance)
  - [Topological Data Analysis (`tda/`)](#topological-data-analysis-tda)
  - [Power Grid Import (`power_grid/`)](#power-grid-import-power_grid)
  - [Integration Layer (`integration/`)](#integration-layer-integration)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### 🎨 Graph Editor
- **Left-click** on empty space → Add a new node
- **Left-click** on a node → Select it (highlighted in red)
- **Left-click** on another node while one is selected → Create a directed edge
- **Left-click** on the same node again → Deselect it
- **Left-drag** on a node → Move the node
- **Right-click** on a node → Delete the node and its edges
- **Right-click** on an edge → Delete the edge
- **Delete key** → Delete selected/hovered node
- **Ctrl+Z** → Undo (remove last added node)

### ⚡ Power Grid Integration
- Import power grid data from **JSON**, **CSV**, **Matpower (.m)**, or **PyPSA (.nc/.h5)** files
- Built-in test grids: **3-bus** and **5-bus** systems
- Automatic conversion of grid buses/lines into editor nodes/edges
- Synthetic grid generation from manually drawn graphs

### 🔬 Topological Data Analysis
- **Vietoris-Rips Complex** growth visualization with animated slider
- **Persistence Diagram** (H₀ and H₁) plotted on canvas
- Real-time **Betti number** display (β₀, β₁)
- **Betti curves** across all distance thresholds
- **Euler characteristic** computation (χ = V - E)

### 📊 Electrical Distance Metrics
- **PTDF Vector Distance** (L1, L2 norms)
- **Effective Resistance Distance** (via Laplacian pseudoinverse)
- **Bus LODF Sensitivity Distance**
- **PTDF Inverse Distance** (normalized to [0,1])
- **LODF Inverse Distance** (pseudo-inverse of LODF matrix)
- **KCL Current Distance** (KCL-based electrical distance)
- **Hybrid Distance** (weighted combinations)
- **Geodesic-Electrical Hybrid Distance**
- Side-by-side metric comparison view

### 🔬 N-1 Contingency Analysis
- **AC Newton-Raphson Power Flow** solver (pure numpy, no external dependencies)
- **N-1 Contingency Analysis** — removes each line one at a time and checks:
  - **Line overload**: flow on any remaining line > rate (thermal limit)
  - **Voltage violation**: bus voltage outside [V_min, V_max]
  - **Islanding**: grid becomes disconnected (multiple components)
- **Homology Comparison** — compares N-1 vulnerable edges with persistent H1 cycle edges
  - Alignment score = |intersection| / total_edges
  - Precision, recall, specificity metrics
- **Multi-metric comparison** — evaluates alignment across all distance metrics simultaneously

### 🤖 AI Analysis
- Send graph diagram (as image) + topological data to **DeepSeek** via **OpenRouter**
- Receive AI interpretation of topological features and structure
- Korean language responses

### 📋 Project Management
- **[TODO.md](./TODO.md)** — Task tracking and progress overview
- **[history.md](./history.md)** — Project change history and milestones

### ✅ Testing
- **82 unit tests** covering:
  - AC power flow solver (3-bus, 5-bus convergence, power balance)
  - N-1 contingency analysis (3-bus, 5-bus, violation details)
  - Cycle edge extraction from VR persistence (triangle, tree, square)
  - Alignment score computation (perfect, partial, no overlap, empty)
  - Homology comparison integration (compare_with_homology, compare_metrics_vulnerability)
  - PTDF matrix computation (shape, slack bus, edge cases)
  - LODF matrix (shape, diagonal values, bridge line)
  - Effective resistance (symmetry, diagonal, single-line)
  - PTDF vector distance (symmetry, L1/L2 norms)
  - Bus LODF sensitivity (symmetry)
  - LODF Inverse distance (positive, shape, 5-bus)
  - KCL Current distance (compute, name, shape)
  - VR complex (initialization, persistence pairs, Betti numbers/curves, caching)
  - Metric classes (all 8 implementations, edge cases, invalid input)
- Run with: `PYTHONPATH=graph_editor python3 -m pytest graph_editor/tests/ -v`

---

## Installation

### Prerequisites
- Python 3.10+
- NumPy 1.24+
- Tkinter (usually included with Python)

### Clone & Setup

```bash
git clone <repository-url>
cd graph_editor
```

### Install Dependencies

**Core dependencies** (required for basic graph editing and VR computation):
```bash
# Using pip
pip install numpy

# Arch Linux (pacman)
sudo pacman -S python-numpy
```

**Optional dependencies** (for power grid import and AI analysis):
```bash
# Using pip
pip install pillow          # For canvas image capture (AI Analysis)
pip install scipy           # For certain matrix operations
pip install pypsa           # For PyPSA format import
pip install matplotlib      # For metric comparison charts

# Arch Linux (pacman)
sudo pacman -S python-pillow python-scipy python-matplotlib
```

**Testing dependencies:**
```bash
# Using pip
pip install pytest

# Arch Linux (pacman)
sudo pacman -S python-pytest
```

### Verify Installation

```bash
python3 -c "import ast; ast.parse(open('graph_editor/graph_editor.py').read()); print('✅ Ready')"
```

---

## Usage

### Launch the Application

```bash
python3 graph_editor/graph_editor.py
```

### Workflows

#### 1. Manual Graph → TDA Exploration
1. Launch the app and draw nodes/edges on the canvas
2. Click **📊 TDA 탐색기** to open the TDA Explorer
3. Use the slider to animate Vietoris-Rips complex growth
4. Observe persistence diagram, Betti numbers, and Betti curves
5. Click **🤖 AI 분석 (딥시크)** for AI interpretation (requires OpenRouter API key)

#### 2. Power Grid Import → Electrical Distance Analysis
1. Click **⚡ 전력망 임포트**
2. Select a built-in test grid (3-bus or 5-bus) or load from file
3. The grid buses and lines appear on the canvas
4. Click **🔬 TDA Distance** to open the Power Grid TDA Explorer
5. Select a distance metric from the dropdown (PTDF, Effective R, LODF, etc.)
6. Explore VR complex, persistence diagram, and compare all metrics

#### 3. Manual Graph → Synthetic Grid → PTDF Analysis
1. Draw a graph manually
2. Click **🔬 TDA Distance**
3. When prompted, click "No" to use the current graph as a fake grid
4. The graph is converted to a synthetic power grid with distance-based susceptances
5. Explore PTDF-based distance metrics

---

## Architecture

### Module Overview

```
graph_editor/
├── graph_editor.py              # Main application (GUI + core logic)
├── README.md                    # This file
├── electrical_distance/
│   ├── __init__.py              # Package: "Electrical distance metrics..."
│   ├── ptdf_calculator.py       # PTDF, LODF, effective resistance (pure numpy)
│   └── metrics.py               # OOP metric classes (ABC + implementations)
├── tda/
│   ├── __init__.py              # Package: "Topological Data Analysis..."
│   ├── vr_core.py               # Vietoris-Rips complex via union-find
│   └── vulnerability.py         # N-1 contingency + homology comparison engine
├── power_grid/
│   ├── __init__.py              # Package: \"Power grid import...\"
│   ├── importer.py              # Multi-format grid data parser
│   ├── ac_power_flow.py         # AC Newton-Raphson power flow solver
│   └── contingency.py           # N-1 contingency analysis for vulnerability
├── integration/
│   ├── __init__.py              # Package: "Integration layer..."
│   ├── grid_to_graph.py         # Grid data → GraphEditor converter
│   └── power_grid_tda.py        # Enhanced TDA explorer with electrical metrics
└── tests/
    └── __init__.py              # Test package
```

### Key Classes

| Class | Module | Responsibility |
|---|---|---|
| **`Node`** | `graph_editor.py` | Graph vertex with canvas rendering, hit testing, position updates |
| **`Edge`** | `graph_editor.py` | Directed edge with arrowhead rendering, color changes, deletion |
| **`GraphEditor`** | `graph_editor.py` | Main controller: UI, interaction, node/edge management, event handling |
| **`GridGraphConverter`** | `integration/grid_to_graph.py` | Converts power grid data dict → editor nodes/edges with electrical params |
| **`PowerGridTDAExplorer`** | `integration/power_grid_tda.py` | Full TDA explorer window for power grids with multiple distance metrics |
| **`VRComplex`** | `tda/vr_core.py` | Vietoris-Rips complex: persistence pairs, Betti numbers/curves |
| **`ElectricalDistance`** (ABC) | `electrical_distance/metrics.py` | Abstract base for all electrical distance metric implementations |
| **`PTDFVectorDistance`** | `electrical_distance/metrics.py` | Distance = \|\|PTDF_i - PTDF_j\|\|_p |
| **`EffectiveResistanceDistance`** | `electrical_distance/metrics.py` | True electrical distance via Laplacian pseudoinverse |
| **`BusLODFDistance`** | `electrical_distance/metrics.py` | Distance based on LODF sensitivity vectors |
| **`LODFInverseDistance`** | `electrical_distance/metrics.py` | Distance = pseudo-inverse of LODF matrix |
| **`KCLCurrentDistance`** | `electrical_distance/metrics.py` | KCL-based current distribution distance |
| **`ACPowerFlow`** | `power_grid/ac_power_flow.py` | Newton-Raphson AC power flow solver |
| **`N1ContingencyAnalyzer`** | `power_grid/contingency.py` | N-1 contingency analysis for grid vulnerability |

### Module Interaction Flows

#### Manual Graph → TDA Explorer
```
User draws nodes/edges in GraphEditor
    → _tda_explorer() computes distance matrix from node positions
    → Computes H₀/H₁ persistence via union-find
    → Draws VR growth, persistence diagram, Betti curves on Tkinter canvases
    → User can animate VR growth with alpha slider
    → AI Analysis: captures canvas as PostScript → PNG → sends to DeepSeek via OpenRouter
```

#### Power Grid Import → TDA Analysis
```
User clicks "⚡ 전력망 임포트"
    → Import dialog: built-in test grid (3-bus/5-bus) or file (JSON/CSV/Matpower/PyPSA)
    → load_grid() / get_test_grid_*() returns standardized dict
    → GraphEditor._load_grid_data() creates GridGraphConverter
    → GridGraphConverter.add_to_editor() creates Nodes + Edges in GraphEditor
    → User clicks "🔬 TDA Distance"
    → PowerGridTDAExplorer opens with electrical parameters
    → User selects metric (PTDF, Effective R, LODF, etc.)
    → Metric function computes distance matrix via ptdf_calculator.py
    → VRComplex computes persistence from distance matrix
    → Displays VR view, persistence diagram, Betti curves
```

#### Fake Grid from Manual Graph
```
User draws a graph manually
    → GraphEditor._build_fake_grid_from_graph()
    → Converts nodes → buses, edges → lines with distance-based susceptance
    → Creates GridGraphConverter with synthetic grid data
    → Opens PowerGridTDAExplorer for PTDF/LODF analysis
```

### Design Patterns

1. **MVC-like Architecture** — `GraphEditor` acts as the controller, `Node`/`Edge` as models with embedded view logic, Tkinter Canvas as the view.

2. **Strategy Pattern** — `ElectricalDistance` ABC in `metrics.py` defines the interface; `PTDFVectorDistance`, `EffectiveResistanceDistance`, `BusLODFDistance`, etc. provide concrete implementations selectable at runtime.

3. **Adapter Pattern** — `power_grid/importer.py` converts multiple input formats (JSON, CSV, Matpower, PyPSA) to a uniform Python dict schema.

4. **Bridge Pattern** — `integration/` layer bridges power grid data structures ↔ graph editor's node/edge representation ↔ TDA analysis.

5. **Lazy Computation** — `VRComplex` caches persistence pairs and Betti curves after first computation.

6. **Pure NumPy** — All numerical computation avoids scipy for core functionality, using only `numpy.linalg.inv`, `numpy.linalg.pinv`, and `numpy.linalg.cond`.

---

## API Reference

### Core (`graph_editor.py`)

#### `Node(canvas, x, y, label=None)`
| Method | Description |
|---|---|
| `update_position(x, y)` | Move node and redraw connected edges |
| `set_color(color)` | Change fill color |
| `contains_point(x, y)` | Hit test (radius-based) |
| `delete()` | Remove canvas items |

#### `Edge(canvas, source, target, label=None)`
| Method | Description |
|---|---|
| `redraw()` | Re-render after node movement |
| `set_color(color)` | Change edge and arrowhead color |
| `delete()` | Remove canvas items and unregister from nodes |

#### `GraphEditor(root)`
| Method | Description |
|---|---|
| `add_node(x, y, label)` | Create and return a new node |
| `add_edge(source, target, label)` | Create a directed edge (no duplicates) |
| `remove_node(node)` | Delete node and all connected edges |
| `remove_edge(edge)` | Delete specific edge |
| `get_node_at(x, y)` | Find top-most node at coordinates |
| `get_edge_near(x, y, threshold=10)` | Find edge near coordinates |

### Electrical Distance (`electrical_distance/`)

#### `ptdf_calculator.py`
| Function | Returns | Description |
|---|---|---|
| `compute_ptdf(n_bus, bus_pairs, susceptances, slack_bus=0)` | `ndarray (n_line × n_bus)` | PTDF matrix — impact of injection shifts on line flows |
| `compute_lodf(PTDF, bus_pairs)` | `ndarray (n_line × n_line)` | LODF matrix — impact of line outages on other lines |
| `compute_effective_resistance_matrix(n_bus, bus_pairs, susceptances)` | `ndarray (n_bus × n_bus)` | R_eff(i,j) = (e_i-e_j)ᵀ·L⁺·(e_i-e_j) |
| `compute_ptdf_vector_distance(PTDF, p_norm=2.0)` | `ndarray (n_bus × n_bus)` | Bus distance = \|\|PTDF[:,i] - PTDF[:,j]\|\|_p |
| `compute_bus_lodf_sensitivity(PTDF, LODF, bus_pairs)` | `ndarray (n_bus × n_bus)` | Distance based on LODF sensitivity |

#### `metrics.py` — Metric Classes

| Class | `compute()` Returns | Description |
|---|---|---|
| `PTDFVectorDistance(norm_order=2, slack_bus=0)` | Symmetric distance matrix | \|\|PTDF_i - PTDF_j\|\|_p |
| `EffectiveResistanceDistance()` | Symmetric distance matrix | (e_i-e_j)ᵀ·L⁺·(e_i-e_j) |
| `BusLODFDistance()` | Symmetric distance matrix | \|\|LODF_sens_i - LODF_sens_j\|\|₂ |
| `PTDFInverseDistance(transform="inverse")` | Normalized [0,1] matrix | 1/(1 + d), exp(-d²/σ²), or logistic(d) |
| `LODFInverseDistance()` | Symmetric distance matrix | Pseudo-inverse of LODF matrix |
| `KCLCurrentDistance()` | Symmetric distance matrix | KCL-based current distribution distance |
| `HybridDistance(metrics, weights)` | Weighted combination | Σ w_k · normalize(d_k) |
| `GeodesicElectricalHybrid(alpha=1.0, beta=1.0)` | Combined matrix | α·geo + β·elec |

### Topological Data Analysis (`tda/`)

#### `VRComplex(distance_matrix)`
| Method | Returns | Description |
|---|---|---|
| `persistence_pairs()` | `(h0_pairs, h1_pairs)` | H₀ and H₁ persistence pairs (birth, death) |
| `betti_numbers(alpha)` | `(beta0, beta1)` | Betti numbers at threshold α |
| `betti_curves()` | `(thresholds, b0_vals, b1_vals)` | Betti curves across all thresholds |

#### `vulnerability.py` — Vulnerability Detection Engine

| Function | Returns | Description |
|---|---|---|
| `analyze_n1_vulnerability(grid_data, **kwargs)` | Dict | Run N-1 contingency analysis on grid |
| `get_cycle_edges(distance_matrix, bus_pairs)` | Set of tuples | Extract edges in persistent H1 cycles |
| `get_cycle_edge_ids(distance_matrix, bus_pairs, line_id_map)` | Set of ints | Get line IDs of H1 cycle edges |
| `compare_with_homology(grid_data, distance_matrix, **kwargs)` | Dict | Compare N-1 vulnerability with homology detection |
| `compare_metrics_vulnerability(grid_data, distance_matrices, **kwargs)` | Dict | Compare homology alignment across multiple metrics |

### Power Grid Import & Analysis (`power_grid/`)

#### `importer.py`
| Function | Returns | Description |
|---|---|---|
| `load_json(path)` | Grid dict | Load from JSON file |
| `load_csv(buses_path, lines_path, gens_path, loads_path)` | Grid dict | Load from CSV files |
| `load_matpower(path)` | Grid dict | Parse Matpower .m case file |
| `load_pypsa(path)` | Grid dict | Load via PyPSA library |
| `load_grid(path)` | Grid dict | Auto-detect format by extension |
| `get_test_grid_3bus()` | Grid dict | 3-bus test system (Slack-PV-PQ) |
| `get_test_grid_5bus()` | Grid dict | 5-bus meshed loop system |

#### `ac_power_flow.py`
| Class/Method | Returns | Description |
|---|---|---|
| `ACPowerFlow(n_bus, bus_pairs, r_list, x_list, base_mva=100.0)` | — | Newton-Raphson AC power flow solver (pure numpy) |
| `.run_power_flow(p_inj, q_inj, slack_bus, pv_buses, ...)` | Dict | Solve AC power flow, returns V, theta, branch_flows, converged status |

#### `contingency.py`
| Class/Function | Returns | Description |
|---|---|---|
| `N1ContingencyAnalyzer(grid_data, v_min, v_max, overload_threshold)` | — | N-1 contingency analysis for grid vulnerability |
| `.analyze()` | Dict | Run N-1 on all lines: vulnerable_edges, violation_details, vulnerability_ratio |
| `analyze_grid_vulnerability(grid_data, **kwargs)` | Dict | Convenience one-shot vulnerability analysis |
| `get_cycle_edges_from_vr(distance_matrix, bus_pairs)` | Set of tuples | Extract edges in persistent H1 cycles from VR homology |
| `compute_alignment_score(vulnerable_edges, cycle_edge_ids, total_edges)` | Dict | Compute TP/FP/FN/TN, alignment score, precision, recall, specificity |

**Standard Grid Dict Schema:**
```python
{
    "name": str,
    "buses": [{"id": int, "name": str, "x": float, "y": float, "v_nom": float}],
    "lines": [{"id": int, "name": str, "from_bus": int, "to_bus": int,
               "x": float, "r": float, "rate": float}],
    "generators": [{"bus": int, "p_mw": float, "name": str}],
    "loads": [{"bus": int, "p_mw": float, "name": str}],
    "base_mva": 100.0
}
```

### Integration Layer (`integration/`)

#### `grid_to_graph.GridGraphConverter(grid_data)`
| Method | Returns | Description |
|---|---|---|
| `add_to_editor(editor, use_geo_layout=False)` | None | Convert grid → editor nodes/edges |
| `compute_layout(scale_x=1.0, scale_y=1.0, margin=50)` | `(scaled_x, scaled_y)` | Auto-layout with circular per-component placement |
| `get_electrical_data()` | Dict | `{n_bus, n_line, bus_pairs, susceptances, bus_positions, bus_labels}` |

#### `power_grid_tda.PowerGridTDAExplorer(parent, data)`
| Method | Description |
|---|---|
| `open()` | Display the TDA explorer window with VR view, persistence diagram, Betti curves, metric selector, and animation |

**Available Metrics (via `METRICS` dict):**
- `"PTDF Vector (L2)"` — Default
- `"PTDF Vector (L1)"`
- `"Effective Resistance"`
- `"Bus LODF Sensitivity"`
- `"PTDF Inverse"`
- `\"LODF Inverse Distance\"`
- `\"KCL Current Distance\"`
- `"Geographic (Euclidean)"`

---

## Testing

The project has **82 unit tests** covering all modules. To run:

```bash
PYTHONPATH=graph_editor python3 -m pytest graph_editor/tests/ -v
```

### Test Modules
- `tests/test_vr_core.py` — Vietoris-Rips complex, persistence pairs, Betti numbers, caching
- `tests/test_ptdf_calculator.py` — PTDF, LODF, effective resistance, edge cases
- `tests/test_metrics.py` — All 8 distance metric classes
- `tests/test_contingency.py` — AC power flow, N-1 analysis, cycle extraction, alignment scores

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run linting and type checking
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Coding Standards
- Follow PEP 8
- Use type hints for function signatures
- Write docstrings for all public methods
- Keep numerical code pure numpy where possible
- Use Tkinter for all GUI elements (no external GUI dependencies)

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Acknowledgments

- Built with [NumPy](https://numpy.org/) for numerical computation
- GUI powered by Python's standard [Tkinter](https://docs.python.org/3/library/tkinter.html) library
- AI analysis via [OpenRouter](https://openrouter.ai/) and [DeepSeek](https://deepseek.com/)
- Power grid concepts based on DC power flow and PTDF theory

