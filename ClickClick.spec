# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['mouse_recorder.py'],
    pathex=[],
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
    a.binaries,
    a.datas,
    [],
    name='ClickClick',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compresse l'exécutable mais déclenche les heuristiques antivirus, qui
    # sont déjà sensibles à la combinaison PyInstaller + hook clavier global.
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
