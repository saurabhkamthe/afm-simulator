"""Tests for axial-flux PMSM physics (T-502).

Stubs — will be filled in once physics/ modules are implemented (T-102 to T-106).
"""
import pytest


class TestAFPMSizing:
    """Axial-flux sizing equations (Appendix A.5)"""

    def test_torque_density_higher_than_radial(self, afpm_params, pmsm_params):
        """At same D_o, AFPM produces higher torque density than PMSM."""
        pytest.skip("Requires models/afpm.py (T-106)")

    def test_lambda_pm_positive(self, afpm_params):
        pytest.skip("Requires models/afpm.py (T-106)")

    def test_inductance_positive(self, afpm_params):
        pytest.skip("Requires models/afpm.py (T-106)")


class TestAFPMComputeCurve:
    """models/afpm.py compute_curve(speeds) -> dict  (T-106)"""

    def test_returns_expected_keys(self, afpm_params):
        pytest.skip("Requires models/afpm.py (T-106)")

    def test_efficiency_in_range(self, afpm_params):
        """η ∈ (0, 1] at all operating points."""
        pytest.skip("Requires models/afpm.py (T-106)")
