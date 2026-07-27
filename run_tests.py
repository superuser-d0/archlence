import os
import sys
import unittest

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

loader = unittest.TestLoader()
suite = loader.discover("tests")
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Eskiden burada sys.exit yoktu: başarısız test bile exit code 0 ile
# bitiyordu. Yereldeki geliştiriciyi etkilemez (çıktıyı gözle okur) ama
# CI'daki bir "zorunlu" kontrolü tamamen anlamsız kılar — build hiçbir zaman
# kırmızı olamaz. Faz 0 (CI'a gerçek test job'ı) bu düzeltme olmadan sahte bir
# güvenlik hissi verirdi.
sys.exit(0 if result.wasSuccessful() else 1)
