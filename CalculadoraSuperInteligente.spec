# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/presentation/assets', 'src/presentation/assets'),
        ('src/infrastructure/parsing/grammar.lark', 'src/infrastructure/parsing')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
a.datas = [item for item in a.datas
           if not item[0].replace('\\', '/').startswith('PySide6/qml/')]
a.binaries = [item for item in a.binaries
              if not item[0].replace('\\', '/').startswith('PySide6/qml/')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CalculadoraSuperInteligente',
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
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CalculadoraSuperInteligente',
)
