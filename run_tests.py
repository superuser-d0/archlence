import sys
import unittest

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
