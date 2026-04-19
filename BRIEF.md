# EV Motor Simulator — Paperclip Company Brief

> **For Paperclip orchestration.** This document defines a company mission, suggested org chart, project/task breakdown, governance gates, and a technical reference appendix. Import as a company template; assign agents per the org chart; let heartbeats run.

---

## 1. Mission (Company Goal)

> **Build and ship an open-source desktop application that lets engineers interactively simulate and tune two EV motor topologies (Radial Flux PMSM and Axial Flux PM) with engineering-grade fidelity, runs offline on Windows/macOS/Linux, and validates within ±15 % against three reference motors (Tesla Model 3 LR, YASA 750 R, generic 60 kW PMSM).**

**Definition of done for the mission:**
- v1.0 tagged release on GitHub with MIT license.
- Single-file PyInstaller binaries published for Windows, macOS, Linux.
- README with screenshots and a 60-second demo GIF.
- Test suite green; coverage ≥ 80 % on the `physics/` module.
- Three reference presets ship in-app and pass validation tolerances.

**Out of scope (do not let agents drift here):** FEA, thermal coupling beyond a simple temperature-dependent resistance, mobile app, cloud sync, paid features.

---

## 2. Suggested Org Chart

| Role | Suggested agent | Responsibilities | Heartbeat |
|---|---|---|---|
| **CEO (you)** | Human | Approve hires, approve v1.0 release, override on scope creep. | On demand |
| **CTO** | Claude Code (Opus) | Owns architecture, reviews PRs, breaks tickets down further, enforces tech-stack rules. | 4 h |
| **Physics Engineer** | Claude Code (Opus) | Owns `physics/` and `models/`. Implements equations from Appendix A. Writes pytest. | 2 h |
| **GUI Engineer** | Codex / Claude Code (Sonnet) | Owns `ui/`. PyQt6 + pyqtgraph + embedded matplotlib. | 2 h |
| **QA / Validation Engineer** | Cursor / Claude Code (Sonnet) | Validates against reference presets, regression suite, packaging smoke tests. | 6 h |
| **Tech Writer** | Claude Code (Sonnet) | README, in-app help, demo GIF, release notes. | 12 h, late in project |
| **DevOps** | Bash agent | CI (GitHub Actions), PyInstaller builds for 3 OSes, release tagging. | On task |

Reporting lines: Physics, GUI, QA, Writer → CTO → CEO.

---

## 3. Budget & Cost Controls

| Agent | Monthly cap | Hard stop |
|---|---|---|
| CTO | $40 | yes |
| Physics Engineer | $60 | yes |
| GUI Engineer | $60 | yes |
| QA | $25 | yes |
| Writer | $15 | yes |
| DevOps | $10 | yes |
| **Company total** | **$210/mo** | yes |

Expected duration to v1.0: **2–3 weeks of agent calendar time** running on heartbeats.

---

## 4. Governance Gates (require human approval)

1. **G1 — Architecture sign-off** before Phase 1 starts. CTO posts the chosen file layout, dependency versions, and `MotorParams` pydantic schema.
2. **G2 — Physics validation** before Phase 3 starts. Physics Engineer must show the three reference presets matching Appendix B targets within ±15 %.
3. **G3 — UI freeze** before Phase 5 starts. GUI Engineer posts screenshots of all panels.
4. **G4 — Release approval** before tagging v1.0 and publishing binaries.

Anything else: agents proceed autonomously; CEO can chime in via tickets.

---

## 5. Projects (parent tickets)

### P1 — Physics Core
**Owner:** Physics Engineer · **Depends on:** G1 · **Blocks:** P2, P3

Implement the dq-frame model, loss models, MTPA / field-weakening solvers, and the two motor classes. Headless and fully unit-tested. Equations are in **Appendix A**.

### P2 — GUI Shell
**Owner:** GUI Engineer · **Depends on:** P1 (parameter schema only)

PyQt6 main window, parameter panel with sliders/spinboxes wired to a `MotorParams` pydantic model, debounced signal/slot recompute (50 ms), topology selector, splitter layout. Layout sketch in **Appendix C**.

### P3 — Live Plots & Outputs
**Owner:** GUI Engineer (with Physics consult) · **Depends on:** P1, P2

pyqtgraph torque-speed and power-speed curves; matplotlib efficiency-map heatmap (50×50 grid, computed on button press); loss-breakdown bar chart; key-numbers summary panel.

### P4 — Presets, Compare Mode, Export
**Owner:** GUI Engineer · **Depends on:** P3

JSON preset load/save, "Compare both topologies" overlay mode, CSV export for curves.

### P5 — Validation & QA
**Owner:** QA · **Depends on:** P1 (continuously), P3 (gates G2)

Build pytest suite covering every public function in `physics/`. Validate the three reference presets against **Appendix B** targets. Regression checks on every CTO-approved PR.

### P6 — Packaging & Release
**Owner:** DevOps + Writer · **Depends on:** P4, P5, G4

GitHub Actions matrix build (Win/macOS/Linux), PyInstaller single-file binaries, README with screenshots, 60-second demo GIF, signed release notes, v1.0 tag.

---

## 6. Tickets (work items — agents pick these up)

### Physics Core (P1)

- **T-101** Define `MotorParams` pydantic schema covering geometry, electrical, material, and limit fields for both topologies. **AC:** schema validates the 3 reference presets without errors.
- **T-102** Implement `physics/dq_frame.py`: torque equation, steady-state voltage equations. **AC:** unit tests for SPMSM and IPMSM cases.
- **T-103** Implement `physics/losses.py`: copper (with temperature scaling), Steinmetz iron, mechanical friction+windage, stray. **AC:** loss values are non-negative; iron loss scales correctly with f and B.
- **T-104** Implement `physics/control.py`: MTPA solver (closed-form for SPMSM, numerical for IPMSM via scipy), base-speed calculation, field-weakening solver. **AC:** at base speed the voltage limit is exactly met within 1 %.
- **T-105** Implement `models/pmsm.py` with `compute_curve(speeds) -> dict`. **AC:** torque-speed curve shows constant-torque region, then constant-power, then natural roll-off.
- **T-106** Implement `models/afpm.py` analogously, with axial-flux sizing equations from Appendix A. **AC:** at the same `D_o`, AFPM produces measurably higher torque density than PMSM.
- **T-107** Author 3 reference preset JSONs (`tesla_model3.json`, `yasa_750r.json`, `generic_60kw.json`). **AC:** loaded by `MotorParams.parse_file()`.

### GUI Shell (P2)

- **T-201** Set up PyQt6 main window with `QSplitter` left/right layout per Appendix C.
- **T-202** Build `ParamPanel`: collapsible groups (Geometry / Electrical / Material / Limits), sliders + spinboxes two-way bound to `MotorParams`. **AC:** changing a slider emits a `paramsChanged` signal at most every 50 ms.
- **T-203** Topology selector (radio): Radial / Axial / Compare. **AC:** switching topology updates which parameter groups are visible.
- **T-204** Status bar shows compute time per refresh. **AC:** typical refresh < 100 ms.

### Plots & Outputs (P3)

- **T-301** Embed pyqtgraph torque-speed plot. **AC:** updates on `paramsChanged` without flicker.
- **T-302** Embed pyqtgraph power-speed plot.
- **T-303** Key-numbers summary widget (peak T, base ω, max ω, peak P, peak η).
- **T-304** Embed matplotlib efficiency-map widget via `FigureCanvasQTAgg`. Compute on button press to avoid lag. **AC:** a 50×50 map computes in < 5 s on a typical laptop.
- **T-305** Loss-breakdown stacked bar chart for the current operating point (cursor on torque-speed plot picks the point).

### Presets, Compare, Export (P4)

- **T-401** Preset menu: Load / Save / Save As. **AC:** round-trip identical.
- **T-402** "Compare both" mode overlays radial and axial curves with distinct colors and a legend.
- **T-403** "Export curves as CSV" — speed, torque, power, eff, losses columns.

### QA (P5)

- **T-501** pytest scaffolding + GitHub Actions integration.
- **T-502** Per-function tests for `physics/`. **AC:** ≥ 80 % coverage.
- **T-503** Reference-preset validation test that asserts Appendix B numbers within ±15 %. **AC:** test fails informatively if any preset drifts.
- **T-504** Smoke test: PyInstaller-built binary launches on a clean VM and renders the main window.

### Packaging (P6)

- **T-601** GitHub Actions workflow: matrix build for Win/macOS/Linux, PyInstaller `--onefile --windowed`, upload artifacts.
- **T-602** README with feature list, install commands, screenshots, demo GIF, validation table.
- **T-603** v1.0 release notes; tag and publish.

---

## 7. Working Agreements

- **Branch per ticket.** Branch name = ticket ID. PR title starts with ticket ID.
- **No agent merges its own PR** without CTO approval. CTO does not merge own PRs without CEO approval (only on G-gates).
- **All physics formulas cite Appendix A** in code comments. Any deviation requires a ticket and CTO sign-off.
- **No new dependencies** beyond Section 8 without a ticket.
- **Daily standup ticket** auto-generated; each agent posts what it did since last heartbeat.

---

## 8. Tech Stack (locked — do not change without ticket + CTO approval)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| GUI | PyQt6 6.7.x |
| Real-time plots | pyqtgraph |
| Heatmap plots | matplotlib (embedded via `FigureCanvasQTAgg`) |
| Numerics | NumPy, SciPy |
| Config | pydantic v2 |
| Tests | pytest |
| Packaging | PyInstaller |
| CI | GitHub Actions |

Install: `pip install pyqt6==6.7.* pyqtgraph matplotlib numpy scipy pydantic>=2 pytest pyinstaller`

---

## Appendix A — Physics Reference

> All equations use **SI units**. Currents `i_d`, `i_q` are **peak phase values**.

### A.1 Symbols

| Symbol | Meaning | Unit |
|---|---|---|
| `p` | Pole pairs | — |
| `ω_m`, `ω_e = p · ω_m` | Mechanical, electrical angular speed | rad/s |
| `λ_pm` | PM flux linkage | Wb |
| `L_d`, `L_q` | d/q-axis inductance | H |
| `R_s` | Phase resistance | Ω |
| `V_dc`, `V_max = V_dc / √3` | DC bus, max phase voltage (SVPWM) | V |
| `I_max` | Max peak phase current | A |

### A.2 Torque (dq-frame, both topologies)

```
T_em = (3/2) · p · [ λ_pm · i_q + (L_d − L_q) · i_d · i_q ]
```
SPMSM and typical AFPM: `L_d ≈ L_q` → reluctance term vanishes.

### A.3 Steady-state voltages

```
v_d = R_s · i_d − ω_e · L_q · i_q
v_q = R_s · i_q + ω_e · L_d · i_d + ω_e · λ_pm
```
Constraints: `v_d² + v_q² ≤ V_max²` and `i_d² + i_q² ≤ I_max²`.

### A.4 Operating regions

- **Region 1 (MTPA, below base speed).** SPMSM/AFPM: `i_d = 0`, `i_q = I_max`. IPMSM: solve
  ```
  i_d = [λ_pm − √(λ_pm² + 8(L_q − L_d)² · I_max²)] / [4(L_q − L_d)]
  i_q = √(I_max² − i_d²)
  ```
- **Base speed:**
  ```
  ω_e,base = V_max / √( (L_q · i_q,MTPA)² + (λ_pm + L_d · i_d,MTPA)² )
  ```
- **Region 2 (Field Weakening).** Inject negative `i_d`. Solve voltage∩current ellipse intersection with `scipy.optimize.brentq`.
- **Region 3 (MTPV).** Optional; only for strong-saliency IPMSMs.

### A.5 Axial-flux sizing

```
T_em ≈ (π² / 4) · k_w · B_g · A_s · D_avg² · L_a
λ_pm  ≈ N_turns · k_w · B_g · (π / (2p)) · (D_o² − D_i²) / 4
L     ≈ μ_0 · (N_turns · k_w)² · A_gap / (p · g_eff)
```
where `D_avg = (D_o + D_i)/2`, `L_a = (D_o − D_i)/2`, `g_eff = g_mech + l_pm/μ_r`.

Typical ranges: `k_w` 0.9–0.95, `B_g` 0.8–1.0 T, `A_s` 30 000–60 000 A/m.

### A.6 Radial-flux sizing

```
T_em ≈ (π / 2) · k_w · B_g · A_s · D_ro² · L_stk
λ_pm ≈ (2 / π) · N_turns · k_w · B_g · τ_p · L_stk        with  τ_p = π · D_ro / (2p)
```

### A.7 Losses

```
Copper:  P_cu = (3/2) · R_s(T) · (i_d² + i_q²)
              R_s(T) = R_s,20 · (1 + 0.00393 · (T − 20))     [copper temp coeff]

Iron:    P_fe = V_core · [ k_h · f · B_m^α + k_c · (f · B_m)² + k_e · (f · B_m)^1.5 ]
              f = ω_e / (2π);  M19/M270-35A defaults: k_h≈0.02, k_c≈5e-5, α≈1.7

Mech:    P_mech = T_fric · ω_m + k_w · ω_m³                 (defaults T_fric=0.1 Nm, k_w=1e-6)

Stray:   P_stray ≈ 0.01 · P_in                              (MVP lump)

η = (T_em · ω_m) / (T_em · ω_m + P_cu + P_fe + P_mech + P_stray)
```

---

## Appendix B — Validation Targets (gates G2 and T-503)

Each preset must be within **±15 %** of all four columns.

| Preset | Peak torque | Base speed | Peak power | Peak η |
|---|---|---|---|---|
| Tesla Model 3 LR rear (IPMSM) | ~420 Nm | ~6 000 rpm | ~211 kW | ~97 % |
| YASA 750 R (AFPM) | ~790 Nm | ~3 250 rpm | ~200 kW | ~95 % |
| Generic 60 kW PMSM | ~150 Nm | ~4 000 rpm | ~60 kW | ~94 % |

---

## Appendix C — UI Layout Sketch

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

## Appendix D — Project File Structure (target)

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

**End of brief.** Import into Paperclip, hire the org chart, set the budgets, hit go.
