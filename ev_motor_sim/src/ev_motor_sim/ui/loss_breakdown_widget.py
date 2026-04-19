"""Stacked-bar loss-breakdown widget for the current operating point (T-305).

Updates whenever the cursor moves on the T-ω plot.
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
from ev_motor_sim.physics.losses import copper_loss, iron_loss, stray_loss, windage_loss

_LABELS = ["Copper", "Iron", "Windage", "Stray"]
_COLORS = ["#e05f5f", "#f5a623", "#4a90d9", "#7ed321"]


def _losses_at(params: dict, speed_rpm: float) -> tuple[float, float, float, float]:
    """Return (P_cu_W, P_fe_W, P_wind_W, P_stray_W) at the given speed (full-load MTPA/FW)."""
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
    omega_m = max(speed_rpm, 1.0) * (2.0 * pi / 60.0)
    omega_e = p_pairs * omega_m

    if omega_m <= omega_m_base * (1.0 + 1e-6):
        i_d, i_q = mtpa_currents(lambda_pm, L_d, L_q, I_max)
    else:
        i_d, i_q = field_weakening(lambda_pm, L_d, L_q, I_max, V_max, omega_e)

    T_em = float(electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d, i_q))
    T_shaft = max(T_em - T_fric, 0.0)
    P_shaft = T_shaft * omega_m

    P_cu = float(copper_loss(R_s_20, i_d, i_q, T_winding))
    P_fe = float(iron_loss(omega_e, B_g, k_h, alpha, k_c, k_e, V_core))
    P_wind = float(windage_loss(k_windage, omega_m))
    P_in = P_shaft + P_cu + P_fe + P_wind
    P_stray = float(stray_loss(P_in))

    return P_cu, P_fe, P_wind, P_stray


class LossBreakdownWidget(QWidget):
    """Stacked bar chart of loss components at the cursor operating point."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._placeholder = QLabel("Hover over the T-ω plot to see loss breakdown")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: gray; font-size: 11px;")

        layout.addWidget(self._placeholder)
        layout.addWidget(self._canvas)
        self._canvas.hide()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)

    # ------------------------------------------------------------------
    def update_params(self, params: dict) -> None:
        """Store latest motor params (does not redraw)."""
        self._params = params

    def update_point(self, speed_rpm: float) -> None:
        """Recompute losses at *speed_rpm* and redraw the stacked bar chart."""
        if self._params is None or speed_rpm <= 0:
            return

        try:
            P_cu, P_fe, P_wind, P_stray = _losses_at(self._params, speed_rpm)
        except Exception:
            return

        values_kW = [v / 1000.0 for v in (P_cu, P_fe, P_wind, P_stray)]
        total_kW = sum(values_kW)

        self._ax.clear()
        bottom = 0.0
        x = ["Operating\nPoint"]
        for label, val, color in zip(_LABELS, values_kW, _COLORS):
            bar = self._ax.bar(x, [val], bottom=[bottom], color=color, label=label,
                               edgecolor="white", linewidth=0.5)
            # Annotate segment if tall enough to label
            if val > 0.005 * total_kW:
                self._ax.text(
                    0,
                    bottom + val / 2.0,
                    f"{val * 1000:.0f} W",
                    ha="center", va="center",
                    fontsize=7, color="white", fontweight="bold",
                )
            bottom += val

        self._ax.set_ylabel("Loss (kW)", fontsize=8)
        self._ax.set_title(
            f"Loss Breakdown @ {speed_rpm:.0f} rpm  (Σ {total_kW:.2f} kW)",
            fontsize=9,
        )
        self._ax.legend(loc="upper right", fontsize=7, framealpha=0.8)
        self._ax.tick_params(axis="x", labelbottom=False)
        self._ax.tick_params(labelsize=7)

        self._placeholder.hide()
        self._canvas.show()
        self._canvas.draw()
