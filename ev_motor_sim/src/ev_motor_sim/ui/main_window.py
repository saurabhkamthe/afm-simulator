import time

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QMenuBar, QStatusBar, QLabel, QGroupBox, QRadioButton,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt

from ev_motor_sim.models import Topology
from ev_motor_sim.models.pmsm import compute_curve
from ev_motor_sim.ui.param_panel import ParamPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EV Motor Simulator")
        self.setMinimumSize(1100, 700)
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
        mb.addMenu("&Presets")
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
        self.btn_save_preset = QPushButton("Save Preset")
        layout.addWidget(self.btn_load_preset)
        layout.addWidget(self.btn_save_preset)

        return container

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
            result = compute_curve(params)
            self._torque_curve.setData(result["speed_rpm"], result["torque_Nm"])
            self._base_speed_line.setValue(result["base_speed_rpm"])
            self._power_curve.setData(result["speed_rpm"], result["power_W"] / 1000.0)
            self._power_base_speed_line.setValue(result["base_speed_rpm"])
            peak_T = result["peak_torque_Nm"]
            base_rpm = result["base_speed_rpm"]
            max_rpm = float(result["speed_rpm"][-1])
            peak_P_kW = float(result["power_W"].max()) / 1000.0
            peak_eta_pct = float(result["efficiency"].max()) * 100.0
            self.summary_label.setText(
                f"Peak T  {peak_T:.0f} N·m  |  Base ω  {base_rpm:.0f} rpm  |"
                f"  Max ω  {max_rpm:.0f} rpm  |  Peak P  {peak_P_kW:.1f} kW  |"
                f"  Peak η  {peak_eta_pct:.1f}%"
            )
        except Exception:
            pass
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.status_label.setText(f"Refresh: {elapsed_ms:.1f} ms")

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
        left_col.addWidget(self._placeholder_frame("Efficiency Map\n(matplotlib — T-304)"))
        right_col.addWidget(self._build_power_speed_plot())
        right_col.addWidget(self._placeholder_frame("Loss Breakdown\n(bar chart — T-305)"))

        grid.addLayout(left_col)
        grid.addLayout(right_col)
        layout.addLayout(grid, stretch=1)

        # Key-numbers summary row (T-303)
        self.summary_label = QLabel("Peak T — | Base ω — | Max ω — | Peak P — | Peak η —")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(self.summary_label)

        # Action buttons row
        btn_row = QHBoxLayout()
        self.btn_compute_eff = QPushButton("Compute Eff Map")
        self.btn_export_csv = QPushButton("Export CSV")
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
        self._torque_curve = pw.plot(pen=pg.mkPen(color="#1f77b4", width=2))
        dash_pen = pg.mkPen(color="#e05f5f", width=1, style=Qt.PenStyle.DashLine)
        self._base_speed_line = pg.InfiniteLine(angle=90, movable=False, pen=dash_pen)
        pw.addItem(self._base_speed_line)
        return pw

    def _build_power_speed_plot(self) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setBackground("w")
        pw.setLabel("left", "Power", units="kW")
        pw.setLabel("bottom", "Speed", units="rpm")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.setMinimumHeight(180)
        pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._power_curve = pw.plot(pen=pg.mkPen(color="#2ca02c", width=2))
        dash_pen = pg.mkPen(color="#e05f5f", width=1, style=Qt.PenStyle.DashLine)
        self._power_base_speed_line = pg.InfiniteLine(angle=90, movable=False, pen=dash_pen)
        pw.addItem(self._power_base_speed_line)
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
