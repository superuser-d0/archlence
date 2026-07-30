import os
import sys
import tempfile
import unittest

# ── Konsol kodlaması: Türkçe metin Windows'ta süreci ÖLDÜRMESİN ─────────────
# Windows'ta `sys.stdout`/`sys.stderr` konsolun kod sayfasını kullanır (çoğu
# Türkçe kurulumda cp1252). Bu kod sayfası 'ı', 'ğ', 'ş' gibi karakterleri
# KODLAYAMAZ ve `print()` bir `UnicodeEncodeError` fırlatır.
#
# Bu teorik bir incelik değil: uygulamanın hata mesajları Türkçe ve bunların
# çoğu `except` bloklarının İÇİNDE basılıyor. Orada `print` patlayınca hata
# yutulmuyor — istisna dışarı sızıp asıl işlemi öldürüyor. Windows CI'da
# ampirik olarak ölçüldü: `TransactionService.add_transaction` içindeki
# "Abonelik radarına yazılamadı" satırı, abonelik radarı hata verdiğinde
# İŞLEMİN TAMAMINI kaybettiriyordu (tests/test_subscription_interceptor.py
# ::test_radar_failure_does_not_lose_the_transaction Windows'ta bu yüzden
# kırmızıydı, Linux'ta yeşildi).
#
# errors="replace": kodlanamayan karakter '?' olur ama süreç ASLA durmaz.
# Teşhis çıktısı kısmen bozulabilir; veri kaybetmekten sonsuz kez iyidir.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        # Paketlenmiş pencereli derlemede (console=False) bu akışlar None ya
        # da yeniden yapılandırılamaz olabilir; o durumda zaten yazılmıyor.
        pass

# Kivy, `import kivy` sırasında sys.stderr'i KENDİ akışıyla değiştiriyor
# (.venv/.../kivy/logger.py:631 -> `sys.stderr = ProcessingStream("stderr",
# Logger.warning)`, yalnızca KIVY_NO_CONSOLELOG ayarlı DEĞİLSE). O akış kendisine
# yazılan her şeyi Kivy'nin logger'ına huniliyor.
#
# Sonuç (v0.0.1'de ölçüldü): tam paket koşusunda Kivy çekirdeği ilk kez derinden
# import edildiği anda — ~69. test civarı — unittest'in raporu bu huniye düşüp
# KAYBOLUYORDU. Kaybolanlar: kalan ~505 testin adları, assertion mesajları,
# traceback'ler ve en önemlisi "Ran N tests" + "OK"/"FAILED (failures=N)" özeti.
# Testlerin hepsi gerçekten koşuyor ve çıkış kodu DOĞRU kalıyordu (kasıtlı bir
# hatayla doğrulandı: exit 1), ama log'a bakan hiç kimse NEYİN neden
# başarısız olduğunu göremiyordu — CI çıktısı yeşil bir koşuyla ayırt edilemez
# hâle geliyordu.
#
# Çözüm: gerçek akışı, herhangi bir Kivy importundan ÖNCE yakala ve runner'a
# açıkça ver. Kivy'nin kendi davranışına dokunmuyoruz (kendi [INFO]/[CRITICAL]
# satırları görünmeye devam etsin); yalnızca test raporunun hedefini sabitliyoruz.
_REAL_STDERR = sys.stderr

# Discovery HERHANGİ bir test dosyasını içe aktarmadan önce set edilmeli.
# main.py'yi import eden birden fazla test dosyası var; main.py aynı süreçte
# yalnızca İLK kez gerçekten çalışır (sys.modules önbelleği), sonraki
# `import main` çağrıları üst-seviye kodu tekrar ÇALIŞTIRMAZ. Yani bu
# değişkeni yalnızca tek tek dosyaların kendi başına set etmesine güvenmek,
# "hangi dosya önce import edildi" sırasına bağlı kırılgan bir davranış
# üretirdi (bkz. docs/ROADMAP.md Faz 1 madde 2 — main.py artık gerçek
# pencere kurulamadığında yalnızca bu bayrak açıkça set edildiyse sessizce
# stub sınıflara düşüyor, aksi hâlde görünür şekilde patlıyor).
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")

# Aynı sıralama kırılganlığı bir kademe daha derinde de var: main.py'nin
# kendi ARCHLENCE_HEADLESS bloğu SDL_VIDEODRIVER=dummy / KIVY_WINDOW=sdl2
# set ediyor (bkz. main.py, docs/ROADMAP.md Faz 1 madde 2 — CI'da display
# sunucusu hiç yokken Kivy'nin ham x11 sağlayıcısı süreci OS seviyesinde
# çökertiyordu). Ama Kivy kendi `kivy_options` sözlüğünü, `kivy` paketi
# İLK import edildiğinde (main.py'den bağımsız olarak) bir kere okuyup
# sabitliyor. Bazı mixin dosyaları (ör. mixins/transaction_mixin.py) kendi
# tepesinde `from kivy.clock import Clock` yapıyor ve bir test METODU
# içinde main.py hiç import edilmeden önce çalışabiliyor — bu durumda
# main.py'nin env değişkeni ayarı hiçbir zaman devreye giremeden kivy_options
# çoktan sabitlenmiş oluyor (ampirik olarak PR #16'nın CI çalışmasında
# doğrulandı: KIVY_WINDOW=sdl2 set edilmesine rağmen ham x11 sağlayıcısı
# yine de denendi). Tek güvenilir nokta: test discovery'den önce, burada.
if os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in ("1", "true", "yes"):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("KIVY_WINDOW", "sdl2")

# utils/app_paths.py::data_dir() artık gerçek şeyler barındırıyor: bir
# şifreleme anahtarı (utils/crypto.py::_get_aead_key, PR #22). O anahtar
# `data_dir()`'ın çözdüğü GERÇEK dizine yazılır — test suite'inin yüzlerce
# çağrısı encrypt()/decrypt()'i (çoğu dolaylı, servis testleri üzerinden)
# tetikliyor, yani bu satır olmadan HER test çalıştırmasında geliştiricinin
# gerçek `~/.local/share/Archlence/encryption.key` dosyasına dokunulurdu —
# main.py'nin crash.log'unun zaten yaptığı gibi (bkz. PR #18), ama bu sefer
# gerçek kripto anahtar malzemesiyle, kabul edilebilirliği çok daha düşük.
# Test discovery'den ÖNCE, tek bir paylaşılan geçici dizine yönlendiriyoruz
# — tüm suite aynı (atılabilir) anahtarda buluşuyor, kimse gerçek ev
# dizinine dokunmuyor.
if "XDG_DATA_HOME" not in os.environ:
    _sandbox = tempfile.mkdtemp(prefix="archlence-test-xdg-")
    os.environ["XDG_DATA_HOME"] = os.path.join(_sandbox, "data")
    os.environ["XDG_CACHE_HOME"] = os.path.join(_sandbox, "cache")
    os.environ["XDG_STATE_HOME"] = os.path.join(_sandbox, "state")

loader = unittest.TestLoader()
suite = loader.discover("tests")
runner = unittest.TextTestRunner(verbosity=2, stream=_REAL_STDERR)
result = runner.run(suite)

# Eskiden burada sys.exit yoktu: başarısız test bile exit code 0 ile
# bitiyordu. Yereldeki geliştiriciyi etkilemez (çıktıyı gözle okur) ama
# CI'daki bir "zorunlu" kontrolü tamamen anlamsız kılar — build hiçbir zaman
# kırmızı olamaz. Faz 0 (CI'a gerçek test job'ı) bu düzeltme olmadan sahte bir
# güvenlik hissi verirdi.
sys.exit(0 if result.wasSuccessful() else 1)
