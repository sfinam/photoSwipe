# -*- mode: python ; coding: utf-8 -*-
# Onedir variant used by the AppImage build. Keeping the runtime files next to
# the executable avoids the extra temporary extraction of the one-file build.
import sys

from PyInstaller.utils.hooks import collect_all

rawpy_datas, rawpy_binaries, rawpy_hidden = collect_all("rawpy")
pygame_datas, pygame_binaries, pygame_hidden = collect_all("pygame")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=rawpy_binaries + pygame_binaries,
    datas=rawpy_datas
    + pygame_datas
    + [("assets/icon.png", "assets"), ("assets/icon.ico", "assets")],
    hiddenimports=rawpy_hidden + pygame_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_icon = "assets/icon.ico" if sys.platform == "win32" else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhotoSwipe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PhotoSwipeApp",
)
