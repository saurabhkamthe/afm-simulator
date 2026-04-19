from __future__ import annotations

from importlib.resources import files

from ev_motor_sim.models.params import MotorParams

_BUILTIN_FILES = ("tesla_model3.json", "yasa_750r.json", "generic_60kw.json")


def list_builtins() -> list[tuple[str, str]]:
    """Return [(display_name, filename), ...] for each bundled preset."""
    result = []
    for fname in _BUILTIN_FILES:
        text = files("ev_motor_sim.presets").joinpath(fname).read_text()
        params = MotorParams.model_validate_json(text)
        result.append((params.name, fname))
    return result


def load_builtin(filename: str) -> MotorParams:
    """Load a bundled preset by its JSON filename."""
    text = files("ev_motor_sim.presets").joinpath(filename).read_text()
    return MotorParams.model_validate_json(text)
