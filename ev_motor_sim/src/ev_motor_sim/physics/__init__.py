"""Physics primitives for PMSM / AFPM simulation (BRIEF §A)."""

from ev_motor_sim.physics.dq_frame import (
    current_magnitude,
    electromagnetic_torque,
    steady_state_voltages,
    voltage_magnitude,
)
from ev_motor_sim.physics.losses import (
    copper_loss,
    friction_loss,
    iron_loss,
    mechanical_loss,
    stray_loss,
    windage_loss,
)

__all__ = [
    "copper_loss",
    "current_magnitude",
    "electromagnetic_torque",
    "friction_loss",
    "iron_loss",
    "mechanical_loss",
    "steady_state_voltages",
    "stray_loss",
    "voltage_magnitude",
    "windage_loss",
]
