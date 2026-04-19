"""MTPA, base-speed, and field-weakening solvers for PMSM/AFPM (BRIEF §A.4).

Three operating regions are covered:

* **Region 1 (MTPA)** — below base speed, use the current that maximises
  torque per ampere.  SPMSM/AFPM collapses to ``i_d = 0, i_q = I_max``.
  IPMSM has a closed-form from BRIEF §A.4.
* **Base speed** — the electrical speed at which the back-EMF reaches
  ``V_max`` while running at MTPA currents.
* **Region 2 (Field Weakening)** — above base speed, ``i_d`` is driven
  negative along the current-limit circle to keep the voltage at
  ``V_max``.  The intersection with the voltage ellipse is solved with
  ``scipy.optimize.brentq``.

All functions operate on scalar floats.  Stator resistance is neglected
(BRIEF §A.4 standard approximation); the solvers therefore only need the
magnetic parameters and the DC-link-limited phase voltage ``V_max``.
"""

from __future__ import annotations

from math import sqrt
from typing import Tuple

from scipy.optimize import brentq


def mtpa_currents(
    lambda_pm: float,
    L_d: float,
    L_q: float,
    I_max: float,
    T_req: float | None = None,
) -> Tuple[float, float]:
    """MTPA (maximum-torque-per-ampere) currents (BRIEF §A.4 Region 1).

    For SPMSM/AFPM (``L_d == L_q``) the optimum is ``i_d = 0, i_q = I_max``.
    For IPMSM (``L_q > L_d``) the closed form is::

        i_d = [λ_pm − √(λ_pm² + 8·(L_q − L_d)² · I_max²)] / [4·(L_q − L_d)]
        i_q = √(I_max² − i_d²)

    If ``T_req`` is given and smaller than the full-current torque, the
    result is scaled along the MTPA ray so that ``i_d² + i_q² ≤ I_max²``.
    When ``T_req`` is *None* (or very large), the full-current MTPA point
    is returned — this is the operating point used to compute base speed.

    Returns ``(i_d, i_q)`` with ``i_d ≤ 0``.
    """
    saliency = L_q - L_d

    if abs(saliency) < 1e-12:
        i_d_full, i_q_full = 0.0, I_max
    else:
        discr = lambda_pm ** 2 + 8.0 * saliency ** 2 * I_max ** 2
        i_d_full = (lambda_pm - sqrt(discr)) / (4.0 * saliency)
        i_q_full = sqrt(max(I_max ** 2 - i_d_full ** 2, 0.0))

    if T_req is None:
        return i_d_full, i_q_full

    # Scale linearly along the MTPA ray for partial load (exact for SPMSM,
    # approximate for IPMSM; acceptable for torque-request sweeps).
    # T_full assumes unit p since callers scale torque themselves.
    T_full = lambda_pm * i_q_full + saliency * i_d_full * i_q_full
    if T_full <= 0.0:
        return i_d_full, i_q_full
    scale = min(abs(T_req) / T_full, 1.0)
    sign = 1.0 if T_req >= 0.0 else -1.0
    return i_d_full * scale, sign * i_q_full * scale


def base_speed(
    lambda_pm: float,
    L_d: float,
    L_q: float,
    I_max: float,
    V_max: float,
) -> float:
    """Electrical base speed [rad/s] (BRIEF §A.4)::

        ω_e,base = V_max / √( (L_q·i_q,MTPA)² + (λ_pm + L_d·i_d,MTPA)² )

    Stator resistance is neglected (standard approximation).
    """
    i_d, i_q = mtpa_currents(lambda_pm, L_d, L_q, I_max, T_req=None)
    psi_d = lambda_pm + L_d * i_d
    psi_q = L_q * i_q
    psi_mag = sqrt(psi_d ** 2 + psi_q ** 2)
    return V_max / psi_mag


def field_weakening(
    lambda_pm: float,
    L_d: float,
    L_q: float,
    I_max: float,
    V_max: float,
    omega_e: float,
) -> Tuple[float, float]:
    """Field-weakening operating point (BRIEF §A.4 Region 2).

    Finds ``(i_d, i_q)`` on the current-limit circle
    ``i_d² + i_q² = I_max²`` that also satisfies the voltage-limit ellipse
    ``(L_q·i_q)² + (λ_pm + L_d·i_d)² = (V_max/ω_e)²`` (R_s neglected).

    Uses ``scipy.optimize.brentq`` on the residual

        g(i_d) = (L_q·√(I_max² − i_d²))² + (λ_pm + L_d·i_d)² − (V_max/ω_e)²

    over ``i_d ∈ [−I_max, 0]``.  Below base speed there is no real root,
    so the MTPA point is returned instead.  If the voltage ellipse sits
    entirely inside the current-limit circle (very high speed / weak PM)
    the routine returns the point of minimum flux on the current circle,
    ``i_d = max(−I_max, −λ_pm/L_d)``.
    """
    if omega_e <= 0.0:
        return mtpa_currents(lambda_pm, L_d, L_q, I_max, T_req=None)

    psi_target = V_max / omega_e  # desired stator flux magnitude

    def g(i_d: float) -> float:
        i_q_sq = max(I_max ** 2 - i_d ** 2, 0.0)
        return (L_q ** 2) * i_q_sq + (lambda_pm + L_d * i_d) ** 2 - psi_target ** 2

    g_hi = g(0.0)  # i_d = 0 (MTPA for SPMSM)
    if g_hi <= 0.0:
        # Voltage at MTPA already ≤ V_max: no weakening needed.
        return mtpa_currents(lambda_pm, L_d, L_q, I_max, T_req=None)

    g_lo = g(-I_max)
    if g_lo > 0.0:
        # Current circle never reaches the voltage ellipse at this speed.
        # Fall back to the i_d that minimises stator flux on the circle:
        # ψ_d = λ_pm + L_d·i_d = 0 → i_d = −λ_pm/L_d (centre of the voltage
        # ellipse projected onto the current axis), clamped to −I_max.
        i_d = max(-I_max, -lambda_pm / L_d) if L_d > 0.0 else -I_max
        i_q = sqrt(max(I_max ** 2 - i_d ** 2, 0.0))
        return i_d, i_q

    i_d = brentq(g, -I_max, 0.0, xtol=1e-10, rtol=1e-12, maxiter=200)
    i_q = sqrt(max(I_max ** 2 - i_d ** 2, 0.0))
    return i_d, i_q
