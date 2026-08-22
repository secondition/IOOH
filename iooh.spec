# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


def collect_tree(source_dir, target_dir):
    source_path = Path(source_dir)
    return [
        (
            str(path),
            str(
                Path(target_dir) / path.relative_to(source_path).parent
            ).replace(".", "")
        )
        for path in source_path.rglob('*')
        if path.is_file()
    ]


datas = collect_tree('shaders', 'shaders')
datas += [('icon.ico', '.')]


a = Analysis(
    ['key_context_configurator.py'],
    pathex=[],
    binaries=[],
    datas=datas,
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
    name='iooh',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
