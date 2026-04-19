"""Radial-flux PMSM torque-speed-efficiency curve model (T-105).

``compute_curve`` sweeps mechanical speeds and computes torque, power, and
efficiency using the dq-frame, loss, and control sub-modules.
"""

from __future__ import annotations

from math import pi, sqrt
from typing import Any, Dict, Optional, Sequence

import numpy as np

from ev_motor_sim.physics.control import (
    base_speed as _base_speed,
    field_weakening,
    mtpa_currents,
)
from ev_motor_sim.physics.dq_frame import electromagnetic_torque
from ev_motor_sim.physics.losses import copper_loss, iron_loss, windage_loss

_N_DEFAULT = 200


def _extract(p: Any) -> dict:
    """Accept a MotorParams pydantic object or a plain dict."""
    if isinstance(p, dict):
        return p
    # Pydantic v2 model_dump
    return p.model_dump()


def compute_curve(
    params: Any,
    speeds_rpm: Optional[Sequence[float]] = None,
) -> Dict[str, np.ndarray]:
    """Compute the torque-speed-efficiency curve for a radial-flux PMSM.

    Parameters
    ----------
    params:
        Motor parameters — accepts ``MotorParams`` (pydantic) or a plain dict
        with the keys used in tests (``p``, ``lambda_pm``, ``L_d``, ``L_q``,
        ``R_s``, ``R_s20``/``R_s_20``, ``V_dc``, ``I_max``, ``T_fric`` …).
    speeds_rpm:
        Mechanical shaft speeds [rpm].  If *None*, 200 points from 0 to
        3 × base-speed are used.

    Returns
    -------
    dict with keys:
        ``speed_rpm``, ``speed_rad_s``, ``torque_Nm``, ``power_W``,
        ``efficiency``, ``base_speed_rpm``, ``peak_torque_Nm``
    """
    d = _extract(params)

    p_pairs = int(d["p"])
    lambda_pm = float(d["lambda_pm"])
    L_d = float(d["L_d"])
    L_q = float(d["L_q"])
    R_s_20 = float(d.get("R_s20") or d.get("R_s_20") or d.get("R_s", 0.05))
    T_winding = float(d.get("T_winding", 80.0))
    V_dc = float(d["V_dc"])
    I_max = float(d["I_max"])
    T_fric = float(d.get("T_fric", 0.0))
    k_windage = float(d.get("k_windage", 0.0))
    B_g = float(d.get("B_g", 0.95))
    k_h = float(d.get("k_h", 0.02))
    alpha = float(d.get("alpha", 1.7))
    k_c = float(d.get("k_c", 5.0e-5))
    k_e = float(d.get("k_e", 0.0))
    V_core = float(d.get("V_core", 2.0e-3))

    V_max = V_dc / sqrt(3.0)

    # Electrical base speed and mechanical equivalent
    omega_e_base = _base_speed(lambda_pm, L_d, L_q, I_max, V_max)
    omega_m_base = omega_e_base / p_pairs

    # Build speed array
    if speeds_rpm is not None:
        omega_m_arr = np.asarray(speeds_rpm, dtype=float) * (2.0 * pi / 60.0)
    else:
        omega_m_arr = np.linspace(0.5, 3.0 * omega_m_base, _N_DEFAULT)

    n = len(omega_m_arr)
    torque_arr = np.zeros(n)
    power_arr = np.zeros(n)
    eff_arr = np.zeros(n)
    losses_arr = np.zeros(n)

    # MTPA currents at full load (below base speed)
    i_d_base, i_q_base = mtpa_currents(lambda_pm, L_d, L_q, I_max)
    T_em_base = float(electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d_base, i_q_base))

    for k, omega_m in enumerate(omega_m_arr):
        omega_e = p_pairs * omega_m

        if omega_m <= omega_m_base * (1.0 + 1e-6):
            i_d, i_q = i_d_base, i_q_base
        else:
            i_d, i_q = field_weakening(lambda_pm, L_d, L_q, I_max, V_max, omega_e)

        T_em = float(electromagnetic_torque(p_pairs, lambda_pm, L_d, L_q, i_d, i_q))
        T_shaft = max(T_em - T_fric, 0.0)
        P_shaft = T_shaft * omega_m

        P_cu = float(copper_loss(R_s_20, i_d, i_q, T_winding))
        P_fe = float(iron_loss(omega_e, B_g, k_h, alpha, k_c, k_e, V_core))
        P_wind = float(windage_loss(k_windage, omega_m))
        P_loss = P_cu + P_fe + P_wind
        P_in = P_shaft + P_loss

        if P_in > 0.0:
            eff_arr[k] = min(P_shaft / P_in, 1.0)
        torque_arr[k] = T_shaft
        power_arr[k] = P_shaft
        losses_arr[k] = P_loss

    return {
        "speed_rpm": omega_m_arr * (60.0 / (2.0 * pi)),
        "speed_rad_s": omega_m_arr,
        "torque_Nm": torque_arr,
        "power_W": power_arr,
        "efficiency": eff_arr,
        "losses_W": losses_arr,
        "base_speed_rpm": float(omega_m_base * (60.0 / (2.0 * pi))),
        "peak_torque_Nm": float(T_em_base),
    }
