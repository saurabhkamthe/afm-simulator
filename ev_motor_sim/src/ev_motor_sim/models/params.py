"""MotorParams schema (T-101, G1 plan §3).

Single flat pydantic v2 model covering geometry, electrical, material, and
limit fields for both Radial PMSM and Axial Flux PM topologies. All numeric
fields carry physical units (documented on each ``Field``) and ranges derived
from the BRIEF physical envelope.

Source of truth: EVM-2 plan document §3.
"""

from __future__ import annotations

import warnings
from enum import Enum
from math import sqrt
from pathlib import Path
from typing import Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Topology(str, Enum):
    RADIAL_PMSM = "radial_pmsm"
    AXIAL_FLUX_PM = "axial_flux_pm"


class RotorSaliency(str, Enum):
    SURFACE = "surface"
    INTERIOR = "interior"


PathLike = Union[str, Path]


class MotorParams(BaseModel):
    """Parameters for a single motor, applicable to both topologies.

    See G1 plan §3 on EVM-2 for field-by-field rationale and ranges.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
    )

    # --- Meta ---
    name: str = Field(
        default="Custom motor",
        min_length=1,
        max_length=80,
        description="Human-readable preset name.",
    )
    topology: Topology = Field(
        default=Topology.RADIAL_PMSM,
        description="Motor topology (radial PMSM or axial-flux PM).",
    )
    saliency: RotorSaliency = Field(
        default=RotorSaliency.SURFACE,
        description="Rotor saliency (surface-mounted vs interior PM).",
    )

    # --- Geometry (radial) ---
    D_ro: float = Field(
        default=0.16, ge=0.03, le=0.4,
        description="Rotor outer diameter [m] (radial topology).",
    )
    L_stk: float = Field(
        default=0.10, ge=0.02, le=0.5,
        description="Stator stack length [m] (radial topology).",
    )

    # --- Geometry (axial) ---
    D_o: float = Field(
        default=0.30, ge=0.08, le=0.6,
        description="Disc outer diameter [m] (axial topology).",
    )
    D_i: float = Field(
        default=0.16, ge=0.02, le=0.5,
        description="Disc inner diameter [m] (axial topology).",
    )
    g_mech: float = Field(
        default=1.0e-3, ge=0.2e-3, le=3.0e-3,
        description="Mechanical air-gap [m] (axial topology).",
    )
    l_pm: float = Field(
        default=6.0e-3, ge=1.0e-3, le=20.0e-3,
        description="Permanent-magnet axial thickness [m] (axial topology).",
    )
    mu_r: float = Field(
        default=1.05, ge=1.0, le=1.2,
        description="PM relative recoil permeability [-].",
    )

    # --- Electrical ---
    p: int = Field(
        default=4, ge=1, le=20,
        description="Number of pole pairs.",
    )
    N_turns: int = Field(
        default=10, ge=1, le=500,
        description="Turns per coil.",
    )
    k_w: float = Field(
        default=0.93, ge=0.80, le=0.98,
        description="Fundamental winding factor [-].",
    )
    R_s_20: float = Field(
        default=0.015, ge=1.0e-4, le=2.0,
        description="Stator phase resistance at 20 °C [Ω].",
    )
    L_d: float = Field(
        default=2.0e-4, ge=1.0e-6, le=1.0e-2,
        description="d-axis synchronous inductance [H].",
    )
    L_q: float = Field(
        default=2.0e-4, ge=1.0e-6, le=1.0e-2,
        description="q-axis synchronous inductance [H].",
    )
    lambda_pm: float = Field(
        default=0.12, ge=1.0e-3, le=1.0,
        description="Permanent-magnet flux linkage (peak) [Wb].",
    )

    # --- Material / loss ---
    B_g: float = Field(
        default=0.95, ge=0.5, le=1.2,
        description="Peak air-gap flux density [T].",
    )
    A_s: float = Field(
        default=4.5e4, ge=1.0e4, le=1.0e5,
        description="Stator electrical loading [A/m].",
    )
    k_h: float = Field(
        default=0.02, ge=0.005, le=0.1,
        description="Steinmetz hysteresis coefficient [-].",
    )
    alpha: float = Field(
        default=1.7, ge=1.4, le=2.0,
        description="Steinmetz flux-density exponent [-].",
    )
    k_c: float = Field(
        default=5.0e-5, ge=1.0e-6, le=1.0e-3,
        description="Classical eddy-current coefficient [-].",
    )
    k_e: float = Field(
        default=0.0, ge=0.0, le=1.0e-3,
        description="Excess (anomalous) loss coefficient [-].",
    )
    V_core: float = Field(
        default=2.0e-3, ge=1.0e-5, le=1.0e-1,
        description="Effective iron-core volume [m³].",
    )
    T_winding: float = Field(
        default=80.0, ge=-20.0, le=180.0,
        description="Winding temperature [°C] (for R_s temperature scaling).",
    )

    # --- Limits ---
    V_dc: float = Field(
        default=400.0, ge=24.0, le=1000.0,
        description="DC-bus voltage [V].",
    )
    I_max: float = Field(
        default=400.0, ge=10.0, le=2000.0,
        description="Peak phase current limit [A].",
    )
    T_fric: float = Field(
        default=0.1, ge=0.0, le=5.0,
        description="Dry-friction torque [N·m].",
    )
    k_windage: float = Field(
        default=1.0e-6, ge=0.0, le=1.0e-3,
        description="Windage coefficient [N·m·s³/rad³].",
    )

    # --- Cross-field validators ---
    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "MotorParams":
        # Axial topology requires D_o strictly greater than D_i (BRIEF §A.3).
        if self.topology is Topology.AXIAL_FLUX_PM and not (self.D_o > self.D_i):
            raise ValueError(
                f"Axial topology requires D_o > D_i "
                f"(got D_o={self.D_o}, D_i={self.D_i})."
            )
        # Surface-PM implies L_d ≈ L_q; interior-PM implies L_d < L_q.
        # We warn rather than error so IPMSM presets with numerical near-ties
        # don't blow up at load time.
        if self.saliency is RotorSaliency.SURFACE and self.L_d != self.L_q:
            warnings.warn(
                f"saliency=SURFACE expects L_d == L_q (got L_d={self.L_d}, "
                f"L_q={self.L_q}).",
                UserWarning,
                stacklevel=2,
            )
        return self

    # --- Computed properties / helpers ---
    @property
    def V_max(self) -> float:
        """Peak phase voltage limit under SVPWM: V_dc / √3 (BRIEF §A.1)."""
        return self.V_dc / sqrt(3.0)

    def R_s(self, T_c: Union[float, None] = None) -> float:
        """Stator resistance at temperature ``T_c`` [°C].

        Uses standard copper temperature coefficient (≈ 0.00393 /°C).
        When ``T_c`` is None, falls back to ``self.T_winding``.
        """
        t = self.T_winding if T_c is None else T_c
        return self.R_s_20 * (1.0 + 0.00393 * (t - 20.0))

    # --- Serialization helpers (T-401 round-trip contract) ---
    @classmethod
    def from_file(cls, path: PathLike) -> "MotorParams":
        """Load a preset from a JSON file on disk."""
        return cls.model_validate_json(Path(path).read_text())

    def to_file(self, path: PathLike) -> None:
        """Write this preset to disk as indented JSON."""
        Path(path).write_text(self.model_dump_json(indent=2))
