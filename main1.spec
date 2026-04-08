# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app', 'app'),
        ('config', 'config'),
        ('constants', 'constants'),
        ('models', 'models'),
        ('.env', '.'),

        # --- THE FIX: Explicitly add the icons folder ---
        # This tells PyInstaller to copy the 'widget_icons' folder
        # from 'app/widgets/' in your source code to 'app/widgets/'
        # inside the final packaged application.
        ('app/widgets/widget_icons', 'app/widgets/widget_icons')
        # --- END OF FIX ---

    ],
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
    name='main',
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
    icon=['C:\\Users\\Administrator\\Desktop\\MBPI-Projects\\DEPLOYMENT-MixerExtruder-Project\\production_icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)