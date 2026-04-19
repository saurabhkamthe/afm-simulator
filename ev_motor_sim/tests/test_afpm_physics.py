"""Per-function tests for axial-flux PM physics (T-502).

Validates physics/ functions and models/afpm.py using the ``afpm_params``
fixture from conftest.py.
"""

from math import sqrt

import numpy as np
import pytest

from ev_motor_sim.models.afpm import afpm_sizing, compute_curve
from ev_motor_sim.physics.dq_frame import electromagnetic_torque


class TestAFPMSizing:
    """Axial-flux sizing equations (Appendix A.5)"""

    def test_lambda_pm_positive(self, afpm_params):
        sizing = afpm_sizing(afpm_params)
        assert sizing["lambda_pm"] > 0.0

    def test_inductance_positive(self, afpm_params):
        sizing = afpm_sizing(afpm_params)
        assert sizing["L_d"] > 0.0
        assert sizing["L_q"] > 0.0

    def test_sizing_returns_required_keys(self, afpm_params):
        sizing = afpm_sizing(afpm_params)
        assert "lambda_pm" in sizing
        assert "L_d" in sizing
        assert "L_q" in sizing

    def test_torque_density_higher_than_radial(self, afpm_params, pmsm_params):
        """AFPM uses a larger outer diameter and higher I_max than the reference
        PMSM fixture → peak torque normalised by D_o^2 should be at least
        comparable (depends on λ_pm and I_max values chosen in fixtures)."""
        # Peak electromagnetic torque for each topology
        a = afpm_params
        T_afpm = electromagnetic_torque(a["p"], a["lambda_pm"], a["L_d"], a["L_q"],
                                        0.0, a["I_max"])
        # Use PMSM D_o ≈ rotor diameter; fixture has no D_o, use a comparable value
        p = pmsm_params
        T_pmsm = electromagnetic_torque(p["p"], p["lambda_pm"], p["L_d"], p["L_q"],
                                        0.0, p["I_max"])
        # Normalise by the same outer diameter (AFPM D_o) so the comparison is
        # "at same envelope diameter, AFPM wins".  PMSM fixture does not carry
        # a D_o; we use the AFPM machine's D_o = 0.35 m for both.
        D_o = a["D_o"]
        density_afpm = T_afpm / D_o ** 3
        density_pmsm = T_pmsm / D_o ** 3
        assert density_afpm > density_pmsm


class TestAFPMComputeCurve:
    """models/afpm.py compute_curve(params) -> dict  (T-106)"""

    def test_returns_expected_keys(self, afpm_params):
        result = compute_curve(afpm_params)
        for key in ("speed_rpm", "speed_rad_s", "torque_Nm", "power_W", "efficiency",
                    "base_speed_rpm", "peak_torque_Nm"):
            assert key in result

    def test_efficiency_in_range(self, afpm_params):
        """η ∈ [0, 1] at all operating points."""
        result = compute_curve(afpm_params)
        eff = result["efficiency"]
        assert np.all(eff >= 0.0)
        assert np.all(eff <= 1.0 + 1e-9)

    def test_power_non_negative(self, afpm_params):
        result = compute_curve(afpm_params)
        assert np.all(result["power_W"] >= 0.0)

    def test_base_speed_rpm_positive(self, afpm_params):
        result = compute_curve(afpm_params)
        assert result["base_speed_rpm"] > 0.0

    def test_peak_torque_positive(self, afpm_params):
        result = compute_curve(afpm_params)
        assert result["peak_torque_Nm"] > 0.0

    def test_custom_speeds(self, afpm_params):
        speeds = [300.0, 600.0, 1200.0]
        result = compute_curve(afpm_params, speeds_rpm=speeds)
        assert len(result["speed_rpm"]) == 3

    def test_torque_decreases_in_field_weakening(self, afpm_params):
        result = compute_curve(afpm_params)
        base_rpm = result["base_speed_rpm"]
        speeds = result["speed_rpm"]
        torques = result["torque_Nm"]
        idx_2x = int(np.searchsorted(speeds, base_rpm * 1.8))
        if idx_2x < len(torques):
            assert torques[idx_2x] < result["peak_torque_Nm"]
