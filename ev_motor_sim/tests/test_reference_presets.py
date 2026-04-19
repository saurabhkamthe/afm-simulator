"""Reference-preset validation tests (T-503).

Asserts Appendix B numbers within ±15% for all three reference motors.
Stubs — requires models/ implementation and preset JSON files (T-107).
"""
import pytest


TOLERANCE = 0.15  # ±15%

REFERENCE_TARGETS = {
    "tesla_model3": {
        "peak_torque_Nm": 420.0,
        "base_speed_rpm": 6000.0,
        "peak_power_kW": 211.0,
        "peak_efficiency": 0.97,
    },
    "yasa_750r": {
        "peak_torque_Nm": 790.0,
        "base_speed_rpm": 3250.0,
        "peak_power_kW": 200.0,
        "peak_efficiency": 0.95,
    },
    "generic_60kw": {
        "peak_torque_Nm": 150.0,
        "base_speed_rpm": 4000.0,
        "peak_power_kW": 60.0,
        "peak_efficiency": 0.94,
    },
}


def _within_tolerance(actual: float, target: float, tol: float = TOLERANCE) -> bool:
    return abs(actual - target) / target <= tol


@pytest.mark.validation
@pytest.mark.parametrize("preset_name,targets", REFERENCE_TARGETS.items())
class TestReferencePresets:
    def test_peak_torque(self, preset_name, targets):
        pytest.skip("Requires models/ implementation and preset JSONs (T-105, T-106, T-107)")

    def test_base_speed(self, preset_name, targets):
        pytest.skip("Requires models/ implementation and preset JSONs (T-105, T-106, T-107)")

    def test_peak_power(self, preset_name, targets):
        pytest.skip("Requires models/ implementation and preset JSONs (T-105, T-106, T-107)")

    def test_peak_efficiency(self, preset_name, targets):
        pytest.skip("Requires models/ implementation and preset JSONs (T-105, T-106, T-107)")
