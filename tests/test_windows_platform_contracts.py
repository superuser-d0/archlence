"""Windows'ta gerçekten koşması gereken platform sözleşmeleri.

BU DOSYANIN AMACI, "Windows'ta test edildi" iddiasını mock'tan ÖLÇÜME
çevirmek. İki ayrı test sınıfı var ve ayrım bilinçli:

  * Platformdan BAĞIMSIZ koşanlar — mantık her yerde aynı, ama kırıldığında
    bedeli Windows'ta ödenir (ASCII dışı profil yolu, uzun yol, dosya kilidi,
    DPAPI yarış dalı). Bunlar geliştirme makinesinde de koşar, yani bir
    regresyon Windows CI'yı beklemeden yakalanır.

  * Yalnız Windows'ta koşanlar (`skipUnless(os.name == "nt")`) — gerçek
    `CryptProtectData`/`CryptUnprotectData` çağrısı. Bu yol BUGÜNE KADAR
    HİÇBİR YERDE ÇALIŞMADI: `tests/test_key_provider.py`'deki DPAPI testleri
    sahte bir protector enjekte ediyor, yani doğrulanan şey sarmalayıcı
    mantığıydı, Windows API'sinin kendisi değil. Uygulama Windows'ta açıldığında
    gerçek yolu kullanıyor ama açılış smoke testi boş bir profilde herhangi bir
    şifreleme/çözme tetiklemeyebilir — dolayısıyla ortada deterministik bir
    kanıt yoktu.

GERÇEK MAKİNE GEREKTİRDİĞİ İÇİN BURADA OLMAYANLAR (ayrı bir tur):
SmartScreen/Defender itibarı, DPAPI'nin BAŞKA bir Windows kullanıcısı
tarafından çözülememesi, yeniden başlatma sonrası kalıcılık, gerçek DPI
ölçekleme, IME/klavye davranışı, yönetici olmayan kullanıcıyla kurulum.
Bunların hiçbiri burada "geçti" sayılmaz.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from utils.key_provider import DpapiKeyProvider, FileKeyProvider


NON_ASCII_PROFILE = "Çağrı Şıkğüöİ"


class _FakeProtector:
    """DPAPI'nin şeklini taklit eder: korunmuş blob ham anahtar DEĞİLDİR."""

    def protect(self, data):
        return b"protected:" + data[::-1]

    def unprotect(self, data):
        if not data.startswith(b"protected:"):
            raise OSError("tampered")
        return data[len(b"protected:"):][::-1]


class KeyCreationRaceContract(unittest.TestCase):
    """Anahtar oluşturma yarışını KAYBEDEN, diskteki anahtarı almalı.

    `FileKeyProvider` bunu `os.link` sıralamasıyla çözüyor ve kendi
    dokümantasyonunda "sessiz anahtar imhası" diye anlatıyor: kaybeden kendi
    anahtarıyla devam ederse, o anahtarla şifrelenen her şey süreç kapandığında
    kalıcı olarak okunamaz olur.

    Yarış teorik değil. `utils/key_provider.py`'nin kendi notu şunu söylüyor:
    "açılışta kripto ısıtma thread'i ile veri thread'i ilk şifre çözmeyi aynı
    anda tetikleyebilir". Windows'ta o yolun sağlayıcısı `DpapiKeyProvider`.
    """

    def _losing_creation(self, provider_factory):
        """Dosya ZATEN varken `_create_atomically` — yarışı kaybeden dal.

        `get_or_create_key`'in `load_key()` kontrolü ile `os.link` arasına
        giren ikinci yazarın gördüğü durum tam olarak budur.
        """
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "encryption.key")
            winner = provider_factory(path).get_or_create_key()
            loser = provider_factory(path)
            returned = loser._create_atomically(os.urandom(32))
            return winner, returned, loser.load_key()

    def test_file_provider_loser_returns_the_stored_key(self):
        winner, returned, on_disk = self._losing_creation(FileKeyProvider)
        self.assertEqual(returned, winner)
        self.assertEqual(on_disk, winner)

    def test_dpapi_provider_loser_returns_the_stored_key(self):
        winner, returned, on_disk = self._losing_creation(
            lambda path: DpapiKeyProvider(path, protector=_FakeProtector()))
        self.assertEqual(
            returned, winner,
            "yarışı kaybeden, diske hiç yazılmamış kendi anahtarını döndürdü — "
            "onunla şifrelenen veri kalıcı olarak okunamaz olur",
        )
        self.assertEqual(on_disk, winner)

    def test_dpapi_provider_winner_still_returns_its_own_key(self):
        """Düzeltme yarışı çözerken normal yolu bozmamalı."""
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "encryption.key")
            provider = DpapiKeyProvider(path, protector=_FakeProtector())
            created = provider.get_or_create_key()
            self.assertEqual(provider.load_key(), created)
            self.assertEqual(
                DpapiKeyProvider(path, protector=_FakeProtector()).load_key(),
                created)


class NonAsciiAndLongProfilePaths(unittest.TestCase):
    """Profil yolu ASCII dışı ya da çok uzunken tam tur çalışmalı.

    `ARCHLENCE_HOME` üretimde de var olan bir override (utils/app_paths.py);
    testin icat ettiği bir kapı değil. Zincirin tamamı ölçülüyor: yol çözümü →
    SQLite dosyası → anahtar dosyası → şifreli yazma → okuma.
    """

    def _round_trip(self, root):
        """Verilen kökte hesap açıp şifreli tutarı geri okur."""
        with mock.patch.dict(os.environ, {"ARCHLENCE_HOME": str(root)}):
            from utils.app_paths import data_dir

            resolved = Path(data_dir())
            os.makedirs(resolved, exist_ok=True)
            db_path = resolved / "finance.db"
            key_path = resolved / "encryption.key"
            key = FileKeyProvider(str(key_path)).get_or_create_key()

            with mock.patch("database.db.DB_NAME", str(db_path)), \
                    mock.patch("utils.crypto._get_aead_key", return_value=key):
                from database.init_db import initialize_database
                from services.account_service import AccountService
                from services.transaction_service import TransactionService

                initialize_database()
                account_id = AccountService.create_account(
                    "Türkçe Hesap", "checking", initial_balance=1000.0)
                TransactionService.add_transaction(
                    account_id, 249.99, "expense", "Market", "Şırınga & çilek",
                    detect_subscription=False)
                balance = AccountService.get_account(account_id)["balance"]
                rows = TransactionService.get_recent_for_account(
                    account_id, limit=None)
        return db_path, key_path, balance, rows

    def test_non_ascii_profile_directory_round_trips(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / NON_ASCII_PROFILE / "Archlence"
            db_path, key_path, balance, rows = self._round_trip(root)

            self.assertTrue(db_path.is_file(), "veritabanı ASCII dışı yolda açılmadı")
            self.assertTrue(key_path.is_file(), "anahtar ASCII dışı yolda yazılmadı")
            self.assertAlmostEqual(balance, 1000.0 - 249.99, places=2)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0]["amount"], 249.99, places=2)


            self.assertEqual(rows[0]["description"], "Şırınga & çilek")

    def test_deep_profile_directory_round_trips(self):
        """Windows'ta 260 karakter sınırı — uzun ama gerçekçi bir profil yolu.

        Sınırı AŞMAYI hedeflemiyoruz (o zaman testin kendisi ortama bağımlı
        olurdu); sınıra YAKLAŞAN bir yolun çalıştığını sabitliyoruz.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            for _ in range(4):
                root = root / ("u" * 40)
            db_path, _key, balance, rows = self._round_trip(root / "Archlence")
            self.assertTrue(db_path.is_file())
            self.assertAlmostEqual(balance, 1000.0 - 249.99, places=2)
            self.assertEqual(len(rows), 1)


class BackupSurvivesAnOpenDatabase(unittest.TestCase):
    """Yedekleme/geri yükleme, veritabanı KULLANILDIKTAN sonra çalışmalı.

    Windows'ta açık bir handle `os.replace`/`os.rename`'i `PermissionError`
    ile düşürür — Linux'ta düşürmez. `database/init_db.py::initialize_database`
    bağlantıyı her çıkış yolunda kapatmayı tam da bu yüzden dert ediyor
    ("Windows'ta ise finance.db üzerinde duran bir kilit, yani sonraki
    restore/rename/silme adımını bloklardı"). O gerekçe bugüne kadar yalnız
    yorumdaydı; burada ölçülüyor.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archlence-winlock-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / "finance.db"
        self.key_path = self.root / "encryption.key"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)

        self._db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self._key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key)
        self._db_patch.start()
        self._key_patch.start()
        self.addCleanup(self._db_patch.stop)
        self.addCleanup(self._key_patch.stop)

        from database.init_db import initialize_database
        initialize_database()

    def test_backup_and_restore_after_real_database_use(self):
        from services.account_service import AccountService
        from services.backup_service import create_backup, restore_backup
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Kilit", "checking", initial_balance=5000.0)
        TransactionService.add_transaction(
            account_id, 100.0, "expense", "Market", "x",
            detect_subscription=False)

        package = self.root / "yedek.archlence-backup"
        create_backup(package, "cok-guclu-yedek-parolasi-2026", db_path=self.db_path,
                      key_path=self.key_path)
        self.assertTrue(package.is_file())


        TransactionService.add_transaction(
            account_id, 250.0, "expense", "Market", "y",
            detect_subscription=False)
        self.assertAlmostEqual(
            AccountService.get_account(account_id)["balance"], 4650.0, places=2)

        restore_backup(package, "cok-guclu-yedek-parolasi-2026", db_path=self.db_path,
                       key_path=self.key_path)


        self.assertAlmostEqual(
            AccountService.get_account(account_id)["balance"], 4900.0, places=2)


        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions").fetchone()[0]
        self.assertEqual(count, 1)


@unittest.skipUnless(os.name == "nt", "gerçek DPAPI yalnız Windows'ta var")
class RealWindowsDpapi(unittest.TestCase):
    """GERÇEK `CryptProtectData`/`CryptUnprotectData` — sahte protector YOK.

    Bu sınıf yalnız Windows runner'ında koşar; Linux'ta atlanır ve atlanmış
    bir test HİÇBİR ŞEY kanıtlamaz. Kapsamı da sınırlı: aynı kullanıcı, aynı
    oturum. Anahtarın BAŞKA bir Windows kullanıcısı tarafından çözülemediği ve
    yeniden başlatma sonrası açılabildiği burada DEĞİL, gerçek makinede
    doğrulanacak.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archlence-dpapi-")
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "encryption.key.dpapi")


    CRYPTPROTECT_LOCAL_MACHINE = 0x4

    def test_key_is_never_protected_with_machine_scope(self):
        """Kullanıcılar arası izolasyonun MEKANİZMASINI sabitler.

        İkinci bir Windows hesabıyla uçtan uca koşum bu makinede yapılamadı
        (tek etkin normal hesap var). Yapılabilen ve aslında daha kalıcı olan
        şey bu: bayrağın hiçbir zaman verilmediğini DAVRANIŞSAL olarak
        ölçmek. Kaynak metni aramak yetmezdi — burada gerçek
        `CryptProtectData` çağrısı araya girilerek `dwFlags` yakalanıyor.

        NE KANITLAR: Windows kendi sözleşmesi gereği blob'u çağıran kullanıcı
        hesabına bağlar; başka bir kullanıcı çözemez.
        NE KANITLAMAZ: Windows'un kendi sözleşmesine uyduğunu (işletim
        sistemine güveniyoruz) ve gerçek bir ikinci hesapla koşulduğunu.

        Asıl değeri regresyona karşı: biri ileride "makinedeki servis de
        okusun" diye bu bayrağı eklerse, sessizce tüm kullanıcılara açılmak
        yerine bu test kırmızıya döner.
        """
        import ctypes
        from unittest import mock as _mock
        from utils.key_provider import _WindowsDpapi

        real = ctypes.windll.crypt32.CryptProtectData
        captured = {}

        def _spy(*args):


            captured["flags"] = args[5]
            return real(*args)

        with _mock.patch.object(
            ctypes.windll.crypt32, "CryptProtectData", _spy
        ):
            _WindowsDpapi().protect(os.urandom(32))

        self.assertIn(
            "flags", captured,
            "CryptProtectData hiç çağrılmadı — test bir şey ölçmedi",
        )
        self.assertEqual(
            captured["flags"] & self.CRYPTPROTECT_LOCAL_MACHINE, 0,
            "anahtar MAKİNE kapsamıyla korunuyor: makinedeki her Windows "
            "kullanıcısı çözebilir",
        )

    def test_unprotect_also_stays_in_user_scope(self):
        """Çözme tarafı da bayraksız olmalı; asimetri sessiz sürprizdir."""
        import ctypes
        from unittest import mock as _mock
        from utils.key_provider import _WindowsDpapi

        dpapi = _WindowsDpapi()
        blob = dpapi.protect(os.urandom(32))
        real = ctypes.windll.crypt32.CryptUnprotectData
        captured = {}

        def _spy(*args):
            captured["flags"] = args[5]
            return real(*args)

        with _mock.patch.object(
            ctypes.windll.crypt32, "CryptUnprotectData", _spy
        ):
            dpapi.unprotect(blob)

        self.assertIn("flags", captured)
        self.assertEqual(
            captured["flags"] & self.CRYPTPROTECT_LOCAL_MACHINE, 0
        )

    def test_protect_unprotect_round_trip(self):
        from utils.key_provider import _WindowsDpapi

        dpapi = _WindowsDpapi()
        secret = os.urandom(32)
        blob = dpapi.protect(secret)
        self.assertNotEqual(blob, secret, "korunmuş blob ham anahtarı taşıyor")
        self.assertNotIn(secret, blob, "ham anahtar blob'un içinde düz duruyor")
        self.assertEqual(dpapi.unprotect(blob), secret)

    def test_tampered_blob_is_rejected(self):
        from utils.key_provider import _WindowsDpapi

        dpapi = _WindowsDpapi()
        blob = bytearray(dpapi.protect(os.urandom(32)))
        blob[-1] ^= 0xFF
        with self.assertRaises(OSError):
            dpapi.unprotect(bytes(blob))

    def test_key_survives_a_new_provider_instance(self):
        """Süreç yeniden başlatmasının test içindeki karşılığı."""
        created = DpapiKeyProvider(self.path).get_or_create_key()
        self.assertEqual(len(created), 32)
        self.assertEqual(DpapiKeyProvider(self.path).get_or_create_key(),
                         created)

    def test_stored_file_never_contains_the_raw_key(self):
        created = DpapiKeyProvider(self.path).get_or_create_key()
        with open(self.path, "rb") as stream:
            stored = stream.read()
        self.assertNotEqual(stored, created)
        self.assertNotIn(created, stored)

    def test_platform_factory_selects_dpapi_and_reports_it_as_secure(self):
        from utils.key_provider import create_platform_key_provider

        provider = create_platform_key_provider(self.temp.name)
        self.assertEqual(provider.status.method, "Windows DPAPI")
        self.assertTrue(provider.status.secure_store)
        self.assertIsNone(provider.status.warning)


        key = provider.get_or_create_key()
        self.assertEqual(len(key), 32)
        self.assertEqual(
            create_platform_key_provider(self.temp.name).get_or_create_key(),
            key)


if __name__ == "__main__":
    unittest.main()
