"""ParamPanel — collapsible parameter groups with slider + spinbox two-way binding.

Each group (Geometry / Electrical / Material / Limits) is a checkable QGroupBox.
Unchecking collapses its contents.  Every parameter row has a QSlider and a
QDoubleSpinBox / QSpinBox that stay in sync via blockSignals.  A 50 ms QTimer
debounces the ``paramsChanged`` signal so rapid slider drags don't flood
downstream consumers (BRIEF §5 P2).
"""
from __future__ import annotations

from typing import NamedTuple, Union

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ev_motor_sim.models import MotorParams, Topology, RotorSaliency

_SLIDER_STEPS = 1000


class _ParamSpec(NamedTuple):
    """Describes one editable motor parameter."""
    key: str           # attribute name on MotorParams
    label: str         # row label shown in the UI
    store_min: float   # min in storage units (MotorParams field)
    store_max: float   # max in storage units
    store_def: float   # default in storage units
    decimals: int      # spinbox decimal places (in display units)
    disp_unit: str     # unit string shown after label
    disp_mult: float = 1.0   # storage → display multiplier
    is_int: bool = False


# Parameters grouped into the four collapsible sections.
# store_min/max must match the Pydantic field ge/le constraints in params.py.
_GROUPS: dict[str, list[_ParamSpec]] = {
    "Geometry": [
        # Radial-PMSM fields
        _ParamSpec("D_ro",  "Rotor diam D_ro",     0.03,  0.40,  0.16,  1, "mm",  disp_mult=1e3),
        _ParamSpec("L_stk", "Stack length L_stk",  0.02,  0.50,  0.10,  1, "mm",  disp_mult=1e3),
        # Axial-flux fields
        _ParamSpec("D_o",   "Disc outer diam D_o", 0.08,  0.60,  0.30,  1, "mm",  disp_mult=1e3),
        _ParamSpec("D_i",   "Disc inner diam D_i", 0.02,  0.50,  0.16,  1, "mm",  disp_mult=1e3),
        _ParamSpec("g_mech","Air-gap g_mech",       2e-4,  3e-3,  1e-3,  2, "mm",  disp_mult=1e3),
        _ParamSpec("l_pm",  "PM thickness l_pm",   1e-3,  20e-3, 6e-3,  2, "mm",  disp_mult=1e3),
        _ParamSpec("mu_r",  "PM rel. perm μ_r",    1.0,   1.2,   1.05,  3, ""),
    ],
    "Electrical": [
        _ParamSpec("p",        "Pole pairs",         1,    20,    4,     0, "",      is_int=True),
        _ParamSpec("N_turns",  "Turns/coil",         1,   500,   10,     0, "",      is_int=True),
        _ParamSpec("k_w",      "Winding factor k_w", 0.80, 0.98,  0.93,  3, ""),
        _ParamSpec("R_s_20",   "R_s @20 °C",         1e-4, 2.0,   0.015, 4, "Ω"),
        _ParamSpec("L_d",      "L_d",                1e-6, 1e-2,  2e-4,  3, "mH",  disp_mult=1e3),
        _ParamSpec("L_q",      "L_q",                1e-6, 1e-2,  2e-4,  3, "mH",  disp_mult=1e3),
        _ParamSpec("lambda_pm","λ_pm",               1e-3, 1.0,   0.12,  3, "Wb"),
    ],
    "Material": [
        _ParamSpec("B_g",      "Air-gap flux B_g",   0.5,  1.2,   0.95,  3, "T"),
        _ParamSpec("A_s",      "Stator loading A_s", 1e4,  1e5,   4.5e4, 0, "A/m"),
        _ParamSpec("k_h",      "Hysteresis k_h",     5e-3, 0.1,   0.02,  4, ""),
        _ParamSpec("alpha",    "Flux exp α",         1.4,  2.0,   1.7,   2, ""),
        _ParamSpec("k_c",      "Eddy-current k_c",   1e-6, 1e-3,  5e-5,  6, ""),
        _ParamSpec("V_core",   "Core volume V_core", 1e-5, 0.1,   2e-3,  5, "m³"),
        _ParamSpec("T_winding","Winding temp",      -20.0, 180.0, 80.0,  0, "°C"),
    ],
    "Limits": [
        _ParamSpec("V_dc",      "DC-bus V_dc",       24.0,  1000.0, 400.0, 0, "V"),
        _ParamSpec("I_max",     "Peak current I_max", 10.0, 2000.0, 400.0, 0, "A"),
        _ParamSpec("T_fric",    "Friction T_fric",    0.0,   5.0,   0.1,   2, "N·m"),
        _ParamSpec("k_windage", "Windage k_windage",  0.0,   1e-3,  1e-6,  7, ""),
    ],
}


class ParamPanel(QWidget):
    """Left-panel parameter editor.

    Signals
    -------
    paramsChanged(MotorParams)
        Emitted at most once per 50 ms while the user is adjusting sliders or
        spinboxes.  Use :py:meth:`get_params` / :py:meth:`set_params` for
        programmatic access.
    """

    paramsChanged = pyqtSignal(MotorParams)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Non-numeric fields preserved across set_params / get_params calls.
        self._topology = Topology.RADIAL_PMSM
        self._saliency = RotorSaliency.SURFACE
        self._name = "Custom motor"

        self._sliders: dict[str, QSlider] = {}
        self._spinboxes: dict[str, Union[QDoubleSpinBox, QSpinBox]] = {}
        self._specs: dict[str, _ParamSpec] = {}

        # 50 ms debounce timer (BRIEF §5 P2).
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(50)
        self._debounce.timeout.connect(self._emit_params)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        vlayout = QVBoxLayout(inner)
        vlayout.setSpacing(6)
        vlayout.setContentsMargins(4, 4, 4, 4)

        for group_name, specs in _GROUPS.items():
            vlayout.addWidget(self._build_group(group_name, specs))

        vlayout.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_params(self) -> MotorParams:
        """Return a :class:`MotorParams` built from the current widget state."""
        values: dict = {
            "name": self._name,
            "topology": self._topology,
            "saliency": self._saliency,
        }
        for key, spec in self._specs.items():
            values[key] = self._read_store_value(key, spec)
        return MotorParams(**values)

    def set_params(self, params: MotorParams) -> None:
        """Update all widgets from *params* without emitting paramsChanged."""
        self._topology = params.topology
        self._saliency = params.saliency
        self._name = params.name
        data = params.model_dump()
        for key, spec in self._specs.items():
            store_val = data[key]
            self._update_spinbox(key, store_val, spec)
            self._update_slider(key, store_val, spec)

    # ------------------------------------------------------------------
    # Group / row construction
    # ------------------------------------------------------------------

    def _build_group(self, name: str, specs: list[_ParamSpec]) -> QGroupBox:
        gb = QGroupBox(name)
        gb.setCheckable(True)
        gb.setChecked(True)

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        contents = QWidget()
        contents.setLayout(form)

        group_layout = QVBoxLayout(gb)
        group_layout.setContentsMargins(4, 4, 4, 4)
        group_layout.addWidget(contents)

        # Collapse / expand by toggling child visibility.
        gb.toggled.connect(contents.setVisible)

        for spec in specs:
            self._specs[spec.key] = spec
            slider, spinbox = self._build_row(spec)
            self._sliders[spec.key] = slider
            self._spinboxes[spec.key] = spinbox

            row_widget = QWidget()
            hl = QHBoxLayout(row_widget)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)
            hl.addWidget(slider, stretch=3)
            hl.addWidget(spinbox, stretch=2)

            label_text = f"{spec.label} [{spec.disp_unit}]" if spec.disp_unit else spec.label
            form.addRow(label_text, row_widget)

        return gb

    def _build_row(self, spec: _ParamSpec):
        disp_min = spec.store_min * spec.disp_mult
        disp_max = spec.store_max * spec.disp_mult
        disp_def = spec.store_def * spec.disp_mult

        if spec.is_int:
            spinbox: Union[QSpinBox, QDoubleSpinBox] = QSpinBox()
            spinbox.setRange(int(spec.store_min), int(spec.store_max))
            spinbox.setValue(int(spec.store_def))
            spinbox.setSingleStep(1)
        else:
            sb = QDoubleSpinBox()
            sb.setDecimals(spec.decimals)
            sb.setRange(disp_min, disp_max)
            sb.setValue(disp_def)
            step = (disp_max - disp_min) / 100.0
            sb.setSingleStep(step if step > 0 else 1.0)
            spinbox = sb

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, _SLIDER_STEPS)
        slider.setValue(self._store_to_slider(spec, spec.store_def))

        key = spec.key
        slider.valueChanged.connect(lambda v, k=key: self._on_slider(k, v))
        if spec.is_int:
            spinbox.valueChanged.connect(lambda v, k=key: self._on_spinbox_int(k, v))
        else:
            spinbox.valueChanged.connect(lambda v, k=key: self._on_spinbox_float(k, v))

        return slider, spinbox

    # ------------------------------------------------------------------
    # Slider ↔ spinbox synchronisation
    # ------------------------------------------------------------------

    def _store_to_slider(self, spec: _ParamSpec, store_val: float) -> int:
        span = spec.store_max - spec.store_min
        if span == 0:
            return 0
        frac = (store_val - spec.store_min) / span
        return round(max(0, min(_SLIDER_STEPS, frac * _SLIDER_STEPS)))

    def _slider_to_store(self, spec: _ParamSpec, slider_int: int) -> float:
        frac = slider_int / _SLIDER_STEPS
        return spec.store_min + frac * (spec.store_max - spec.store_min)

    def _on_slider(self, key: str, slider_val: int) -> None:
        spec = self._specs[key]
        store_val = self._slider_to_store(spec, slider_val)
        sb = self._spinboxes[key]
        sb.blockSignals(True)
        if spec.is_int:
            sb.setValue(round(store_val))
        else:
            sb.setValue(store_val * spec.disp_mult)
        sb.blockSignals(False)
        self._debounce.start()

    def _on_spinbox_float(self, key: str, disp_val: float) -> None:
        spec = self._specs[key]
        store_val = disp_val / spec.disp_mult
        sl = self._sliders[key]
        sl.blockSignals(True)
        sl.setValue(self._store_to_slider(spec, store_val))
        sl.blockSignals(False)
        self._debounce.start()

    def _on_spinbox_int(self, key: str, val: int) -> None:
        spec = self._specs[key]
        sl = self._sliders[key]
        sl.blockSignals(True)
        sl.setValue(self._store_to_slider(spec, val))
        sl.blockSignals(False)
        self._debounce.start()

    def _update_spinbox(self, key: str, store_val: float, spec: _ParamSpec) -> None:
        sb = self._spinboxes[key]
        sb.blockSignals(True)
        if spec.is_int:
            sb.setValue(round(store_val))
        else:
            sb.setValue(store_val * spec.disp_mult)
        sb.blockSignals(False)

    def _update_slider(self, key: str, store_val: float, spec: _ParamSpec) -> None:
        sl = self._sliders[key]
        sl.blockSignals(True)
        sl.setValue(self._store_to_slider(spec, store_val))
        sl.blockSignals(False)

    def _read_store_value(self, key: str, spec: _ParamSpec) -> float | int:
        sb = self._spinboxes[key]
        val = sb.value()
        if spec.is_int:
            return int(val)
        return val / spec.disp_mult

    # ------------------------------------------------------------------
    # Debounced signal emission
    # ------------------------------------------------------------------

    def _emit_params(self) -> None:
        self.paramsChanged.emit(self.get_params())
