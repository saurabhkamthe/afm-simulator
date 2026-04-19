"""Shared pytest fixtures for ev_motor_sim test suite."""
import pytest


@pytest.fixture
def pmsm_params():
    """Minimal PMSM parameter dict for unit tests."""
    return {
        "topology": "radial",
        "p": 4,
        "lambda_pm": 0.15,
        "L_d": 0.5e-3,
        "L_q": 0.8e-3,
        "R_s": 0.05,
        "V_dc": 400.0,
        "I_max": 300.0,
        "T_fric": 0.1,
        "R_s20": 0.05,
    }


@pytest.fixture
def afpm_params():
    """Minimal AFPM parameter dict for unit tests."""
    return {
        "topology": "axial",
        "p": 8,
        "lambda_pm": 0.20,
        "L_d": 0.4e-3,
        "L_q": 0.4e-3,
        "R_s": 0.03,
        "V_dc": 400.0,
        "I_max": 500.0,
        "D_o": 0.35,
        "D_i": 0.20,
        "T_fric": 0.1,
        "R_s20": 0.03,
    }
