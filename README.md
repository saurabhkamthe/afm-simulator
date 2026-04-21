# EV Motor Simulator

An open-source desktop application for interactively simulating and tuning EV motor topologies with engineering-grade fidelity. Runs fully offline on Windows, macOS, and Linux.

![Demo GIF](docs/assets/demo.gif)
<!-- TODO: Replace with actual 60-second demo GIF once UI is complete (T-602) -->

---

## Features

- **Two motor topologies** — Radial Flux PMSM and Axial Flux PM (AFPM) simulation side-by-side
- **Interactive parameter panel** — sliders and spinboxes for geometry, electrical, material, and limit fields, debounced at 50 ms for smooth real-time recompute
- **Live torque-speed and power-speed plots** — rendered with pyqtgraph, updates without flicker on every parameter change
- **Efficiency map** — full 50×50 operating-point heatmap computed on demand via matplotlib
- **Loss breakdown chart** — copper, iron, mechanical, and stray losses at any operating point selected by cursor
- **Key numbers summary** — instant readout of peak torque, base speed, max speed, peak power, and peak efficiency
- **Compare mode** — overlay radial and axial curves with distinct colours and a legend
- **Preset management** — load, save, and save-as JSON presets; three reference presets ship in-app
- **CSV export** — export speed, torque, power, efficiency, and loss columns for post-processing
- **Validated physics** — dq-frame model with MTPA, field-weakening, and MTPV solvers; all three reference motors validated within ±15 % of published datasheet values

---

## Installation

### Prerequisites

- Python 3.11 or newer
- pip

### From PyPI (recommended once v1.0 is released)

```bash
pip install ev-motor-sim
ev-motor-sim
```

### From source

```bash
git clone https://github.com/your-org/ev-motor-sim.git
cd ev-motor-sim
pip install -e .
python -m ev_motor_sim.main
```

### Install all dependencies manually

```bash
pip install "pyqt6==6.7.*" pyqtgraph matplotlib numpy scipy "pydantic>=2" pytest pyinstaller
```

### Pre-built binaries

Single-file binaries for Windows, macOS, and Linux are attached to every [GitHub Release](../../releases). Download, make executable (macOS/Linux), and run — no Python installation required.

| Platform | File |
|---|---|
| Windows | `ev-motor-sim-windows.exe` |
| macOS | `ev-motor-sim-macos` |
| Linux | `ev-motor-sim-linux` |

```bash
# macOS / Linux
chmod +x ev-motor-sim-linux
./ev-motor-sim-linux
```

---

## Screenshots

### Main Window — Radial PMSM (Tesla Model 3 LR preset)

![Main window showing radial PMSM torque-speed and power-speed curves](docs/assets/screenshot-main-radial.png)
<!-- TODO: Replace with actual screenshot (T-602) -->

### Efficiency Map — YASA 750 R (Axial Flux preset)

![Efficiency heatmap for YASA 750 R axial flux motor](docs/assets/screenshot-eff-map.png)
<!-- TODO: Replace with actual screenshot (T-602) -->

### Compare Mode — Radial vs Axial Overlay

![Side-by-side comparison of radial and axial motor curves](docs/assets/screenshot-compare.png)
<!-- TODO: Replace with actual screenshot (T-602) -->

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  File   View   Presets   Help                                    │
├──────────────────┬───────────────────────────────────────────────┤
│  [Topology]      │     Torque vs. Speed          Power vs. Speed │
│  ○ Radial PMSM   │    ┌──────────────────┐    ┌────────────────┐ │
│  ● Axial Flux    │    │   (pyqtgraph)    │    │  (pyqtgraph)   │ │
│  ○ Compare       │    └──────────────────┘    └────────────────┘ │
│  ── Geometry ──  │     Efficiency Map             Loss Breakdown │
│  ── Electrical ─ │    ┌──────────────────┐    ┌────────────────┐ │
│  ── Material ──  │    │   (matplotlib    │    │ Copper ████    │ │
│  ── Limits ────  │    │    heatmap)      │    │ Iron   ██      │ │
│                  │    └──────────────────┘    └────────────────┘ │
│  [Load Preset]   │   Peak T / Base ω / Max ω / Peak P / Peak η   │
│  [Save Preset]   │   [Compute Eff Map]   [Export CSV]            │
└──────────────────┴────────────────────────────────────────────────┘
```

---

## Reference Presets

Three validated presets ship in-app under `Presets → Load`:

| Preset | File |
|---|---|
| Tesla Model 3 LR (Rear, IPMSM) | `tesla_model3.json` |
| YASA 750 R (Axial Flux PM) | `yasa_750r.json` |
| Generic 60 kW PMSM | `generic_60kw.json` |

---

## Validation

All three reference presets are validated within **±15 %** of published datasheet values. Results from the automated test suite (`pytest tests/test_reference_presets.py`):

| Preset | Metric | Reference | Simulated | Error |
|---|---|---|---|---|
| Tesla Model 3 LR | Peak torque | ~420 Nm | ✓ | ≤ ±15 % |
| Tesla Model 3 LR | Base speed | ~6 000 rpm | ✓ | ≤ ±15 % |
| Tesla Model 3 LR | Peak power | ~211 kW | ✓ | ≤ ±15 % |
| Tesla Model 3 LR | Peak η | ~97 % | ✓ | ≤ ±15 % |
| YASA 750 R | Peak torque | ~790 Nm | ✓ | ≤ ±15 % |
| YASA 750 R | Base speed | ~3 250 rpm | ✓ | ≤ ±15 % |
| YASA 750 R | Peak power | ~200 kW | ✓ | ≤ ±15 % |
| YASA 750 R | Peak η | ~95 % | ✓ | ≤ ±15 % |
| Generic 60 kW PMSM | Peak torque | ~150 Nm | ✓ | ≤ ±15 % |
| Generic 60 kW PMSM | Base speed | ~4 000 rpm | ✓ | ≤ ±15 % |
| Generic 60 kW PMSM | Peak power | ~60 kW | ✓ | ≤ ±15 % |
| Generic 60 kW PMSM | Peak η | ~94 % | ✓ | ≤ ±15 % |

Run the validation suite yourself:

```bash
pytest tests/test_reference_presets.py -v
```

---

## Physics Model

The simulator uses a **dq-frame model** (SI units throughout):

- **Torque:** `T_em = (3/2) · p · [λ_pm · i_q + (L_d − L_q) · i_d · i_q]`
- **Operating regions:** MTPA (below base speed), field-weakening (Region 2), and MTPV for high-saliency IPMSMs
- **Losses:** copper (with temperature-dependent resistance), Steinmetz iron, mechanical friction + windage, stray (1 % of input)
- **Axial-flux sizing:** uses `T_em ≈ (π²/4) · k_w · B_g · A_s · D_avg² · L_a`

Full equation reference: see `BRIEF.md` Appendix A.

---

## Project Structure

```
ev_motor_sim/
├── pyproject.toml
├── README.md
├── src/ev_motor_sim/
│   ├── main.py
│   ├── models/        (base.py, pmsm.py, afpm.py)
│   ├── physics/       (dq_frame.py, losses.py, control.py)
│   ├── ui/            (main_window.py, param_panel.py, plots.py, efficiency_map.py)
│   └── presets/       (tesla_model3.json, yasa_750r.json, generic_60kw.json)
└── tests/
    ├── test_pmsm_physics.py
    ├── test_afpm_physics.py
    └── test_reference_presets.py
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| GUI | PyQt6 6.7.x |
| Real-time plots | pyqtgraph |
| Heatmap | matplotlib (via `FigureCanvasQTAgg`) |
| Numerics | NumPy, SciPy |
| Config / schemas | pydantic v2 |
| Tests | pytest |
| Packaging | PyInstaller |
| CI | GitHub Actions |

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/your-org/ev-motor-sim.git
cd ev-motor-sim
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage report
pytest --cov=src/ev_motor_sim --cov-report=term-missing

# Build a local binary
pyinstaller --onefile --windowed src/ev_motor_sim/main.py -n ev-motor-sim
```

CI runs automatically on every PR via GitHub Actions across Windows, macOS, and Linux.

---

## Contributing

1. Fork the repository and create a branch named after the ticket (e.g. `T-301`).
2. Make your changes; all physics formulas must cite Appendix A in code comments.
3. Open a PR — title must start with the ticket ID.
4. A CTO review is required before merge; no agent merges its own PR.

No new dependencies without a ticket and CTO sign-off.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Out of Scope

FEA, thermal coupling beyond simple temperature-dependent resistance, mobile app, cloud sync, and paid features are intentionally out of scope for v1.0.
