#!/usr/bin/env bash
# Verify that the package installs from a clean venv and the test + GUI surfaces work.
# Must be runnable from a fresh checkout with nothing but Python >= 3.11 on PATH.
#
# Exit codes:
#   0  success
#   1  environment / install failure
#   2  pytest failure
#   3  GUI smoke failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/fresh_venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_ROOT"

echo "==> Removing any previous venv at $VENV_DIR"
rm -rf "$VENV_DIR"

echo "==> Creating fresh venv with $PYTHON_BIN"
if ! "$PYTHON_BIN" -m venv "$VENV_DIR" 2>/dev/null; then
    echo "   venv module missing ensurepip; bootstrapping pip manually"
    "$PYTHON_BIN" -m venv --without-pip "$VENV_DIR"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$VENV_DIR/get-pip.py"
    "$VENV_DIR/bin/python" "$VENV_DIR/get-pip.py"
    rm -f "$VENV_DIR/get-pip.py"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip"
python -m pip install --upgrade pip >/dev/null

echo "==> Installing ev_motor_sim with dev extras (editable)"
pip install -e ".[dev]"

echo "==> Running pytest"
pytest -v

echo "==> GUI smoke test (offscreen)"
QT_QPA_PLATFORM=offscreen python - <<'PY'
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ev_motor_sim.ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("EV Motor Simulator")
window = MainWindow()
window.show()
assert window.isVisible(), "MainWindow did not become visible"
QTimer.singleShot(200, app.quit)
app.exec()
print("GUI smoke OK")
PY

echo "==> Clean install verified"
