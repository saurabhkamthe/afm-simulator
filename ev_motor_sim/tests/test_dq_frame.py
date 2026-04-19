"""Unit tests for ``physics/dq_frame.py`` (T-102).

Covers the SPMSM case (``L_d ≈ L_q``, reluctance torque vanishes) and the
IPMSM case (``L_d < L_q``, nonzero reluctance contribution). Equations are
BRIEF §A.2 (torque) and §A.3 (steady-state voltages).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ev_motor_sim.physics.dq_frame import (
    current_magnitude,
    electromagnetic_torque,
    steady_state_voltages,
    voltage_magnitude,
)


# ---------------------------------------------------------------------------
# SPMSM parameters: L_d == L_q, so reluctance term must be zero.
# ---------------------------------------------------------------------------
SPMSM = {
    "p": 4,
    "lambda_pm": 0.15,
    "L_d": 5.0e-4,
    "L_q": 5.0e-4,
    "R_s": 0.05,
}

# ---------------------------------------------------------------------------
# IPMSM parameters: L_q > L_d (saliency). Ballpark of Tesla Model 3 rear motor.
# ---------------------------------------------------------------------------
IPMSM = {
    "p": 4,
    "lambda_pm": 0.08,
    "L_d": 2.0e-4,
    "L_q": 6.0e-4,
    "R_s": 0.015,
}


# ---------------------------------------------------------------------------
# Torque
# ---------------------------------------------------------------------------

class TestTorqueSPMSM:
    def test_reluctance_term_vanishes(self):
        """With L_d == L_q, torque depends only on i_q (BRIEF §A.2)."""
        base = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=0.0, i_q=200.0,
        )
        # Any i_d must produce the same torque for SPMSM.
        swept = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=-150.0, i_q=200.0,
        )
        assert math.isclose(base, swept, rel_tol=1e-12, abs_tol=1e-12)

    def test_closed_form_value(self):
        """Hand-computed T_em against Appendix A.2."""
        i_q = 250.0
        expected = 1.5 * SPMSM["p"] * SPMSM["lambda_pm"] * i_q
        got = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=0.0, i_q=i_q,
        )
        assert math.isclose(got, expected, rel_tol=1e-12)

    def test_zero_at_zero_current(self):
        got = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=0.0, i_q=0.0,
        )
        assert got == 0.0

    def test_sign_tracks_i_q(self):
        pos = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=0.0, i_q=+100.0,
        )
        neg = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=0.0, i_q=-100.0,
        )
        assert pos > 0.0
        assert neg == -pos


class TestTorqueIPMSM:
    def test_reluctance_term_contributes(self):
        """For IPMSM with i_d<0, reluctance term adds positive torque."""
        pm_only = 1.5 * IPMSM["p"] * IPMSM["lambda_pm"] * 200.0
        full = electromagnetic_torque(
            IPMSM["p"], IPMSM["lambda_pm"], IPMSM["L_d"], IPMSM["L_q"],
            i_d=-100.0, i_q=200.0,
        )
        # Reluctance term: (3/2)*p*(L_d-L_q)*i_d*i_q with L_d<L_q and i_d<0 is positive.
        assert full > pm_only

    def test_closed_form_value(self):
        p, lam = IPMSM["p"], IPMSM["lambda_pm"]
        L_d, L_q = IPMSM["L_d"], IPMSM["L_q"]
        i_d, i_q = -120.0, 220.0
        expected = 1.5 * p * (lam * i_q + (L_d - L_q) * i_d * i_q)
        got = electromagnetic_torque(p, lam, L_d, L_q, i_d=i_d, i_q=i_q)
        assert math.isclose(got, expected, rel_tol=1e-12)

    def test_positive_i_d_reduces_torque(self):
        """Positive i_d with L_d<L_q makes reluctance torque negative."""
        at_zero = electromagnetic_torque(
            IPMSM["p"], IPMSM["lambda_pm"], IPMSM["L_d"], IPMSM["L_q"],
            i_d=0.0, i_q=200.0,
        )
        at_pos = electromagnetic_torque(
            IPMSM["p"], IPMSM["lambda_pm"], IPMSM["L_d"], IPMSM["L_q"],
            i_d=+100.0, i_q=200.0,
        )
        assert at_pos < at_zero


class TestTorqueVectorized:
    def test_accepts_arrays(self):
        i_q = np.array([0.0, 100.0, 200.0])
        got = electromagnetic_torque(
            SPMSM["p"], SPMSM["lambda_pm"], SPMSM["L_d"], SPMSM["L_q"],
            i_d=np.zeros_like(i_q), i_q=i_q,
        )
        expected = 1.5 * SPMSM["p"] * SPMSM["lambda_pm"] * i_q
        np.testing.assert_allclose(got, expected, rtol=1e-12)


# ---------------------------------------------------------------------------
# Steady-state voltages
# ---------------------------------------------------------------------------

class TestVoltagesSPMSM:
    def test_zero_current_zero_speed(self):
        v_d, v_q = steady_state_voltages(
            SPMSM["R_s"], SPMSM["L_d"], SPMSM["L_q"], SPMSM["lambda_pm"],
            omega_e=0.0, i_d=0.0, i_q=0.0,
        )
        assert v_d == 0.0
        assert v_q == 0.0

    def test_open_circuit_back_emf(self):
        """With no current, v_q = ω_e · λ_pm; v_d = 0 (BRIEF §A.3)."""
        omega_e = 1000.0
        v_d, v_q = steady_state_voltages(
            SPMSM["R_s"], SPMSM["L_d"], SPMSM["L_q"], SPMSM["lambda_pm"],
            omega_e=omega_e, i_d=0.0, i_q=0.0,
        )
        assert v_d == 0.0
        assert math.isclose(v_q, omega_e * SPMSM["lambda_pm"], rel_tol=1e-12)

    def test_resistive_drop_at_zero_speed(self):
        """At ω_e = 0, voltages collapse to pure resistive drop."""
        i_d, i_q = -20.0, 150.0
        v_d, v_q = steady_state_voltages(
            SPMSM["R_s"], SPMSM["L_d"], SPMSM["L_q"], SPMSM["lambda_pm"],
            omega_e=0.0, i_d=i_d, i_q=i_q,
        )
        assert math.isclose(v_d, SPMSM["R_s"] * i_d, rel_tol=1e-12)
        assert math.isclose(v_q, SPMSM["R_s"] * i_q, rel_tol=1e-12)

    def test_closed_form_value(self):
        R, L_d, L_q, lam = (
            SPMSM["R_s"], SPMSM["L_d"], SPMSM["L_q"], SPMSM["lambda_pm"],
        )
        omega_e, i_d, i_q = 400.0, -30.0, 180.0
        exp_d = R * i_d - omega_e * L_q * i_q
        exp_q = R * i_q + omega_e * L_d * i_d + omega_e * lam
        v_d, v_q = steady_state_voltages(
            R, L_d, L_q, lam, omega_e=omega_e, i_d=i_d, i_q=i_q,
        )
        assert math.isclose(v_d, exp_d, rel_tol=1e-12)
        assert math.isclose(v_q, exp_q, rel_tol=1e-12)

    def test_voltage_magnitude_within_bus_limit(self):
        """MTPA at base speed should satisfy |v| ≤ V_max ≈ V_dc/√3."""
        V_dc = 400.0
        V_max = V_dc / math.sqrt(3.0)
        i_q = 250.0  # MTPA for SPMSM: i_d = 0, i_q = I_max
        # Pick ω_e small enough to stay under the limit.
        omega_e = 200.0
        v_d, v_q = steady_state_voltages(
            SPMSM["R_s"], SPMSM["L_d"], SPMSM["L_q"], SPMSM["lambda_pm"],
            omega_e=omega_e, i_d=0.0, i_q=i_q,
        )
        assert voltage_magnitude(v_d, v_q) <= V_max


class TestVoltagesIPMSM:
    def test_saliency_affects_v_d(self):
        """v_d has L_q·i_q, v_q has L_d·i_d — saliency splits them (§A.3)."""
        R, L_d, L_q, lam = (
            IPMSM["R_s"], IPMSM["L_d"], IPMSM["L_q"], IPMSM["lambda_pm"],
        )
        omega_e, i_d, i_q = 600.0, -80.0, 220.0
        exp_d = R * i_d - omega_e * L_q * i_q
        exp_q = R * i_q + omega_e * L_d * i_d + omega_e * lam
        v_d, v_q = steady_state_voltages(
            R, L_d, L_q, lam, omega_e=omega_e, i_d=i_d, i_q=i_q,
        )
        assert math.isclose(v_d, exp_d, rel_tol=1e-12)
        assert math.isclose(v_q, exp_q, rel_tol=1e-12)

    def test_field_weakening_reduces_v_q(self):
        """Injecting negative i_d reduces v_q (field weakening, §A.4)."""
        omega_e, i_q = 800.0, 200.0
        _, v_q_nofw = steady_state_voltages(
            IPMSM["R_s"], IPMSM["L_d"], IPMSM["L_q"], IPMSM["lambda_pm"],
            omega_e=omega_e, i_d=0.0, i_q=i_q,
        )
        _, v_q_fw = steady_state_voltages(
            IPMSM["R_s"], IPMSM["L_d"], IPMSM["L_q"], IPMSM["lambda_pm"],
            omega_e=omega_e, i_d=-150.0, i_q=i_q,
        )
        assert v_q_fw < v_q_nofw


class TestVoltageMagnitude:
    def test_pythagoras(self):
        assert math.isclose(voltage_magnitude(3.0, 4.0), 5.0, rel_tol=1e-12)

    def test_vectorized(self):
        out = voltage_magnitude(np.array([3.0, 0.0]), np.array([4.0, 5.0]))
        np.testing.assert_allclose(out, [5.0, 5.0])


class TestCurrentMagnitude:
    def test_pythagoras(self):
        assert math.isclose(current_magnitude(0.0, 10.0), 10.0, rel_tol=1e-12)

    def test_respects_current_limit(self):
        """MTPA for SPMSM (i_d=0, i_q=I_max) saturates |i| at I_max."""
        I_max = 300.0
        assert math.isclose(
            current_magnitude(0.0, I_max), I_max, rel_tol=1e-12,
        )
