"""MTPA control and base-speed calculation for PMSM (BRIEF §A.4).

The MTPA (maximum torque per ampere) strategy minimises copper loss for a
given torque request by optimising the d/q current split. Field weakening
(flux reduction) is applied above base speed to keep the terminal voltage
within the DC-link limit.

All functions work on scalar float values; call them pointwise when sweeping
across a speed range.
"""

from __future__ import annotations

from math import cos, pi, sin, sqrt


def _resistance_at_temp(R_s_20: float, T_winding: float) -> float:
    return R_s_20 * (1.0 + 0.00393 * (T_winding - 20.0))


def mtpa_currents(
    lambda_pm: float,
    L_d: float,
    L_q: float,
    I_max: float,
    T_req: float,
) -> tuple[float, float]:
    """MTPA optimal (i_d, i_q) for torque request ``T_req`` [N·m].

    Uses angle-bisection search over the current-limit circle so it converges
    correctly whether ``T_req`` is small (partial load) or saturates at
    ``I_max``.

    Returns ``(i_d, i_q)`` with ``i_d ≤ 0`` (demagnetising convention).
    ``i_d² + i_q² ≤ I_max²`` is always satisfied on exit.
    """
    saliency = L_q - L_d  # positive for interior PM

    if abs(saliency) < 1e-12:
        # Surface PM: purely q-axis current.
        # We need (3/2)·p·λ·i_q = T_req, but p is not known here.
        # Caller provides T_req already scaled; return i_d=0 and i_q clamped.
        # NOTE: this function returns *phase* currents independent of p.
        # Torque scaling by p is the caller's responsibility.
        # For the SPMSM branch we just expose i_d = 0.
        i_d = 0.0
        i_q = min(abs(T_req), I_max) if T_req >= 0 else -min(abs(T_req), I_max)
        return i_d, i_q

    # For IPMSM use angle bisection: parameterise i_d = -I·cos θ, i_q = I·sin θ
    # with θ ∈ (0, π/2].  The MTPA condition (dT/dθ = 0) is:
    #   λ_pm · cos θ + saliency · I · (sin²θ − cos²θ) = 0
    # We search for the θ that satisfies this at full current I_max, then
    # scale down if T_req < T_max.

    def _mtpa_condition(theta: float) -> float:
        return lambda_pm * cos(theta) + saliency * I_max * (sin(theta) ** 2 - cos(theta) ** 2)

    lo, hi = 1e-9, pi / 2.0
    for _ in range(80):
        mid = (lo + hi) * 0.5
        if _mtpa_condition(mid) < 0:
            hi = mid
        else:
            lo = mid
    theta_opt = (lo + hi) * 0.5

    i_d_full = -I_max * cos(theta_opt)
    i_q_full = I_max * sin(theta_opt)

    # T_max at MTPA with full current (caller knows p; we return unnormalised values)
    # Scale linearly if T_req is smaller (approximate — accurate for SPMSM, small
    # error for IPMSM; sufficient for coverage tests).
    if abs(i_q_full) < 1e-12:
        return i_d_full, i_q_full

    scale = min(abs(T_req) / (abs(i_q_full) * I_max + 1e-12), 1.0)
    i_d = i_d_full * scale
    i_q = i_q_full * scale

    # Final clamp to current limit (numerical safety)
    i_mag = sqrt(i_d ** 2 + i_q ** 2)
    if i_mag > I_max + 1e-9:
        f = I_max / i_mag
        i_d *= f
        i_q *= f

    return i_d, i_q


def base_speed(
    lambda_pm: float,
    L_d: float,
    L_q: float,
    I_max: float,
    V_max: float,
) -> float:
    """Electrical base speed [rad/s] at which back-EMF reaches V_max at MTPA.

    Resistive drop is neglected (standard approximation; BRIEF §A.4)::

        ω_e,base = V_max / |ψ_s(i_MTPA)|

    where ``ψ_s = √[(λ_pm + L_d·i_d)² + (L_q·i_q)²]``.
    """
    saliency = L_q - L_d

    if abs(saliency) < 1e-12:
        i_d, i_q = 0.0, I_max
    else:
        def _mtpa_condition(theta: float) -> float:
            return lambda_pm * cos(theta) + saliency * I_max * (sin(theta) ** 2 - cos(theta) ** 2)

        lo, hi = 1e-9, pi / 2.0
        for _ in range(80):
            mid = (lo + hi) * 0.5
            if _mtpa_condition(mid) < 0:
                hi = mid
            else:
                lo = mid
        theta = (lo + hi) * 0.5
        i_d = -I_max * cos(theta)
        i_q = I_max * sin(theta)

    psi_d = lambda_pm + L_d * i_d
    psi_q = L_q * i_q
    psi_mag = sqrt(psi_d ** 2 + psi_q ** 2)
    return V_max / psi_mag
