"""MotorParams schema tests (T-101 AC).

Covers the T-101 acceptance criterion: the schema validates the 3 reference
presets without errors. Physics-accurate validation against Appendix B
targets lives in ``test_reference_presets.py`` (T-503).
"""

from __future__ import annotations

import json
from importlib.resources import files
from math import isclose, sqrt

import pytest
from pydantic import ValidationError

from ev_motor_sim.models.params import MotorParams, RotorSaliency, Topology


PRESET_FILES = ("tesla_model3.json", "yasa_750r.json", "generic_60kw.json")


def _preset_path(name: str):
    return files("ev_motor_sim.presets").joinpath(name)


# ---------------------------------------------------------------------------
# T-101 AC: schema validates the 3 reference presets without errors.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fname", PRESET_FILES)
def test_preset_file_schema_validates(fname: str) -> None:
    text = _preset_path(fname).read_text()
    params = MotorParams.model_validate_json(text)
    assert params.name
    # Every range-bounded field should survive model_dump round-trip.
    assert MotorParams.model_validate(params.model_dump()) == params


@pytest.mark.parametrize("fname", PRESET_FILES)
def test_preset_from_file_helper(fname: str, tmp_path) -> None:
    # Copy preset out of the package so ``MotorParams.from_file`` exercises
    # the disk path (not just the in-memory traversable).
    target = tmp_path / fname
    target.write_text(_preset_path(fname).read_text())
    params = MotorParams.from_file(target)
    assert isinstance(params, MotorParams)


def test_preset_round_trip_is_identical(tmp_path) -> None:
    """T-401 forward-compat: model_dump_json round-trips without drift."""
    params = MotorParams.from_file(_preset_path("generic_60kw.json"))
    out = tmp_path / "out.json"
    params.to_file(out)
    reloaded = MotorParams.from_file(out)
    assert reloaded == params


# ---------------------------------------------------------------------------
# Defaults + enums + computed helpers
# ---------------------------------------------------------------------------

def test_defaults_are_valid() -> None:
    params = MotorParams()
    assert params.topology is Topology.RADIAL_PMSM
    assert params.saliency is RotorSaliency.SURFACE
    assert params.V_dc == pytest.approx(400.0)


def test_V_max_uses_svpwm_bound() -> None:
    params = MotorParams(V_dc=600.0)
    assert isclose(params.V_max, 600.0 / sqrt(3.0))


def test_R_s_temperature_scaling() -> None:
    params = MotorParams(R_s_20=0.010, T_winding=20.0)
    assert isclose(params.R_s(), 0.010, rel_tol=1e-9)
    # +100 °C above reference → +39.3 % resistance.
    assert isclose(params.R_s(120.0), 0.010 * (1.0 + 0.00393 * 100.0), rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def test_axial_requires_D_o_gt_D_i() -> None:
    with pytest.raises(ValidationError):
        MotorParams(topology=Topology.AXIAL_FLUX_PM, D_o=0.20, D_i=0.25)


def test_radial_does_not_enforce_D_o_gt_D_i() -> None:
    # Radial presets may leave the axial-disc fields at any valid numeric value.
    params = MotorParams(topology=Topology.RADIAL_PMSM, D_o=0.20, D_i=0.25)
    assert params.D_o == pytest.approx(0.20)


def test_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        MotorParams(V_dc=5.0)  # below 24 V floor
    with pytest.raises(ValidationError):
        MotorParams(p=0)  # pole pairs must be >= 1


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        MotorParams.model_validate({"name": "x", "not_a_real_field": 42})


def test_surface_with_salient_inductances_warns() -> None:
    with pytest.warns(UserWarning):
        MotorParams(
            saliency=RotorSaliency.SURFACE,
            L_d=2.0e-4,
            L_q=5.0e-4,
        )


def test_validate_assignment_enforces_ranges() -> None:
    params = MotorParams()
    with pytest.raises(ValidationError):
        params.V_dc = 5.0  # below floor, must be caught on assignment


def test_presets_are_valid_json_documents() -> None:
    for fname in PRESET_FILES:
        # Sanity: files parse as JSON before we even ask pydantic.
        json.loads(_preset_path(fname).read_text())
