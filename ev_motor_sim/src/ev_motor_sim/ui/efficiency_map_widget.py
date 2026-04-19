"""Matplotlib efficiency-map widget embedded via FigureCanvasQTAgg (T-304).

Computes a 50×50 (torque × speed) grid on button press to avoid UI lag.
"""

from __future__ import annotations

from math import pi, sqrt

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ev_motor_sim.physics.control import base_speed, field_weakening, mtpa_currents
from ev_motor_sim.physics.dq_frame import electromagnetic_torque
from ev_motor_sim.physics.losses import copper_loss, iron_loss, windage_loss

_N = 50  # grid resolution (50×50)


def _compute_map(params: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (speed_rpm 1-D, torque_Nm 1-D, efficiency 2-D [torque, speed])."""
    p_pairs = int(params["p"])
    lambda_pm = float(params["lambda_pm"])
    L_d = float(params["L_d"])
    L_q = float(params["L_q"])
    R_s_20 = float(params.get("R_s20") or params.get("R_s_20") or params.get("R_s", 0.05))
    T_winding = float(params.get("T_winding", 80.0))
    V_dc = float(params["V_dc"])
    I_max = float(params["I_max"])
    T_fric = float(params.get("T_fric", 0.0))
    k_windage = float(params.get("k_windage", 0.0))
    B_g = float(params.get("B_g", 0.95))
    k_h = float(params.get("k_h", 0.02))
    alpha = float(params.get("alpha", 1.7))
    k_c = float(params.get("k_c", 5.0e-5))
    k_e = float(params.get("k_e", 0.0))
    V_core = float(params.get("V_core", 2.0e-3))

    V_max = V_dc / sqrt(3.0)
    omega_e_base = base_speed(lambda_pm, L_d, L_q, I_max, V_max)
    omega_m_base = omega_e_base / p_pairs

    i_d_mtpa, i_q_mtpa = mtpa_currents(lambda_pm, L_d, L_q, I_max)
    T_peak = float(electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d_mtpa, i_q_mtpa))
    T_peak = max(T_peak - T_fric, 1.0)

    speed_rpm = np.linspace(100.0, 3.0 * omega_m_base * 60.0 / (2.0 * pi), _N)
    torque_Nm = np.linspace(0.05 * T_peak, T_peak, _N)

    eff_map = np.full((_N, _N), np.nan)

    # mtpa_currents T_req is in the internal scale (without 3/2·p factor)
    _scale = 1.5 * p_pairs

    for j, rpm in enumerate(speed_rpm):
        omega_m = rpm * (2.0 * pi / 60.0)
        omega_e = p_pairs * omega_m

        if omega_m <= omega_m_base * (1.0 + 1e-6):
            i_d_ceil, i_q_ceil = i_d_mtpa, i_q_mtpa
        else:
            i_d_ceil, i_q_ceil = field_weakening(lambda_pm, L_d, L_q, I_max, V_max, omega_e)

        T_ceil = float(
            electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d_ceil, i_q_ceil)
        ) - T_fric

        for i, T_req in enumerate(torque_Nm):
            if T_req > T_ceil + 0.5:
                continue

            t_internal = min(T_req, T_ceil) / _scale
            i_d, i_q = mtpa_currents(lambda_pm, L_d, L_q, I_max, T_req=t_internal)

            T_shaft = max(
                float(electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d, i_q)) - T_fric,
                0.0,
            )
            P_shaft = T_shaft * omega_m

            P_cu = float(copper_loss(R_s_20, i_d, i_q, T_winding))
            P_fe = float(iron_loss(omega_e, B_g, k_h, alpha, k_c, k_e, V_core))
            P_wind = float(windage_loss(k_windage, omega_m))
            P_loss = P_cu + P_fe + P_wind
            P_in = P_shaft + P_loss

            if P_in > 0.0:
                eff_map[i, j] = min(P_shaft / P_in, 1.0) * 100.0

    return speed_rpm, torque_Nm, eff_map


class EfficiencyMapWidget(QWidget):
    """Embeds a matplotlib contour efficiency map; renders only when triggered."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._placeholder = QLabel('Press  \u201cCompute Eff Map\u201d  to render')
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: gray; font-size: 11px;")

        layout.addWidget(self._placeholder)
        layout.addWidget(self._canvas)
        self._canvas.hide()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)

    # ------------------------------------------------------------------
    def update_params(self, params: dict) -> None:
        """Store latest motor params (does not trigger a redraw)."""
        self._params = params

    def compute_and_draw(self) -> None:
        """Compute the map from the last stored params and redraw the canvas."""
        if self._params is None:
            return

        speed_rpm, torque_Nm, eff_map = _compute_map(self._params)

        self._ax.clear()
        spd, tq = np.meshgrid(speed_rpm, torque_Nm)
        levels = np.arange(50, 101, 2)
        cf = self._ax.contourf(spd, tq, eff_map, levels=levels, cmap="RdYlGn", extend="min")

        if not hasattr(self, "_cbar"):
            self._cbar = self._fig.colorbar(cf, ax=self._ax, label="η (%)")
        else:
            self._cbar.update_normal(cf)

        self._ax.set_xlabel("Speed (rpm)", fontsize=8)
        self._ax.set_ylabel("Torque (N·m)", fontsize=8)
        self._ax.set_title("Efficiency Map", fontsize=9)
        self._ax.tick_params(labelsize=7)

        self._placeholder.hide()
        self._canvas.show()
        self._canvas.draw()
