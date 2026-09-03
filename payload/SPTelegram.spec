# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve()
BUILD_ASSETS = ROOT / ".build_assets"

# Keep runtime resources at the same package-relative locations used by the
# source tree. Module-relative __file__ lookups therefore work in both source
# runs and PyInstaller's extraction directory.
datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "app" / "styles"), "app/styles"),
    (str(ROOT / "app" / "localization"), "app/localization"),
]

datas += copy_metadata("keyring")

hiddenimports = sorted(
    set(
        collect_submodules("keyring.backends")
        + [
            "qrcode.image.pil",
        ]
    )
)


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "license_server",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SP Telegram",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BUILD_ASSETS / "sp_telegram.ico"),
    version=str(BUILD_ASSETS / "version_info.txt"),
    uac_admin=False,
)
