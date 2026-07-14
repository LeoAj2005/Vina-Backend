# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Aggressively collect data, binaries, and submodules for our native/heavy deps
datas = []
binaries = []
hiddenimports = []

for pkg in ['lancedb', 'pyarrow', 'fastembed', 'onnxruntime', 'tokenizers', 'uvicorn', 'uvicorn.logging', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# FastAPI/Pydantic also have hidden imports sometimes
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('pydantic')

block_cipher = None

a = Analysis(
    ['vina_launcher.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Vina',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Keep console for Phase 0 debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Vina',
)