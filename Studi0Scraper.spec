# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scraper_app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/gear-outline-dark.png', 'assets'), ('assets/gear-outline-light.png', 'assets')],
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
    name='Studi0Scraper',
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
    icon=['assets/Studi0Scraper.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Studi0Scraper',
)
app = BUNDLE(
    coll,
    name='Studi0Scraper.app',
    icon='assets/Studi0Scraper.icns',
    bundle_identifier=None,
)
