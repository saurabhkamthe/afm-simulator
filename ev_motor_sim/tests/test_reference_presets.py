"""Reference-preset validation tests (T-503).

Asserts Appendix B numbers within ±15 % for all three reference motors:
peak torque (MTPA at I_max), base (corner) speed, peak power, and peak
efficiency.  A test failure means the preset has drifted outside the
engineering tolerance and gates G2.
"""
from __future__ import annotations

import math
from importlib.resources import files

import numpy as np
import pytest

from ev_motor_sim.models.params import MotorParams, RotorSaliency
from ev_motor_sim.physics.dq_frame import electromagnetic_torque
from ev_motor_sim.physics.losses import (
    copper_loss,
    iron_loss,
    mechanical_loss,
    stray_loss,
)

TOLERANCE = 0.15  # ±15 %

# Appendix B targets: peak_torque_Nm, base_speed_rpm, peak_power_W, peak_eta
REFERENCE_TARGETS: dict[str, tuple[float, float, float, float]] = {
    "tesla_model3": (420.0, 6_000.0, 211_000.0, 0.97),
    "yasa_750r":    (790.0, 3_250.0, 200_000.0, 0.95),
    "generic_60kw": (150.0, 4_000.0,  60_000.0, 0.94),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(preset_name: str) -> MotorParams:
    return MotorParams.model_validate_json(
        files("ev_motor_sim.presets").joinpath(f"{preset_name}.json").read_text()
    )


def _mtpa_currents(p: MotorParams) -> tuple[float, float]:
    """Return (i_d, i_q) [A, peak] at I_max using the MTPA strategy.

    For surface PM (L_d ≈ L_q) the optimal angle is i_d = 0, i_q = I_max.
    For interior PM the MTPA angle satisfies a quadratic in sin(δ) derived
    from dT/dδ = 0 (BRIEF §A.2).
    """
    I = p.I_max
    if p.saliency is RotorSaliency.SURFACE or math.isclose(p.L_d, p.L_q, rel_tol=1e-4):
        return 0.0, I
    delta_L = p.L_q - p.L_d  # > 0 for interior
    disc = p.lambda_pm ** 2 + 8.0 * delta_L ** 2 * I ** 2
    sin_delta = (-p.lambda_pm + math.sqrt(disc)) / (4.0 * delta_L * I)
    sin_delta = max(0.0, min(1.0, sin_delta))
    i_d = -I * sin_delta
    i_q = math.sqrt(max(0.0, I ** 2 - i_d ** 2))
    return i_d, i_q


def _base_speed_rpm(p: MotorParams, i_d: float, i_q: float) -> float:
    """Corner speed [rpm] at which |V(i_d, i_q, ω_e)| = V_max.

    Solves the quadratic  a·ω_e² + b·ω_e + (c − V_max²) = 0  for ω_e,
    then converts to rpm.  Returns 0 if no real solution exists.
    """
    R_s = p.R_s()
    V_max = p.V_max
    a = (p.L_q * i_q) ** 2 + (p.L_d * i_d + p.lambda_pm) ** 2
    b = 2.0 * R_s * (i_q * (i_d * (p.L_d - p.L_q) + p.lambda_pm))
    c = R_s ** 2 * (i_d ** 2 + i_q ** 2)
    disc = b ** 2 - 4.0 * a * (c - V_max ** 2)
    if disc < 0.0 or a == 0.0:
        return 0.0
    omega_e = (-b + math.sqrt(disc)) / (2.0 * a)
    omega_m = omega_e / p.p
    return omega_m * 60.0 / (2.0 * math.pi)


def _peak_efficiency(p: MotorParams) -> float:
    """Scan a speed × current grid and return the highest efficiency found."""
    id0, iq0 = _mtpa_currents(p)
    angle = math.atan2(-id0, iq0)          # MTPA current angle from q-axis
    omega_m_max = p.V_max / (p.lambda_pm * p.p) * 1.5
    omega_m_vals = np.linspace(50.0, omega_m_max, 50)
    current_fracs = np.linspace(0.05, 1.0, 40)
    best_eta = 0.0
    for omega_m in omega_m_vals:
        omega_e = omega_m * p.p
        for frac in current_fracs:
            I = frac * p.I_max
            i_d = -I * math.sin(angle)
            i_q = I * math.cos(angle)
            T_em = float(
                electromagnetic_torque(p.p, p.lambda_pm, p.L_d, p.L_q, i_d, i_q)
            )
            if T_em <= 0.0:
                continue
            P_out = T_em * omega_m
            P_cu = float(copper_loss(p.R_s_20, i_d, i_q, p.T_winding))
            P_fe = float(
                iron_loss(omega_e, p.B_g, p.k_h, p.alpha, p.k_c, p.k_e, p.V_core)
            )
            P_mech = float(mechanical_loss(p.T_fric, p.k_windage, omega_m))
            P_in = P_out + P_cu + P_fe + P_mech
            P_in += float(stray_loss(P_in))
            if P_in > 0.0:
                eta = P_out / P_in
                if eta > best_eta:
                    best_eta = eta
    return best_eta


def _assert_within(
    computed: float, target: float, label: str, preset: str
) -> None:
    lo = target * (1.0 - TOLERANCE)
    hi = target * (1.0 + TOLERANCE)
    assert lo <= computed <= hi, (
        f"{preset} | {label}: computed={computed:.4g}, target={target:.4g}, "
        f"allowed=[{lo:.4g} … {hi:.4g}]  (±{TOLERANCE*100:.0f} %)"
    )


# ---------------------------------------------------------------------------
# Parametrised validation tests
# ---------------------------------------------------------------------------

@pytest.mark.validation
@pytest.mark.parametrize("preset_name,targets", REFERENCE_TARGETS.items())
class TestReferencePresets:
    """Asserts Appendix B numbers within ±15 % (T-503, gates G2)."""

    def test_peak_torque(self, preset_name: str, targets: tuple) -> None:
        t_target, *_ = targets
        p = _load(preset_name)
        i_d, i_q = _mtpa_currents(p)
        T_peak = float(
            electromagnetic_torque(p.p, p.lambda_pm, p.L_d, p.L_q, i_d, i_q)
        )
        _assert_within(T_peak, t_target, "peak torque [Nm]", preset_name)

    def test_base_speed(self, preset_name: str, targets: tuple) -> None:
        _, n_target, *_ = targets
        p = _load(preset_name)
        i_d, i_q = _mtpa_currents(p)
        n_base = _base_speed_rpm(p, i_d, i_q)
        _assert_within(n_base, n_target, "base speed [rpm]", preset_name)

    def test_peak_power(self, preset_name: str, targets: tuple) -> None:
        t_target, n_target, P_target, _ = targets
        p = _load(preset_name)
        i_d, i_q = _mtpa_currents(p)
        T_peak = float(
            electromagnetic_torque(p.p, p.lambda_pm, p.L_d, p.L_q, i_d, i_q)
        )
        n_base = _base_speed_rpm(p, i_d, i_q)
        omega_m_base = n_base * 2.0 * math.pi / 60.0
        P_peak = T_peak * omega_m_base
        _assert_within(P_peak, P_target, "peak power [W]", preset_name)

    def test_peak_efficiency(self, preset_name: str, targets: tuple) -> None:
        *_, eta_target = targets
        p = _load(preset_name)
        eta_peak = _peak_efficiency(p)
        _assert_within(eta_peak, eta_target, "peak efficiency [-]", preset_name)
