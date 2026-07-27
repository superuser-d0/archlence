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
