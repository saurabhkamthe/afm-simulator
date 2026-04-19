"""Physics primitives for PMSM / AFPM simulation (BRIEF §A)."""

from ev_motor_sim.physics.dq_frame import (
    current_magnitude,
    electromagnetic_torque,
    steady_state_voltages,
    voltage_magnitude,
)

__all__ = [
    "current_magnitude",
    "electromagnetic_torque",
    "steady_state_voltages",
    "voltage_magnitude",
]
