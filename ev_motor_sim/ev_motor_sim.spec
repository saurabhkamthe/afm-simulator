# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ev-motor-sim single-file binary (T-601 / T-504).

Build from the ev_motor_sim/ directory:
    pyinstaller ev_motor_sim.spec
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['src/ev_motor_sim/main.py'],
    pathex=['src'],
    binaries=[],
    datas=collect_data_files('ev_motor_sim', includes=['presets/*.json']),
    hiddenimports=[
        *collect_submodules('ev_motor_sim'),
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtOpenGL',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'matplotlib',
        'matplotlib.backends.backend_qtagg',
        'numpy',
        'scipy',
        'scipy.special._ufuncs_cxx',
        'pydantic',
        'pydantic.v1',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PySide2', 'PySide6', 'PyQt5'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ev-motor-sim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
