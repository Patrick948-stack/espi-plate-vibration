# -*- mode: python ; coding: utf-8 -*-
#
# Mac build recipe for the ESPI app.
#
# This file exists (instead of a plain command line) for one reason:
# PyInstaller has no command line flag for adding custom Info.plist keys,
# and this app needs one, NSCameraUsageDescription, or macOS kills the
# app the instant it opens a camera (a TCC privacy crash, not a normal
# catchable Python error, see the info_plist block below).
#
# Build with, from the project root, venv_physics active:
#   pyinstaller packaging/ESPI.spec --distpath packaging/dist --workpath packaging/build
#
# All paths below are written relative to this file's own location (using
# PyInstaller's built-in SPEC variable), not relative to whatever
# directory you happen to run the command from, so this works the same
# way no matter where it is invoked.

import os

_HERE = os.path.dirname(os.path.abspath(SPEC))
_PROJECT_ROOT = os.path.dirname(_HERE)

a = Analysis(
    [os.path.join(_PROJECT_ROOT, 'espi_app', 'main.py')],
    pathex=[os.path.join(_PROJECT_ROOT, 'ESPI Full Algorithm')],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ESPI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(_HERE, 'assets', 'logo.icns')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ESPI',
)
app = BUNDLE(
    coll,
    name='ESPI.app',
    icon=os.path.join(_HERE, 'assets', 'logo.icns'),
    bundle_identifier='edu.whitman.espi',
    info_plist={
        # Required. Without this key, macOS kills the app the instant it
        # tries to open any camera (cv2.VideoCapture, pypylon, vmbpy),
        # with a TCC privacy crash, not a normal catchable Python error.
        # This is the exact string macOS shows the user in the permission
        # prompt the first time the app opens a camera.
        'NSCameraUsageDescription':
            'ESPI needs camera access to capture live speckle pattern images '
            'for vibration measurement.',
    },
)
