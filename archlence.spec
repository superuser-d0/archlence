# -*- mode: python ; coding: utf-8 -*-
#
# Archlence — Windows PyInstaller spec dosyası
#
# ÖNEMLİ: PyInstaller çapraz derleme YAPAMAZ. Bu dosya Windows üzerinde
# çalıştırılmalı (GitHub Actions'taki windows-latest runner dahil). Linux'ta
# `pyinstaller archlence.spec` çalıştırırsan Linux binary üretir, .exe değil.
#
# Kullanım (Windows'ta, venv aktifken):
#   pip install pyinstaller kivy_deps.sdl2 kivy_deps.glew kivy_deps.angle
#   pyinstaller archlence.spec
#
# Çıktı: dist/Archlence/Archlence.exe (+ yanındaki DLL/kaynak klasörü — bu bir
# "onedir" build, tek dosyalık .exe DEĞİL. Kivy uygulamaları PyInstaller'da
# --onefile ile sık sorun çıkarır; onedir çok daha güvenilir. Dağıtırken
# dist/Archlence/ klasörünün TAMAMINI zipleyip paylaş.)
#
# İkonun vektör kaynağı assets/icon_source.svg; masaüstü paketleri için
# üretilmiş PNG ve çok çözünürlüklü ICO sürümleri assets/ altında tutulur.

import os
from kivy_deps import sdl2, glew
from PyInstaller.utils.hooks import collect_all

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

# KivyMD kendi içinde .kv dosyaları, fontlar ve ikonlar taşıyor; PyInstaller
# bunları normal .py taramasıyla bulamaz, collect_all ile açıkça toplanıyor.
kivymd_datas, kivymd_binaries, kivymd_hidden = collect_all("kivymd")

# matplotlib / kivy_garden.matplotlib BİLEREK toplanmıyor.
#
# Vaktiyle grafikler için eklenmişti, ama uygulama artık tüm grafikleri ham
# Kivy canvas'ıyla çiziyor (ui/charts.py: CurvedTrendChart, PieChart,
# HorizontalBarChart...). Kod tabanının tamamında — .py, .kv, .json — tek bir
# matplotlib/scipy referansı yok.
#
# `collect_all("kivy_garden.matplotlib")` ise matplotlib'i TÜM veri dosyaları
# ve fontlarıyla birlikte içeri çekiyordu: matplotlib 25 MB + fontTools 21 MB,
# yanında hiç kullanılmayan scipy 113 MB. Windows runner'da derlemenin 34
# dakikaya çıkıp iptal edilmesinin ana sebebi buydu.
#
# Grafikler için matplotlib'e geri dönülürse burayı geri açmak yetmez;
# aşağıdaki `excludes` listesinden de çıkarılmalı.

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[*kivymd_binaries],
    datas=[
        ("ui", "ui"),           # main.py:230 -> Builder.load_file("ui/dashboard.kv")
        ("assets", "assets"),   # assets/stock_logos/*.png (BIST logoları)
        ("data", "data"),       # data/bist100.py'nin yanındaki statik veriler
        *kivymd_datas,
    ],
    hiddenimports=[
        "yfinance",
        "curl_cffi",
        "peewee",
        "playhouse.sqlite_ext",
        "Crypto.Cipher.AES",
        *kivymd_hidden,
    ],
    hookspath=[],
    runtime_hooks=[],
    # Kullanılmayan ağır bağımlılıklar. Bunlar dolaylı olarak (bir kütüphanenin
    # isteğe bağlı importu üzerinden) içeri sızabiliyor; açıkça dışlanınca hem
    # derleme süresi hem çıktı boyutu ciddi düşüyor.
    #   * matplotlib/kivy_garden/mpl_toolkits/scipy: yukarıdaki nota bak.
    #   * flake8, pycodestyle, pyflakes, mccabe: requirements.txt'te duran lint
    #     araçları — çalışma zamanında hiç gerekmiyor.
    #   * tkinter: Kivy uygulaması, Tk'ye ihtiyaç yok.
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
    # UPX KAPALI. İki sebep:
    #   1) Hız: UPX her ikiliyi tek tek, tek çekirdekte sıkıştırır. numpy,
    #      pandas, curl_cffi, kivy ve cryptography'nin DLL'leriyle bu, CI'da
    #      derlemenin en uzun adımı hâline geliyor.
    #   2) Doğruluk: UPX'in numpy/pandas gibi bilimsel yığınların .pyd/.dll
    #      dosyalarını bozup çalışma anında "DLL load failed" ürettiği bilinen
    #      bir sorun. Kazanılan birkaç on MB, bu riske değmiyor.
    upx=False,
    console=False,   # arka planda siyah konsol penceresi açılmasın
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    *[Tree(p) for p in sdl2.dep_bins + glew.dep_bins],
    strip=False,
    upx=False,   # EXE'deki ile aynı gerekçe (hız + numpy/pandas bozulması)
    name="Archlence",
)
