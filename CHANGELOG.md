# Changelog

All notable changes to the EV Motor Simulator project are documented in this file.

## [1.0.0] — 2026-04-20

### Initial Release

**EV Motor Simulator v1.0** is the first stable release of our open-source desktop application for interactively simulating and tuning EV motor topologies with engineering-grade fidelity.

#### Features

- **Dual Motor Topology Support**
  - Radial Flux PMSM and Axial Flux PM (AFPM) simulation side-by-side
  - Real-time parameter tuning with debounced 50 ms recompute cycle

- **Interactive Parameter Panel**
  - Geometry, electrical, material, and limit field controls
  - Sliders and spinboxes for intuitive adjustment
  - Live updates without flicker

- **Live Analysis & Visualization**
  - Torque-speed and power-speed curves rendered with pyqtgraph
  - Full 50×50 operating-point efficiency map heatmap via matplotlib
  - Loss breakdown chart (copper, iron, mechanical, stray) at any operating point
  - Key numbers summary: peak torque, base speed, max speed, peak power, peak efficiency

- **Preset Management**
  - Load, save, and save-as JSON presets
  - Three validated reference presets ship in-app
  - Compare mode: overlay radial and axial topologies with distinct colors

- **Data Export**
  - CSV export of speed, torque, power, efficiency, and loss columns
  - Post-processing friendly format

- **Physics Engine**
  - dq-frame model with MTPA and field-weakening solvers
  - Three reference motor validation: Tesla Model 3 LR, YASA 750 R, generic 60 kW PMSM
  - Validated within ±15 % of published datasheet values
  - Test suite coverage ≥ 80% on physics module

#### Platform Support

- **Windows** — Single-file executable via PyInstaller
- **macOS** — Single-file executable via PyInstaller (universal binary compatible)
- **Linux** — Single-file executable via PyInstaller

#### Technical

- Built with PyQt6, pyqtgraph, and matplotlib
- Headless physics engine fully unit-tested
- Pydantic-backed parameter validation
- Runs completely offline
- Requires Python 3.11 or newer (pre-packaged binaries included)

#### Acceptance Criteria Met

✓ v1.0 tagged release on GitHub with MIT license  
✓ Single-file PyInstaller binaries for Windows, macOS, Linux  
✓ README with features documentation  
✓ Test suite passing; physics coverage ≥ 80%  
✓ Three reference presets validated within ±15% tolerances  

---

## Getting Started

### From PyPI
```bash
pip install ev-motor-sim
ev-motor-sim
```

### From Source
```bash
git clone https://github.com/your-org/ev-motor-sim.git
cd ev-motor-sim
pip install -e .
python -m ev_motor_sim.main
```

### From Pre-Built Binaries

Download the latest v1.0 binaries for your platform:
- **Windows**: `EVMotorSimulator.exe`
- **macOS**: `EVMotorSimulator.dmg` (or raw executable)
- **Linux**: `EVMotorSimulator`

---

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.

## Credits

Built with PyQt6, pyqtgraph, matplotlib, NumPy, SciPy, and Pydantic.
