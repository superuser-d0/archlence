

import sys

IS_WINDOWS = sys.platform.startswith("win")


import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

if IS_WINDOWS:
    from kivy_deps import sdl2, glew, angle

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")


kivymd_datas, kivymd_binaries, kivymd_hidden = collect_all("kivymd")


a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[*kivymd_binaries],
    datas=[
        ("ui", "ui"),           # main.py:230 -> Builder.load_file("ui/dashboard.kv")
        ("assets", "assets"),
        ("data", "data"),
        *kivymd_datas,
    ],
    hiddenimports=[
        "yfinance",
        "curl_cffi",
        "peewee",
        "playhouse.sqlite_ext",
        "Crypto.Cipher.AES",


        "win32timezone",
        *collect_submodules("keyring.backends"),
        *kivymd_hidden,
    ],
    hookspath=[],
    runtime_hooks=[],


    excludes=[
        "matplotlib",
        "kivy_garden",
        "mpl_toolkits",
        "scipy",
        "tkinter",
        "flake8",
        "pycodestyle",
        "pyflakes",
        "mccabe",
        "docutils",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


a.datas = [
    item for item in a.datas
    if not item[0].replace("\\", "/").startswith("kivy_install/modules/")
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Archlence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,


    upx=False,
    console=False,


    icon="assets/icon.ico" if IS_WINDOWS else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,


    *([Tree(p) for p in sdl2.dep_bins + glew.dep_bins + angle.dep_bins]
      if IS_WINDOWS else []),
    strip=False,
    upx=False,
    name="Archlence",
)
