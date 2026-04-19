"""Loss models for PMSM / AFPM (BRIEF §A.7).

Implements the four loss components the MVP efficiency map needs:

* copper (Joule) loss with temperature-scaled stator resistance
* iron (core) loss via the three-term Steinmetz model
* mechanical loss (friction + windage)
* stray loss (lumped as a fraction of input power)

All functions accept scalars or numpy arrays and return values in watts. The
formulas are the ones written out verbatim in BRIEF §A.7.
"""

from __future__ import annotations

from typing import Union

import numpy as np
from numpy.typing import ArrayLike

Number = Union[float, np.ndarray]

# Copper temperature coefficient [1/°C]. BRIEF §A.7.
_ALPHA_CU = 0.00393

# MVP stray-loss fraction of input power. BRIEF §A.7.
_DEFAULT_STRAY_FRACTION = 0.01


def copper_loss(
    R_s_20: float,
    i_d: ArrayLike,
    i_q: ArrayLike,
    T_winding: float = 80.0,
) -> Number:
    """Copper (Joule) loss in the stator windings.

    BRIEF §A.7::

        P_cu = (3/2) · R_s(T) · (i_d² + i_q²)
        R_s(T) = R_s,20 · [1 + α_Cu · (T − 20)]
    """
    R_s = R_s_20 * (1.0 + _ALPHA_CU * (T_winding - 20.0))
    i_d_arr = np.asarray(i_d, dtype=float)
    i_q_arr = np.asarray(i_q, dtype=float)
    return 1.5 * R_s * (i_d_arr ** 2 + i_q_arr ** 2)


def iron_loss(
    omega_e: ArrayLike,
    B_g: float,
    k_h: float = 0.02,
    alpha: float = 1.7,
    k_c: float = 5.0e-5,
    k_e: float = 0.0,
    V_core: float = 1.0,
) -> Number:
    """Steinmetz iron (core) loss.

    BRIEF §A.7::

        P_fe = V_core · [ k_h · f · B_m^α
                        + k_c · (f · B_m)²
                        + k_e · (f · B_m)^1.5 ]
        f    = ω_e / (2π)

    Defaults match the M19 / M270-35A values in the brief
    (``k_h≈0.02``, ``k_c≈5e-5``, ``α≈1.7``; ``k_e`` defaults to 0 because the
    excess-loss term is optional for the MVP map).
    """
    omega_arr = np.asarray(omega_e, dtype=float)
    f = omega_arr / (2.0 * np.pi)
    f_abs = np.abs(f)
    B_abs = abs(B_g)
    p_hyst = k_h * f_abs * (B_abs ** alpha)
    p_eddy = k_c * (f_abs * B_abs) ** 2
    p_excess = k_e * (f_abs * B_abs) ** 1.5
    return V_core * (p_hyst + p_eddy + p_excess)


def friction_loss(T_fric: float, omega_m: ArrayLike) -> Number:
    """Mechanical friction (bearing + seal) loss.

    ``P_fric = T_fric · |ω_m|``

    ``T_fric`` is the coulombic friction torque in Nm; ``omega_m`` is the
    mechanical speed in rad/s. The magnitude keeps the loss non-negative when
    the caller passes negative speeds (regenerating).
    """
    omega_arr = np.asarray(omega_m, dtype=float)
    return T_fric * np.abs(omega_arr)


def windage_loss(k_windage: float, omega_m: ArrayLike) -> Number:
    """Aerodynamic windage loss.

    ``P_w = k_windage · |ω_m|³``
    """
    omega_arr = np.asarray(omega_m, dtype=float)
    return k_windage * np.abs(omega_arr) ** 3


def mechanical_loss(
    T_fric: float,
    k_windage: float,
    omega_m: ArrayLike,
) -> Number:
    """Total mechanical loss = friction + windage.

    BRIEF §A.7::

        P_mech = T_fric · ω_m + k_w · ω_m³      (defaults T_fric=0.1 Nm, k_w=1e-6)
    """
    return friction_loss(T_fric, omega_m) + windage_loss(k_windage, omega_m)


def stray_loss(
    P_in: ArrayLike,
    fraction: float = _DEFAULT_STRAY_FRACTION,
) -> Number:
    """Stray / additional load loss, lumped as a fraction of input power.

    BRIEF §A.7::

        P_stray ≈ 0.01 · P_in     (MVP lump)
    """
    P_in_arr = np.asarray(P_in, dtype=float)
    return fraction * np.abs(P_in_arr)
