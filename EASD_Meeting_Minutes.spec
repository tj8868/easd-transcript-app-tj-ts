# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/ESAD -Taseen-Workspace-2026/EASD-TJ-Admin/EASD Meeting Minutes/Transcription APP/app.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/ESAD -Taseen-Workspace-2026/EASD-TJ-Admin/EASD Meeting Minutes/Transcription APP/frontend/dist', 'frontend/dist'), ('E:/ESAD -Taseen-Workspace-2026/EASD-TJ-Admin/EASD Meeting Minutes/Transcription APP/static', 'static'), ('E:/ESAD -Taseen-Workspace-2026/EASD-TJ-Admin/EASD Meeting Minutes/Transcription APP/EASD Meeting minutes - Template-DDMonthYY.docx', '.')],
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
    name='EASD_Meeting_Minutes',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EASD_Meeting_Minutes',
)
