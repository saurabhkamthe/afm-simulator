import csv
import time
from pathlib import Path

import pyqtgraph as pg
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QMenuBar, QStatusBar, QLabel,
    QGroupBox, QRadioButton, QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt

from ev_motor_sim.models import Topology
from ev_motor_sim.models.params import MotorParams
from ev_motor_sim.models.pmsm import compute_curve as compute_curve_pmsm
from ev_motor_sim.models.afpm import compute_curve as compute_curve_afpm
from ev_motor_sim.presets import list_builtins, load_builtin
from ev_motor_sim.ui.efficiency_map_widget import EfficiencyMapWidget
from ev_motor_sim.ui.key_numbers_widget import KeyNumbersWidget
from ev_motor_sim.ui.loss_breakdown_widget import LossBreakdownWidget
from ev_motor_sim.ui.param_panel import ParamPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EV Motor Simulator")
        self.setMinimumSize(1100, 700)
        self._current_preset_path: Path | None = None
        self._last_result: dict | None = None
        self._last_result_axial: dict | None = None
        self._build_menu()
        self._build_central()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _build_menu(self):
        mb = QMenuBar(self)
        mb.addMenu("&File")
        mb.addMenu("&View")

        presets_menu = mb.addMenu("&Presets")

        # Built-in presets
        for display_name, filename in list_builtins():
            action = QAction(display_name, self)
            action.triggered.connect(
                lambda checked=False, fn=filename: self._on_load_builtin(fn)
            )
            presets_menu.addAction(action)

        presets_menu.addSeparator()

        load_action = QAction("&Load Preset…", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._on_load_preset)
        presets_menu.addAction(load_action)

        self._save_action = QAction("&Save Preset", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._on_save_preset)
        presets_menu.addAction(self._save_action)

        save_as_action = QAction("Save Preset &As…", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_preset_as)
        presets_menu.addAction(save_as_action)

        mb.addMenu("&Help")
        self.setMenuBar(mb)

    # ------------------------------------------------------------------
    # Central widget — QSplitter with left param panel / right plot area
    # ------------------------------------------------------------------
    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())

        # ~25 % left / ~75 % right initial split
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # Left panel: topology selector + param groups + preset buttons
    # ------------------------------------------------------------------
    def _build_left_panel(self):
        container = QWidget()
        container.setMinimumWidth(220)
        container.setMaximumWidth(320)
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Topology selector
        topo_box = QGroupBox("Topology")
        topo_layout = QVBoxLayout(topo_box)
        self.radio_radial = QRadioButton("Radial PMSM")
        self.radio_axial = QRadioButton("Axial Flux")
        self.radio_compare = QRadioButton("Compare")
        self.radio_radial.setChecked(True)
        for rb in (self.radio_radial, self.radio_axial, self.radio_compare):
            topo_layout.addWidget(rb)
        layout.addWidget(topo_box)

        # Parameter panel (T-202): collapsible groups with sliders + spinboxes.
        self.param_panel = ParamPanel()
        self.param_panel.paramsChanged.connect(self._on_params_changed)
        layout.addWidget(self.param_panel, stretch=1)

        # Wire topology radio buttons now that param_panel exists.
        self.radio_radial.toggled.connect(
            lambda checked: checked and self._on_topology_changed()
        )
        self.radio_axial.toggled.connect(
            lambda checked: checked and self._on_topology_changed()
        )
        self.radio_compare.toggled.connect(
            lambda checked: checked and self._on_topology_changed()
        )

        # Preset buttons
        self.btn_load_preset = QPushButton("Load Preset")
        self.btn_load_preset.clicked.connect(self._on_load_preset)
        self.btn_save_preset = QPushButton("Save Preset")
        self.btn_save_preset.clicked.connect(self._on_save_preset)
        layout.addWidget(self.btn_load_preset)
        layout.addWidget(self.btn_save_preset)

        return container

    # ------------------------------------------------------------------
    # Preset actions
    # ------------------------------------------------------------------

    def _apply_params(self, params: MotorParams) -> None:
        """Load *params* into the UI without emitting paramsChanged immediately."""
        if params.topology == Topology.RADIAL_PMSM:
            self.radio_radial.setChecked(True)
        elif params.topology == Topology.AXIAL_FLUX_PM:
            self.radio_axial.setChecked(True)
        self.param_panel.set_params(params)
        self.param_panel.paramsChanged.emit(params)
        self.status_label.setText(f"Loaded: {params.name}")

    def _on_load_builtin(self, filename: str) -> None:
        try:
            params = load_builtin(filename)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            return
        self._current_preset_path = None
        self._apply_params(params)

    def _on_load_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Preset", "", "JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            params = MotorParams.from_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            return
        self._current_preset_path = Path(path)
        self._apply_params(params)

    def _on_save_preset(self) -> None:
        if self._current_preset_path is None:
            self._on_save_preset_as()
            return
        try:
            self.param_panel.get_params().to_file(self._current_preset_path)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        self.status_label.setText(f"Saved: {self._current_preset_path.name}")

    def _on_save_preset_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Preset As", "", "JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        self._current_preset_path = Path(path)
        try:
            self.param_panel.get_params().to_file(self._current_preset_path)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        self.status_label.setText(f"Saved: {self._current_preset_path.name}")

    def _on_topology_changed(self) -> None:
        if self.radio_radial.isChecked():
            topo: Topology | None = Topology.RADIAL_PMSM
            label = "Radial PMSM"
        elif self.radio_axial.isChecked():
            topo = Topology.AXIAL_FLUX_PM
            label = "Axial Flux"
        else:
            topo = None  # Compare: show all geometry rows
            label = "Compare"
        self.param_panel.set_topology(topo)
        self.status_label.setText(f"Topology: {label}")

    def _on_params_changed(self, params) -> None:
        t0 = time.perf_counter()
        try:
            is_compare = self.radio_compare.isChecked()
            if is_compare:
                r_result = compute_curve_pmsm(params)
                a_result = compute_curve_afpm(params)
                self._last_result = r_result
                self._last_result_axial = a_result
                self._torque_curve.setData(r_result["speed_rpm"], r_result["torque_Nm"])
                self._torque_curve_axial.setData(a_result["speed_rpm"], a_result["torque_Nm"])
                self._torque_curve_axial.setVisible(True)
                self._base_speed_line.setValue(r_result["base_speed_rpm"])
                self._power_curve.setData(r_result["speed_rpm"], r_result["power_W"] / 1000.0)
                self._power_curve_axial.setData(a_result["speed_rpm"], a_result["power_W"] / 1000.0)
                self._power_curve_axial.setVisible(True)
                self._power_base_speed_line.setValue(r_result["base_speed_rpm"])
                self._ts_legend.setVisible(True)
                self._ps_legend.setVisible(True)
                result = r_result
            else:
                result = compute_curve_pmsm(params)
                self._last_result = result
                self._last_result_axial = None
                self._torque_curve.setData(result["speed_rpm"], result["torque_Nm"])
                self._torque_curve_axial.setVisible(False)
                self._base_speed_line.setValue(result["base_speed_rpm"])
                self._power_curve.setData(result["speed_rpm"], result["power_W"] / 1000.0)
                self._power_curve_axial.setVisible(False)
                self._power_base_speed_line.setValue(result["base_speed_rpm"])
                self._ts_legend.setVisible(False)
                self._ps_legend.setVisible(False)
            peak_T = result["peak_torque_Nm"]
            base_rpm = result["base_speed_rpm"]
            max_rpm = float(result["speed_rpm"][-1])
            peak_P_kW = float(result["power_W"].max()) / 1000.0
            peak_eta_pct = float(result["efficiency"].max()) * 100.0
            self.key_numbers.update_values(peak_T, base_rpm, max_rpm, peak_P_kW, peak_eta_pct)
            params_dict = params if isinstance(params, dict) else params.model_dump()
            self._eff_map_widget.update_params(params_dict)
            self._loss_bar_widget.update_params(params_dict)
        except Exception:
            pass
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.status_label.setText(f"Refresh: {elapsed_ms:.1f} ms")

    def _on_torque_speed_mouse_moved(self, evt) -> None:
        pos = evt[0]
        if self._ts_plot.sceneBoundingRect().contains(pos):
            mouse_point = self._ts_plot.getViewBox().mapSceneToView(pos)
            self._loss_bar_widget.update_point(mouse_point.x())

    def _on_compute_eff_map(self) -> None:
        t0 = time.perf_counter()
        self.status_label.setText("Computing efficiency map…")
        self._eff_map_widget.compute_and_draw()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.status_label.setText(f"Eff map: {elapsed_ms:.0f} ms")

    def _on_export_csv(self) -> None:
        if self._last_result is None:
            QMessageBox.warning(self, "No Data", "No curve data to export. Adjust parameters first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "motor_curves.csv", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"

        try:
            r = self._last_result
            a = self._last_result_axial
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                if a is None:
                    writer.writerow([
                        "speed (rpm)", "torque (N·m)", "power (W)",
                        "efficiency (%)", "total_loss (W)",
                    ])
                    for i in range(len(r["speed_rpm"])):
                        writer.writerow([
                            f"{r['speed_rpm'][i]:.4f}",
                            f"{r['torque_Nm'][i]:.4f}",
                            f"{r['power_W'][i]:.4f}",
                            f"{r['efficiency'][i] * 100.0:.4f}",
                            f"{r['losses_W'][i]:.4f}",
                        ])
                else:
                    writer.writerow([
                        "radial_speed (rpm)", "radial_torque (N·m)", "radial_power (W)",
                        "radial_efficiency (%)", "radial_total_loss (W)",
                        "axial_speed (rpm)", "axial_torque (N·m)", "axial_power (W)",
                        "axial_efficiency (%)", "axial_total_loss (W)",
                    ])
                    n = max(len(r["speed_rpm"]), len(a["speed_rpm"]))
                    r_n = len(r["speed_rpm"])
                    a_n = len(a["speed_rpm"])
                    for i in range(n):
                        r_row = (
                            [f"{r['speed_rpm'][i]:.4f}", f"{r['torque_Nm'][i]:.4f}",
                             f"{r['power_W'][i]:.4f}", f"{r['efficiency'][i] * 100.0:.4f}",
                             f"{r['losses_W'][i]:.4f}"]
                            if i < r_n else ["", "", "", "", ""]
                        )
                        a_row = (
                            [f"{a['speed_rpm'][i]:.4f}", f"{a['torque_Nm'][i]:.4f}",
                             f"{a['power_W'][i]:.4f}", f"{a['efficiency'][i] * 100.0:.4f}",
                             f"{a['losses_W'][i]:.4f}"]
                            if i < a_n else ["", "", "", "", ""]
                        )
                        writer.writerow(r_row + a_row)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return

        self.status_label.setText(f"Exported: {Path(path).name}")

    # ------------------------------------------------------------------
    # Right panel: 2×2 plot grid + summary row + action buttons
    # ------------------------------------------------------------------
    def _build_right_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # 2×2 plot grid
        grid = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        left_col.addWidget(self._build_torque_speed_plot())
        self._eff_map_widget = EfficiencyMapWidget()
        left_col.addWidget(self._eff_map_widget)
        right_col.addWidget(self._build_power_speed_plot())
        self._loss_bar_widget = LossBreakdownWidget()
        right_col.addWidget(self._loss_bar_widget)

        # Wire cursor on T-ω plot → loss breakdown (throttled via SignalProxy)
        self._ts_mouse_proxy = pg.SignalProxy(
            self._ts_plot.scene().sigMouseMoved,
            rateLimit=30,
            slot=self._on_torque_speed_mouse_moved,
        )

        grid.addLayout(left_col)
        grid.addLayout(right_col)
        layout.addLayout(grid, stretch=1)

        # Key-numbers summary row (T-303)
        self.key_numbers = KeyNumbersWidget()
        layout.addWidget(self.key_numbers)

        # Action buttons row
        btn_row = QHBoxLayout()
        self.btn_compute_eff = QPushButton("Compute Eff Map")
        self.btn_compute_eff.clicked.connect(self._on_compute_eff_map)
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_compute_eff)
        btn_row.addWidget(self.btn_export_csv)
        layout.addLayout(btn_row)

        return container

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_status_bar(self):
        self.status_label = QLabel("Ready")
        sb = QStatusBar(self)
        sb.addWidget(self.status_label)
        self.setStatusBar(sb)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_torque_speed_plot(self) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setBackground("w")
        pw.setLabel("left", "Torque", units="N·m")
        pw.setLabel("bottom", "Speed", units="rpm")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.setMinimumHeight(180)
        pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._torque_curve = pw.plot(pen=pg.mkPen(color="#1f77b4", width=2), name="Radial PMSM")
        self._torque_curve_axial = pw.plot(pen=pg.mkPen(color="#ff7f0e", width=2), name="Axial Flux")
        self._torque_curve_axial.setVisible(False)
        dash_pen = pg.mkPen(color="#e05f5f", width=1, style=Qt.PenStyle.DashLine)
        self._base_speed_line = pg.InfiniteLine(angle=90, movable=False, pen=dash_pen)
        pw.addItem(self._base_speed_line)
        self._ts_legend = pw.addLegend(offset=(10, 10))
        self._ts_legend.addItem(self._torque_curve, "Radial PMSM")
        self._ts_legend.addItem(self._torque_curve_axial, "Axial Flux")
        self._ts_legend.setVisible(False)
        self._ts_plot = pw
        return pw

    def _build_power_speed_plot(self) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setBackground("w")
        pw.setLabel("left", "Power", units="kW")
        pw.setLabel("bottom", "Speed", units="rpm")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.setMinimumHeight(180)
        pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._power_curve = pw.plot(pen=pg.mkPen(color="#2ca02c", width=2), name="Radial PMSM")
        self._power_curve_axial = pw.plot(pen=pg.mkPen(color="#ff7f0e", width=2), name="Axial Flux")
        self._power_curve_axial.setVisible(False)
        dash_pen = pg.mkPen(color="#e05f5f", width=1, style=Qt.PenStyle.DashLine)
        self._power_base_speed_line = pg.InfiniteLine(angle=90, movable=False, pen=dash_pen)
        pw.addItem(self._power_base_speed_line)
        self._ps_legend = pw.addLegend(offset=(10, 10))
        self._ps_legend.addItem(self._power_curve, "Radial PMSM")
        self._ps_legend.addItem(self._power_curve_axial, "Axial Flux")
        self._ps_legend.setVisible(False)
        return pw

    @staticmethod
    def _placeholder_frame(text: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumHeight(180)
        layout = QVBoxLayout(frame)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: gray;")
        layout.addWidget(lbl)
        return frame
