"""docs/ROADMAP.md Faz 1 madde 4 — kullanıcı verisi için yol çözümleyici.

Kullanıcı verisi (finance.db, config JSON), önbellek (marka ikonları) ve
log (crash.log) dosyalarının NEREDE tutulacağını `platformdirs` üzerinden
çözer. Paketlenmiş bir Windows kurulumunda uygulamanın kendi kurulum
dizini (`Program Files` altı) genelde salt-okunur — artık oraya yazmıyoruz.

Bu modül yalnızca YOL ÇÖZÜMLEMESİ yapar, hiçbir I/O yan etkisi yok
(`ensure_exists=False`): salt import etmek ya da bu fonksiyonları çağırmak
gerçek bir dizin yaratmaz — bu yüzden test suite'inin her `database.db`
import edişinde geliştiricinin gerçek ev dizininde klasör oluşmaz. Gerçek
dizin oluşturma, o dizine ilk kez GERÇEKTEN yazacak kod tarafında yapılır
(bkz. `database/db.py::get_connection`).

Eski konumlardan yeni konuma tek seferlik taşıma `migrate_legacy_path()`
ile yapılır; NE'nin taşınacağına (hangi dosya, ne zaman) çağıran karar
verir — bu modül yalnızca "kaynakta var, hedefte yok" durumunda güvenli
taşımanın mekaniğini sağlar.
"""
import os
import shutil
import sys
from typing import cast

from platformdirs import PlatformDirs

APP_NAME = "Archlence"


def _dirs() -> PlatformDirs:
    return PlatformDirs(appname=APP_NAME, appauthor=False, ensure_exists=False)


def resource_dir() -> str:
    """Uygulamayla birlikte paketlenen, SALT-OKUNUR kaynakların (`ui/*.kv`,
    `assets/*`) gerçekte durduğu dizin.

    Gerçek bir Windows kurulumunda ampirik olarak doğrulanan çökme:
    `main.py::build()`'daki `Builder.load_file("ui/tools.kv")` gibi çağrılar
    ve `database/db.py::NETWORK_LOGOS` gibi sabitler, hep GÖRELİ yol
    kullanıyordu — yani çalışma dizininin (`cwd`) kurulum klasörüyle AYNI
    olduğunu VARSAYIYORDU. Bu varsayım geliştirmede doğru (uygulama repo
    kökünden çalıştırılır) ama paketlenmiş bir `.exe`, Başlat Menüsü/
    masaüstü kısayolundan ya da Inno Setup'ın kurulum-sonu "Başlat"
    adımından açıldığında YANLIŞ — Windows/Inno Setup çalışma dizinini
    kurulum klasörüyle aynı yapacağını GARANTİ ETMEZ. Sonuç: gerçek bir
    kullanıcı kurulumunda `FileNotFoundError: [Errno 2] No such file or
    directory: 'ui/tools.kv'` ile açılışta çöküyordu.

    `sys._MEIPASS`, PyInstaller'ın (paketlenmiş, `sys.frozen` gerçek
    olduğunda) `datas=[...]` ile gömülen dosyaları GERÇEKTE koyduğu
    dizindir — `.exe`'nin kendisiyle AYNI dizin OLMAYABİLİR (PyInstaller
    6.x varsayılan olarak `_internal` alt klasörünü kullanıyor, bkz.
    archlence.spec). `__file__` ya da `os.getcwd()`'e güvenmek burada
    YANLIŞ olurdu — ikisi de paketlenmiş bir yapıda güvenilir değil.
    """
    if getattr(sys, "frozen", False):
        # `_MEIPASS`'i PyInstaller ÇALIŞMA ZAMANINDA `sys`'e ekler; standart
        # `sys` tipinde böyle bir alan yok ve tip denetleyicinin bunu
        # bilmemesi normal. `getattr` + `cast` yalnızca "frozen yolunda burada
        # bir `str` bekliyoruz" demenin yolu; varsayılan değer VERİLMİYOR,
        # çünkü frozen bir yapıda alanın olmaması gerçek bir arıza olurdu ve
        # sessizce yanlış bir köke düşmek paketlenmiş uygulamayı bozardı.
        return cast(str, getattr(sys, "_MEIPASS"))
    # utils/app_paths.py -> utils/ -> repo kökü.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Tüm kullanıcı dizinlerini tek bir köke yönlendiren AÇIK geçersiz kılma.
#
# NEDEN GEREKLİ: `platformdirs` Windows'ta yolları ORTAM DEĞİŞKENLERİNDEN
# çözmez — `ctypes` varsa (pratikte hep vardır) `SHGetFolderPathW`i çağıran
# `get_win_folder_via_ctypes` kullanılır ve LOCALAPPDATA/APPDATA tamamen YOK
# SAYILIR. Linux/macOS'ta XDG_* değişkenleri işe yarar, Windows'ta yaramaz.
#
# Bunun somut bedeli vardı: test paketi kendini gerçek kullanıcı verisinden
# XDG_* ile ayırıyordu ve bu ayrım Windows'ta HİÇ çalışmıyordu — testler
# geliştiricinin gerçek `%LOCALAPPDATA%\Archlence` dizinine, yani şifreleme
# anahtarının yanına yazıyordu. Windows test job'ı eklenince ortaya çıktı.
#
# Değişken ayarlı DEĞİLSE davranış eskisiyle birebir aynıdır.
HOME_OVERRIDE_ENV = "ARCHLENCE_HOME"


def _override_root() -> str | None:
    root = os.environ.get(HOME_OVERRIDE_ENV, "").strip()
    return root or None


def data_dir() -> str:
    """SQLite veritabanı + JSON config dosyaları için kalıcı kullanıcı verisi."""
    root = _override_root()
    if root:
        return os.path.join(root, "data")
    return _dirs().user_data_dir


def cache_dir() -> str:
    """Marka ikonu gibi yeniden üretilebilir/atılabilir dosyalar için."""
    root = _override_root()
    if root:
        return os.path.join(root, "cache")
    return _dirs().user_cache_dir


def log_dir() -> str:
    """crash.log için."""
    root = _override_root()
    if root:
        return os.path.join(root, "logs")
    return _dirs().user_log_dir


def migrate_legacy_path(old_path: str, new_path: str) -> bool:
    """`old_path`'teki dosyayı `new_path`'e taşır ve `True` döner —
    yalnızca `old_path` gerçekten varsa VE `new_path` henüz yoksa. Diğer
    her durumda hiçbir şey yapmadan `False` döner: taze kurulumda taşınacak
    eski dosya yoktur; `new_path` zaten varsa (önceki bir migration'dan ya
    da başka bir sebepten) kullanıcının GÜNCEL verisinin üzerine eski bir
    kopya asla yazılmaz. İdempotent — art arda çağrılması güvenli."""
    if os.path.exists(new_path) or not os.path.exists(old_path):
        return False
    new_dir = os.path.dirname(new_path)
    if new_dir:
        os.makedirs(new_dir, exist_ok=True)

    # TAŞIMA DEĞİL, KOPYALA + EN İYİ ÇABA SİL. `shutil.move` aynı dosya
    # sisteminde `os.rename`e iner ve bu, KAYNAK DİZİNDE yazma izni ister
    # (dizin girdisini silmek için). Bu fonksiyonun asıl kullanım senaryosu
    # ise tam tersi: kaynak, paketlenmiş bir Windows kurulumunda genelde
    # SALT-OKUNUR olan uygulama kurulum dizini (`Program Files`) — yani
    # madde 4'ün düzeltmek için var olduğu durumun ta kendisi. Salt-okunur
    # bir kaynak dizinle ampirik olarak doğrulandı: `shutil.move`
    # PermissionError fırlatıyordu ve bu, çağrıldığı yerde (build())
    # yakalanmadığı için uygulamayı hiç açılmadan düşürüyordu.
    #
    # Kopyalama başarılı olduktan SONRA eskisini silmeye çalışıyoruz; bu
    # silme başarısız olursa YUTULUYOR: veri güvenle yeni konumda ve
    # yukarıdaki `os.path.exists(new_path)` guard'ı sayesinde bir sonraki
    # açılışta yeniden kopyalanmayacak. Kalan eski dosya bir daha hiç
    # okunmaz — "biraz çöp" ile "uygulama hiç açılmıyor" arasındaki tercih.
    shutil.copy2(old_path, new_path)
    try:
        os.remove(old_path)
    except OSError:
        pass
    return True
