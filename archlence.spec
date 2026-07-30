# -*- mode: python ; coding: utf-8 -*-
#
# Archlence — PyInstaller spec dosyası (Windows + Linux)
#
# ÖNEMLİ: PyInstaller çapraz derleme YAPAMAZ. Bu dosya, üretmek istediğin
# platformun kendi üzerinde çalıştırılmalı (GitHub Actions'ta windows-latest
# .exe, ubuntu-latest Linux ikili üretir). `pyinstaller archlence.spec`
# hangi platformda çalışırsa o platformun çıktısını üretir.
#
# Kullanım (Windows'ta, venv aktifken):
#   pip install pyinstaller kivy_deps.sdl2 kivy_deps.glew kivy_deps.angle
#   set KIVY_GL_BACKEND=angle_sdl2
#   pyinstaller archlence.spec
#
# Kullanım (Linux'ta, venv aktifken):
#   pip install pyinstaller
#   pyinstaller archlence.spec
#   (kivy_deps YOK — o paketler yalnızca Windows'ta SDL2/GLEW/ANGLE'ı DLL
#   olarak bundle etmek için var; Linux'ta Kivy pip tekerleği kendi SDL2'sini
#   zaten taşır, ayrıca paket gerekmez.)
#
# KIVY_GL_BACKEND=angle_sdl2 yalnızca WINDOWS'ta ZORUNLU (aşağıdaki nota
# bak) — onsuz derleme GPU'suz makinelerde (CI runner'ları dahil) çöker.
# Linux runner'ında (ubuntu-latest, ekransız) ANGLE bir seçenek değil —
# ama SDL'nin "dummy" video sürücüsü de (run_tests.py'nin headless test
# deseni) İŞE YARAMIYOR: dummy sürücü hiçbir OpenGL yüzeyi sağlamıyor,
# oysa aşağıdaki `collect_all("kivymd")` GERÇEK (yazılım da olsa) bir GL
# bağlamı istiyor — bu, yerel bir Linux makinesinde denenip doğrulandı.
# Çalışan çözüm: `xvfb-run` ile sanal ama gerçek bir X11 ekranı açmak;
# Mesa'nın llvmpipe yazılım rasterizer'ı üzerinden gelen bağlam Kivy'nin
# OpenGL şartını karşılıyor. Bkz. .github/workflows/build-linux.yml.
#
# Çıktı:
#   Windows: dist/Archlence/Archlence.exe (+ yanındaki DLL/kaynak klasörü)
#   Linux:   dist/Archlence/Archlence     (+ yanındaki .so/kaynak klasörü)
#   İkisi de "onedir" build, tek dosya DEĞİL. Kivy uygulamaları PyInstaller'da
#   --onefile ile sık sorun çıkarır; onedir çok daha güvenilir. Windows'ta
#   installer/archlence.iss, Linux'ta AppImage bu onedir çıktısını tek
#   dosyaya sarmalıyor (bkz. .github/workflows/build-linux.yml).
#
# İkonun vektör kaynağı assets/icon_source.svg; masaüstü paketleri için
# üretilmiş PNG ve çok çözünürlüklü ICO sürümleri assets/ altında tutulur.
# PyInstaller'ın EXE(icon=...) parametresi yalnızca Windows/macOS'ta ikiliye
# gömülür; Linux'ta hiçbir etkisi yok — Linux masaüstü ikonu
# assets/archlence.desktop'taki Icon= alanından ve AppImage'ın kendi
# ikonundan gelir, bu yüzden Linux derlemesinde icon= hiç verilmiyor.
import sys

IS_WINDOWS = sys.platform.startswith("win")

# KIVY_GL_BACKEND ortam değişkeni, PyInstaller BU DOSYAYI Python olarak
# çalıştırırken (aşağıdaki `collect_all("kivymd")` satırında) zaten devrede
# olmalı — burada set etmek ÇOK GEÇ, işlem environment'ı build başlamadan önce
# hazır olmalı (bkz. .github/workflows/build-windows.yml).
#
# NEDEN: `collect_all("kivymd")` kivymd paketini gerçekten import eder. Bu
# zincir Kivy'nin `Window` singleton'ını da tetikler — Kivy'nin bilinen bir
# garipliği: pencere `.run()` çağrılmasını beklemez, `kivy.core.window`
# import edilir edilmez gerçek bir SDL2 penceresi + GL bağlamı açar. GitHub
# Actions'ın Windows runner'ında gerçek GPU yok; sürücü "GDI Generic" yazılım
# render'ına düşer ve yalnızca OpenGL 1.1 verir — Kivy 2.0 şart koşar, CRITICAL
# hatasıyla çöker ve süreç temiz kapanmadığı için PyInstaller'ın analiz adımı
# SONSUZA KADAR ASILI KALIR (build #1'den beri her derlemenin 6 saatte
# zaman aşımına uğramasının GERÇEK sebebi buydu — matplotlib/UPX değil,
# onlar sadece ayrı, meşru optimizasyonlardı).
#
# `kivy_deps.angle` tam bu yüzden zaten pip ile kuruluyordu ama hiç
# bağlanmamıştı: ANGLE, OpenGL ES çağrılarını DirectX'e çevirip gerçek GPU
# olmadan da 2.0+ uyumlu bir bağlam sağlıyor. `KIVY_GL_BACKEND=angle_sdl2`
# Kivy'ye pencere+GL sağlayıcısı olarak ANGLE'ı kullanmasını söylüyor;
# native "GDI Generic" sürücüsüne hiç dokunmuyor.
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

if IS_WINDOWS:
    from kivy_deps import sdl2, glew, angle

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

# KivyMD kendi içinde .kv dosyaları, fontlar ve ikonlar taşıyor; PyInstaller
# bunları normal .py taramasıyla bulamaz, collect_all ile açıkça toplanıyor.
# (Bu satır yukarıdaki KIVY_GL_BACKEND notundaki çökmeyi tetikleyen satırdır.)
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
        *collect_submodules("keyring.backends"),
        *kivymd_hidden,
    ],
    hookspath=[],
    runtime_hooks=[],
    # Kullanılmayan ağır bağımlılıklar. Build artık requirements-runtime.txt
    # kullandığından matplotlib/kivy_garden.matplotlib/scipy zaten hiç pip
    # install edilmiyor (bkz. o dosyanın başlığı) — bu satırlar savunma
    # amaçlı kalıyor: biri yanlışlıkla tam requirements.txt'i kurarsa bile
    # (flake8, pycodestyle, pyflakes, mccabe dahil — bunlar requirements-
    # dev.txt'te) hiçbiri pakete sızmasın.
    #   * matplotlib/kivy_garden/mpl_toolkits/scipy: yukarıdaki nota bak.
    #   * flake8, pycodestyle, pyflakes, mccabe: lint araçları, çalışma
    #     zamanında hiç gerekmiyor.
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
    # Linux'ta icon= parametresinin hiçbir etkisi yok (yukarıdaki nota bak);
    # None vermek PyInstaller'ı .ico dosyasını Windows/macOS formatı olarak
    # ayrıştırmaya zorlamaktan kaçınıyor.
    icon="assets/icon.ico" if IS_WINDOWS else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    # angle.dep_bins de paketleniyor: son kullanıcının makinesinde de GPU/
    # sürücü zayıf çıkarsa (özellikle sanal makine/RDP oturumları) uygulama
    # aynı ANGLE geri dönüşünü çalışma anında kullanabilsin diye.
    # (sdl2/glew/angle yalnızca Windows'ta import edildi — Linux'ta bundle
    # edilecek ayrı bir DLL/Tree yok, Kivy'nin kendi SDL2'si yeterli.)
    *([Tree(p) for p in sdl2.dep_bins + glew.dep_bins + angle.dep_bins]
      if IS_WINDOWS else []),
    strip=False,
    upx=False,   # EXE'deki ile aynı gerekçe (hız + numpy/pandas bozulması)
    name="Archlence",
)
