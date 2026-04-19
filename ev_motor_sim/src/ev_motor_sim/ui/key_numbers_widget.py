from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt


class _KpiCard(QFrame):
    """Single key-performance-indicator card: label on top, value + unit below."""

    def __init__(self, title: str, unit: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self._title_lbl = QLabel(title)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setStyleSheet("font-size: 10px; color: #666;")

        self._value_lbl = QLabel("—")
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._unit_lbl.setStyleSheet("font-size: 10px; color: #888;")

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)
        layout.addWidget(self._unit_lbl)

    def set_value(self, text: str) -> None:
        self._value_lbl.setText(text)

    def clear(self) -> None:
        self._value_lbl.setText("—")


class KeyNumbersWidget(QWidget):
    """Horizontal row of five KPI cards: peak T, base ω, max ω, peak P, peak η."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._peak_t = _KpiCard("Peak T", "N·m")
        self._base_w = _KpiCard("Base ω", "rpm")
        self._max_w = _KpiCard("Max ω", "rpm")
        self._peak_p = _KpiCard("Peak P", "kW")
        self._peak_eta = _KpiCard("Peak η", "%")

        for card in (self._peak_t, self._base_w, self._max_w, self._peak_p, self._peak_eta):
            layout.addWidget(card, stretch=1)

    def update_values(
        self,
        peak_torque_Nm: float,
        base_speed_rpm: float,
        max_speed_rpm: float,
        peak_power_kW: float,
        peak_eta_pct: float,
    ) -> None:
        self._peak_t.set_value(f"{peak_torque_Nm:.0f}")
        self._base_w.set_value(f"{base_speed_rpm:.0f}")
        self._max_w.set_value(f"{max_speed_rpm:.0f}")
        self._peak_p.set_value(f"{peak_power_kW:.1f}")
        self._peak_eta.set_value(f"{peak_eta_pct:.1f}")

    def clear(self) -> None:
        for card in (self._peak_t, self._base_w, self._max_w, self._peak_p, self._peak_eta):
            card.clear()
