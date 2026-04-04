# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# 动态数据文件 - 包含模板和静态文件
datas = [
    ('EasyShare/templates', 'templates'),
    ('EasyShare/static', 'static'),
]

a = Analysis(
    ['EasyShare/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'flask',
        'flask_sslify',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
        'colorama',
        'PIL',
        'PIL._imaging',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EasyShare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='EasyShare.manifest',  # 使用manifest文件请求管理员权限
)
