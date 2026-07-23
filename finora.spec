# -*- mode: python ; coding: utf-8 -*-
#
# Finora — Windows PyInstaller spec dosyası
#
# ÖNEMLİ: PyInstaller çapraz derleme YAPAMAZ. Bu dosya Windows üzerinde
# çalıştırılmalı (GitHub Actions'taki windows-latest runner dahil). Linux'ta
# `pyinstaller finora.spec` çalıştırırsan Linux binary üretir, .exe değil.
#
# Kullanım (Windows'ta, venv aktifken):
#   pip install pyinstaller kivy_deps.sdl2 kivy_deps.glew kivy_deps.angle
#   pyinstaller finora.spec
#
# Çıktı: dist/Finora/Finora.exe (+ yanındaki DLL/kaynak klasörü — bu bir
# "onedir" build, tek dosyalık .exe DEĞİL. Kivy uygulamaları PyInstaller'da
# --onefile ile sık sorun çıkarır; onedir çok daha güvenilir. Dağıtırken
# dist/Finora/ klasörünün TAMAMINI zipleyip paylaş.)

import os
from kivy_deps import sdl2, glew
from PyInstaller.utils.hooks import collect_all

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

# KivyMD kendi içinde .kv dosyaları, fontlar ve ikonlar taşıyor; PyInstaller
# bunları normal .py taramasıyla bulamaz, collect_all ile açıkça toplanıyor.
kivymd_datas, kivymd_binaries, kivymd_hidden = collect_all("kivymd")
mpl_datas, mpl_binaries, mpl_hidden = collect_all("kivy_garden.matplotlib")

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[*kivymd_binaries, *mpl_binaries],
    datas=[
        ("ui", "ui"),           # main.py:230 -> Builder.load_file("ui/dashboard.kv")
        ("assets", "assets"),   # assets/stock_logos/*.png (BIST logoları)
        ("data", "data"),       # data/bist100.py'nin yanındaki statik veriler
        *kivymd_datas,
        *mpl_datas,
    ],
    hiddenimports=[
        "kivy_garden.matplotlib",
        "kivy_garden.matplotlib.backend_kivyagg",
        "matplotlib.backends.backend_agg",
        "yfinance",
        "curl_cffi",
        "peewee",
        "playhouse.sqlite_ext",
        "Crypto.Cipher.AES",
        *kivymd_hidden,
        *mpl_hidden,
    ],
    hookspath=[],
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
    name="Finora",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # arka planda siyah konsol penceresi açılmasın
    icon=None,        # ikon hazır olunca: "assets/icon.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    *[Tree(p) for p in sdl2.dep_bins + glew.dep_bins],
    strip=False,
    upx=True,
    name="Finora",
)
