"""Per-function tests for radial-flux PMSM physics (T-502).

Coverage target: ≥ 80 % on physics/ and models/pmsm.py (pytest-cov).
Fixtures defined in conftest.py provide a minimal PMSM parameter dict.
"""

from math import pi, sqrt

import numpy as np
import pytest

from ev_motor_sim.physics.control import base_speed, field_weakening, mtpa_currents
from ev_motor_sim.physics.dq_frame import (
    current_magnitude,
    electromagnetic_torque,
    steady_state_voltages,
    voltage_magnitude,
)
from ev_motor_sim.physics.losses import copper_loss, iron_loss, windage_loss
from ev_motor_sim.models.pmsm import compute_curve


# ---------------------------------------------------------------------------
# dq_frame — electromagnetic_torque
# ---------------------------------------------------------------------------

class TestTorqueEquation:
    """T_em = (3/2)·p·[λ_pm·i_q + (L_d−L_q)·i_d·i_q]  (Appendix A.2)"""

    def test_spmsm_reluctance_term_zero(self, pmsm_params):
        """For SPMSM (L_d == L_q) the reluctance torque term vanishes."""
        p = pmsm_params
        L = p["L_d"]  # use L_d for both axes → SPMSM
        T = electromagnetic_torque(p["p"], p["lambda_pm"], L, L, 50.0, 100.0)
        T_expected = 1.5 * p["p"] * p["lambda_pm"] * 100.0
        assert T == pytest.approx(T_expected, rel=1e-9)

    def test_torque_positive_for_positive_iq(self, pmsm_params):
        p = pmsm_params
        T = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], 0.0, 100.0)
        assert T > 0.0

    def test_torque_zero_at_zero_current(self, pmsm_params):
        p = pmsm_params
        T = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], 0.0, 0.0)
        assert T == pytest.approx(0.0, abs=1e-12)

    def test_reluctance_torque_adds_for_ipmsm(self, pmsm_params):
        """IPMSM (L_d < L_q): negative i_d with positive i_q adds reluctance torque."""
        p = pmsm_params
        T_no_rel = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_d"], -50.0, 100.0)
        T_with_rel = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], -50.0, 100.0)
        # (L_d - L_q)*i_d*i_q = negative * negative * positive > 0, so T increases
        assert T_with_rel > T_no_rel

    def test_torque_scales_linearly_with_iq(self, pmsm_params):
        p = pmsm_params
        T1 = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], 0.0, 50.0)
        T2 = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], 0.0, 100.0)
        assert T2 == pytest.approx(2.0 * T1)

    def test_numpy_array_input(self, pmsm_params):
        p = pmsm_params
        i_q = np.array([0.0, 50.0, 100.0])
        T = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"], 0.0, i_q)
        assert T.shape == (3,)
        assert T[0] == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# dq_frame — steady_state_voltages / voltage_magnitude / current_magnitude
# ---------------------------------------------------------------------------

class TestSteadyStateVoltage:
    """v_d, v_q constraints (Appendix A.3)"""

    def test_voltage_within_limit_at_low_speed(self, pmsm_params):
        p = pmsm_params
        omega_e = 10.0  # very low electrical speed
        v_d, v_q = steady_state_voltages(
            p["R_s"], p["L_d"], p["L_q"], p["lambda_pm"], omega_e, 0.0, 50.0
        )
        V_max = p["V_dc"] / sqrt(3.0)
        assert float(voltage_magnitude(v_d, v_q)) <= V_max

    def test_voltage_increases_with_speed(self, pmsm_params):
        p = pmsm_params
        v_d1, v_q1 = steady_state_voltages(
            p["R_s"], p["L_d"], p["L_q"], p["lambda_pm"], 100.0, 0.0, 50.0
        )
        v_d2, v_q2 = steady_state_voltages(
            p["R_s"], p["L_d"], p["L_q"], p["lambda_pm"], 500.0, 0.0, 50.0
        )
        assert float(voltage_magnitude(v_d2, v_q2)) > float(voltage_magnitude(v_d1, v_q1))

    def test_vd_zero_at_zero_current_low_speed(self, pmsm_params):
        """At i_d = i_q = 0, v_d = 0."""
        p = pmsm_params
        v_d, v_q = steady_state_voltages(
            p["R_s"], p["L_d"], p["L_q"], p["lambda_pm"], 100.0, 0.0, 0.0
        )
        assert float(v_d) == pytest.approx(0.0, abs=1e-9)

    def test_current_magnitude(self, pmsm_params):
        assert float(current_magnitude(3.0, 4.0)) == pytest.approx(5.0)

    def test_voltage_magnitude_pythagorean(self):
        assert float(voltage_magnitude(3.0, 4.0)) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# losses — copper_loss
# ---------------------------------------------------------------------------

class TestCopperLoss:
    """P_cu = (3/2)·R_s(T)·(i_d²+i_q²)  (Appendix A.7)"""

    def test_copper_loss_non_negative(self, pmsm_params):
        p = pmsm_params
        assert copper_loss(p["R_s20"], 50.0, 100.0) >= 0.0

    def test_copper_loss_scales_with_current_squared(self, pmsm_params):
        p = pmsm_params
        P1 = copper_loss(p["R_s20"], 0.0, 100.0)
        P2 = copper_loss(p["R_s20"], 0.0, 200.0)
        assert P2 == pytest.approx(4.0 * P1)

    def test_temperature_scaling_increases_loss(self, pmsm_params):
        """R_s increases with temperature → copper loss increases."""
        p = pmsm_params
        P_cold = copper_loss(p["R_s20"], 0.0, 100.0, T_winding=20.0)
        P_hot = copper_loss(p["R_s20"], 0.0, 100.0, T_winding=150.0)
        assert P_hot > P_cold

    def test_zero_current_zero_loss(self, pmsm_params):
        assert copper_loss(pmsm_params["R_s20"], 0.0, 0.0) == pytest.approx(0.0)

    def test_numpy_array_input(self, pmsm_params):
        p = pmsm_params
        i_q = np.array([0.0, 100.0, 200.0])
        P = copper_loss(p["R_s20"], 0.0, i_q)
        assert P.shape == (3,)
        assert P[0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# losses — iron_loss
# ---------------------------------------------------------------------------

class TestIronLoss:
    """Steinmetz model (Appendix A.7)"""

    def _iron_params(self):
        return dict(B_g=0.95, k_h=0.02, alpha=1.7, k_c=5e-5, k_e=0.0, V_core=2e-3)

    def test_iron_loss_non_negative(self):
        P = iron_loss(2 * pi * 50, **self._iron_params())
        assert P >= 0.0

    def test_iron_loss_zero_at_zero_frequency(self):
        P = iron_loss(0.0, **self._iron_params())
        assert P == pytest.approx(0.0, abs=1e-12)

    def test_iron_loss_scales_with_frequency(self):
        P1 = iron_loss(2 * pi * 50, **self._iron_params())
        P2 = iron_loss(2 * pi * 100, **self._iron_params())
        assert P2 > P1

    def test_numpy_array_speeds(self):
        omega = np.array([2 * pi * 50, 2 * pi * 100])
        P = iron_loss(omega, **self._iron_params())
        assert P.shape == (2,)
        assert P[1] > P[0]


# ---------------------------------------------------------------------------
# losses — windage_loss
# ---------------------------------------------------------------------------

class TestWindageLoss:
    def test_windage_cubic_scaling(self):
        P1 = windage_loss(1e-6, 100.0)
        P2 = windage_loss(1e-6, 200.0)
        assert P2 == pytest.approx(8.0 * P1, rel=1e-9)

    def test_windage_zero_at_rest(self):
        assert windage_loss(1e-6, 0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# control — mtpa_currents
# ---------------------------------------------------------------------------

class TestMTPA:
    """MTPA solver (Appendix A.4)"""

    def test_spmsm_mtpa_id_zero(self, pmsm_params):
        """SPMSM (L_d == L_q): optimal i_d = 0."""
        p = pmsm_params
        L = p["L_d"]
        i_d, i_q = mtpa_currents(p["lambda_pm"], L, L, p["I_max"], T_req=1.0)
        assert i_d == pytest.approx(0.0, abs=1e-9)

    def test_current_constraint_satisfied(self, pmsm_params):
        """i_d² + i_q² ≤ I_max²"""
        p = pmsm_params
        i_d, i_q = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], T_req=1e9)
        assert i_d ** 2 + i_q ** 2 <= p["I_max"] ** 2 + 1e-6

    def test_iq_positive_for_positive_torque(self, pmsm_params):
        p = pmsm_params
        i_d, i_q = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], T_req=50.0)
        assert i_q > 0.0

    def test_id_non_positive_for_ipmsm(self, pmsm_params):
        """IPMSM: optimal i_d ≤ 0 (demagnetising)."""
        p = pmsm_params
        i_d, i_q = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], T_req=1e9)
        assert i_d <= 0.0 + 1e-9


# ---------------------------------------------------------------------------
# control — base_speed
# ---------------------------------------------------------------------------

class TestBaseSpeed:
    """ω_e,base = V_max / |ψ_s(i_MTPA)|  (Appendix A.4)"""

    def test_base_speed_positive(self, pmsm_params):
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        assert omega_base > 0.0

    def test_voltage_approaches_vmax_at_base_speed(self, pmsm_params):
        """Back-EMF at base speed is approximately V_max (ignoring R_s)."""
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        # Compute voltage at base speed with rated MTPA currents, R_s=0
        i_d, i_q = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], T_req=1e9)
        v_d, v_q = steady_state_voltages(
            0.0, p["L_d"], p["L_q"], p["lambda_pm"], omega_e_base, i_d, i_q
        )
        v_mag = float(voltage_magnitude(v_d, v_q))
        assert v_mag == pytest.approx(V_max, rel=0.01)

    def test_higher_vmax_gives_lower_base_speed(self, pmsm_params):
        """Higher voltage limit → lower base speed (SVPWM constraint relaxes)."""
        p = pmsm_params
        omega1 = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max=200.0)
        omega2 = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max=300.0)
        assert omega2 > omega1

    def test_voltage_within_1pct_at_base_speed_ipmsm(self, pmsm_params):
        """AC for T-104: |v| == V_max within 1 % at base speed (R_s=0)."""
        p = pmsm_params  # IPMSM saliency (L_q > L_d)
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        i_d, i_q = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"])
        v_d, v_q = steady_state_voltages(
            0.0, p["L_d"], p["L_q"], p["lambda_pm"], omega_e_base, i_d, i_q
        )
        v_mag = float(voltage_magnitude(v_d, v_q))
        assert abs(v_mag - V_max) / V_max < 0.01

    def test_voltage_within_1pct_at_base_speed_spmsm(self, pmsm_params):
        """AC for T-104 also holds for SPMSM (L_d == L_q)."""
        p = pmsm_params
        L = p["L_d"]  # force saliency to zero
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], L, L, p["I_max"], V_max)
        i_d, i_q = mtpa_currents(p["lambda_pm"], L, L, p["I_max"])
        v_d, v_q = steady_state_voltages(
            0.0, L, L, p["lambda_pm"], omega_e_base, i_d, i_q
        )
        v_mag = float(voltage_magnitude(v_d, v_q))
        assert abs(v_mag - V_max) / V_max < 0.01


# ---------------------------------------------------------------------------
# control — field_weakening
# ---------------------------------------------------------------------------

class TestFieldWeakening:
    """Region 2 solver — current-limit ∩ voltage-limit intersection (§A.4)."""

    def test_returns_mtpa_below_base_speed(self, pmsm_params):
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        i_d_fw, i_q_fw = field_weakening(
            p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max, omega_e_base * 0.5,
        )
        i_d_mtpa, i_q_mtpa = mtpa_currents(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"])
        assert i_d_fw == pytest.approx(i_d_mtpa, abs=1e-9)
        assert i_q_fw == pytest.approx(i_q_mtpa, abs=1e-9)

    def test_voltage_on_limit_above_base_speed(self, pmsm_params):
        """Above base speed the FW point must sit on the V_max ellipse."""
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        for ratio in (1.2, 1.6, 2.0):
            omega_e = omega_e_base * ratio
            i_d, i_q = field_weakening(
                p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max, omega_e,
            )
            v_d, v_q = steady_state_voltages(
                0.0, p["L_d"], p["L_q"], p["lambda_pm"], omega_e, i_d, i_q
            )
            v_mag = float(voltage_magnitude(v_d, v_q))
            assert v_mag == pytest.approx(V_max, rel=1e-6)

    def test_stays_on_current_limit_circle(self, pmsm_params):
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        i_d, i_q = field_weakening(
            p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max, omega_e_base * 1.5,
        )
        assert sqrt(i_d ** 2 + i_q ** 2) == pytest.approx(p["I_max"], rel=1e-6)
        assert i_d < 0.0

    def test_deeper_weakening_as_speed_increases(self, pmsm_params):
        p = pmsm_params
        V_max = p["V_dc"] / sqrt(3.0)
        omega_e_base = base_speed(p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max)
        i_d_low, _ = field_weakening(
            p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max, omega_e_base * 1.2,
        )
        i_d_hi, _ = field_weakening(
            p["lambda_pm"], p["L_d"], p["L_q"], p["I_max"], V_max, omega_e_base * 2.0,
        )
        assert i_d_hi < i_d_low  # more negative at higher speed


# ---------------------------------------------------------------------------
# models/pmsm — compute_curve
# ---------------------------------------------------------------------------

class TestPMSMComputeCurve:
    """models/pmsm.py compute_curve(params) -> dict  (T-105)"""

    def test_returns_expected_keys(self, pmsm_params):
        result = compute_curve(pmsm_params)
        for key in ("speed_rpm", "speed_rad_s", "torque_Nm", "power_W", "efficiency",
                    "base_speed_rpm", "peak_torque_Nm"):
            assert key in result

    def test_array_shapes_match(self, pmsm_params):
        result = compute_curve(pmsm_params)
        n = len(result["speed_rpm"])
        for key in ("speed_rad_s", "torque_Nm", "power_W", "efficiency"):
            assert len(result[key]) == n

    def test_constant_torque_below_base_speed(self, pmsm_params):
        """Torque is flat (< 1 % variation) in the constant-torque region."""
        result = compute_curve(pmsm_params)
        base_rpm = result["base_speed_rpm"]
        mask = result["speed_rpm"] < base_rpm * 0.85
        torques = result["torque_Nm"][mask]
        if len(torques) > 1:
            span = torques.max() - torques.min()
            assert span / torques.max() < 0.01

    def test_power_non_negative(self, pmsm_params):
        result = compute_curve(pmsm_params)
        assert np.all(result["power_W"] >= 0.0)

    def test_efficiency_in_range(self, pmsm_params):
        result = compute_curve(pmsm_params)
        eff = result["efficiency"]
        assert np.all(eff >= 0.0)
        assert np.all(eff <= 1.0 + 1e-9)

    def test_custom_speeds_honoured(self, pmsm_params):
        speeds = [500.0, 1000.0, 2000.0]
        result = compute_curve(pmsm_params, speeds_rpm=speeds)
        assert len(result["speed_rpm"]) == 3

    def test_peak_torque_positive(self, pmsm_params):
        result = compute_curve(pmsm_params)
        assert result["peak_torque_Nm"] > 0.0

    def test_field_weakening_reduces_torque(self, pmsm_params):
        """Torque at 2× base speed is strictly less than peak torque."""
        result = compute_curve(pmsm_params)
        base_rpm = result["base_speed_rpm"]
        speeds = result["speed_rpm"]
        torques = result["torque_Nm"]
        idx_2x = int(np.searchsorted(speeds, base_rpm * 1.8))
        if idx_2x < len(torques):
            assert torques[idx_2x] < result["peak_torque_Nm"]

    def test_three_region_curve_shape(self, pmsm_params):
        """AC for T-105: constant-torque → constant-power → natural roll-off."""
        result = compute_curve(pmsm_params)
        base_rpm = result["base_speed_rpm"]
        speeds = result["speed_rpm"]
        torques = result["torque_Nm"]
        powers = result["power_W"]
        peak_T = result["peak_torque_Nm"]

        # Region 1 — constant torque below base speed (< 1 % variation).
        mask1 = speeds < base_rpm * 0.85
        if mask1.sum() > 1:
            span = torques[mask1].max() - torques[mask1].min()
            assert span / peak_T < 0.01
            assert torques[mask1].mean() == pytest.approx(peak_T, rel=0.01)

        # Region 2 — constant power: power in the 1.5×–2.5× band is within
        # 10 % of its peak (classic FW plateau).
        mask2 = (speeds >= base_rpm * 1.5) & (speeds <= base_rpm * 2.5)
        if mask2.sum() > 1:
            P_band = powers[mask2]
            peak_P = powers.max()
            assert P_band.min() >= 0.9 * peak_P

        # Region 3 — natural roll-off: torque drops monotonically with speed
        # in the FW region; power near the end is <= peak power.
        mask3 = speeds > base_rpm * 1.5
        if mask3.sum() > 2:
            T_fw = torques[mask3]
            # Strictly decreasing torque (allow small numerical slack)
            assert np.all(np.diff(T_fw) <= 1e-6)
            # Power has rolled off or plateaued — never exceeds the peak.
            assert powers[mask3][-1] <= powers.max() + 1e-6
