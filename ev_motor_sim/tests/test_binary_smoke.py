"""Smoke test: PyInstaller binary launches without crashing (T-504).

Acceptance criterion: the binary starts, renders the main window and stays
alive for at least ALIVE_SECONDS without crashing, on any platform.

The test is skipped when:
- PyInstaller is not installed (``pyinstaller`` not on PATH), or
- the spec file ``ev_motor_sim.spec`` is absent.

The binary is built once per pytest session into a temporary directory so
that repeated parametrisation or re-runs within the same session are fast.

Platform notes
--------------
Linux   : sets QT_QPA_PLATFORM=offscreen (no X server required).
Windows : console=False binary runs via DETACHED_PROCESS; offscreen used.
macOS   : offscreen platform works without a window server in CI.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).parent.parent          # .../ev_motor_sim/
SPEC_FILE = PACKAGE_ROOT / "ev_motor_sim.spec"

ALIVE_SECONDS = 5      # binary must stay running at least this long
STARTUP_GRACE = 10     # total seconds to wait before declaring it alive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pyinstaller_available() -> bool:
    """True when PyInstaller is importable under the current Python."""
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        capture_output=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Session-scoped build fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def built_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the PyInstaller --onefile binary; return its filesystem path."""
    if not _pyinstaller_available():
        pytest.skip("pyinstaller not on PATH — skipping binary smoke test")

    if not SPEC_FILE.exists():
        pytest.skip(f"Spec file not found: {SPEC_FILE} — run from ev_motor_sim/")

    workdir = tmp_path_factory.mktemp("pyinstaller")
    dist_dir = workdir / "dist"
    build_dir = workdir / "build"

    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--distpath", str(dist_dir),
            "--workpath", str(build_dir),
            "--noconfirm",
            str(SPEC_FILE),
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        tail = lambda s: s[-3000:] if len(s) > 3000 else s
        pytest.fail(
            f"PyInstaller build failed (rc={result.returncode})\n"
            f"--- stdout ---\n{tail(result.stdout)}\n"
            f"--- stderr ---\n{tail(result.stderr)}"
        )

    exe_name = "ev-motor-sim" + (".exe" if sys.platform == "win32" else "")
    binary = dist_dir / exe_name
    assert binary.exists(), f"Built binary not found at {binary}"
    return binary


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_binary_launches_without_crashing(built_binary: Path) -> None:
    """Binary must stay alive for ALIVE_SECONDS when run headlessly."""
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Suppress noisy Qt debug output in CI logs.
        "QT_LOGGING_RULES": "*.debug=false",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    kwargs: dict = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS

    proc = subprocess.Popen([str(built_binary)], **kwargs)

    crashed_early = False
    rc: int | None = None
    deadline = time.monotonic() + STARTUP_GRACE

    while time.monotonic() < deadline:
        rc = proc.poll()
        if rc is not None:
            crashed_early = True
            break
        time.sleep(0.25)

    if not crashed_early:
        # Still running — success. Terminate cleanly.
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return  # test passes

    # Process exited before STARTUP_GRACE elapsed.
    stderr_text = b""
    if proc.stderr:
        stderr_text = proc.stderr.read()
    stdout_text = b""
    if proc.stdout:
        stdout_text = proc.stdout.read()

    pytest.fail(
        f"Binary exited with rc={rc} within {STARTUP_GRACE} s "
        f"(expected it to stay alive for at least {ALIVE_SECONDS} s).\n"
        f"stdout: {stdout_text.decode(errors='replace')}\n"
        f"stderr: {stderr_text.decode(errors='replace')}"
    )
