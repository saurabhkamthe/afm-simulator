"""dq-frame physics primitives (T-102).

Implements the electromagnetic torque equation (BRIEF §A.2) and the
steady-state d/q voltage equations (BRIEF §A.3).

SI units throughout. Currents ``i_d``, ``i_q`` are peak phase values; ``omega_e``
is electrical angular speed in rad/s. All functions are numpy-friendly: pass
scalars or arrays for currents/speeds and you will get a matching output.
"""

from __future__ import annotations

from typing import Tuple, Union

import numpy as np
from numpy.typing import ArrayLike

Number = Union[float, np.ndarray]


def electromagnetic_torque(
    p: int,
    lambda_pm: float,
    L_d: float,
    L_q: float,
    i_d: ArrayLike,
    i_q: ArrayLike,
) -> Number:
    """Electromagnetic torque in the dq frame.

    BRIEF §A.2::

        T_em = (3/2) · p · [ λ_pm · i_q + (L_d − L_q) · i_d · i_q ]

    The second term is the reluctance torque; for SPMSM / typical AFPM
    (``L_d ≈ L_q``) it vanishes.
    """
    i_d_arr = np.asarray(i_d, dtype=float)
    i_q_arr = np.asarray(i_q, dtype=float)
    return 1.5 * p * (lambda_pm * i_q_arr + (L_d - L_q) * i_d_arr * i_q_arr)


def steady_state_voltages(
    R_s: float,
    L_d: float,
    L_q: float,
    lambda_pm: float,
    omega_e: ArrayLike,
    i_d: ArrayLike,
    i_q: ArrayLike,
) -> Tuple[Number, Number]:
    """Steady-state dq-axis voltages.

    BRIEF §A.3::

        v_d = R_s · i_d − ω_e · L_q · i_q
        v_q = R_s · i_q + ω_e · L_d · i_d + ω_e · λ_pm
    """
    omega_arr = np.asarray(omega_e, dtype=float)
    i_d_arr = np.asarray(i_d, dtype=float)
    i_q_arr = np.asarray(i_q, dtype=float)
    v_d = R_s * i_d_arr - omega_arr * L_q * i_q_arr
    v_q = R_s * i_q_arr + omega_arr * L_d * i_d_arr + omega_arr * lambda_pm
    return v_d, v_q


def voltage_magnitude(v_d: ArrayLike, v_q: ArrayLike) -> Number:
    """Phase voltage magnitude ``√(v_d² + v_q²)`` (BRIEF §A.3 constraint)."""
    return np.hypot(np.asarray(v_d, dtype=float), np.asarray(v_q, dtype=float))


def current_magnitude(i_d: ArrayLike, i_q: ArrayLike) -> Number:
    """Phase current magnitude ``√(i_d² + i_q²)`` (BRIEF §A.3 constraint)."""
    return np.hypot(np.asarray(i_d, dtype=float), np.asarray(i_q, dtype=float))
