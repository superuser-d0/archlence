# Antigravity IDE — Mekanik Temizlik Görevleri (Finora)

Bu dosyadaki görevler sırayla, **her görev ayrı bir git commit'i** olacak şekilde
yapılmalı. Her görevden sonra doğrulama komutu çalıştırılıp geçtiği görülmeden
sonraki göreve geçilmemeli.

Ortak doğrulama komutu (proje kökünde):

```
.venv/bin/python test_startup_import.py
```

---

## Görev 1 — Ölü tek seferlik scriptleri sil

Aşağıdaki 8 dosya, geçmişte tek seferlik düzeltmeler için yazılmış ve artık
tamamen işlevsiz scriptlerdir (bazıları sabit satır numaralarına, bazıları
artık var olmayan transcript dosyalarına bağımlı). Hiçbir yerden import
edilmiyorlar. Silinecekler:

- `extract.py`
- `split_mixins.py`
- `remove_extracted.py`
- `fix_indent.py`
- `fix_indentation.py`
- `fix_metrics_goals.py`
- `get_diff.py`
- `get_first_kv.py`

Doğrulama: ortak doğrulama komutu + `grep -rn "extract\|split_mixins\|remove_extracted\|fix_indent\|fix_metrics\|get_diff\|get_first_kv" --include="*.py" .` çıktısında bu modüllere import kalmadığını görmek.

## Görev 2 — Test dosyalarını `tests/` klasörüne taşı

`tests/` klasörü oluştur ve kökteki şu dosyaları içine taşı:

- `test_crypto.py`
- `test_gui.py`
- `test_ids.py`
- `test_main_metrics.py`
- `test_metrics.py`
- `test_startup_import.py`

Testler proje kökünden import yaptığı için (`import main`, `from utils.crypto
import ...` vb.) her test dosyasının en üstüne, mevcut importlardan ÖNCE şu
bloğu ekle (yoksa):

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Ayrıca boş bir `tests/__init__.py` oluştur.

Doğrulama: `.venv/bin/python tests/test_startup_import.py` geçmeli.
(Bu görevden sonra ortak doğrulama komutunun yolu artık `tests/` altındadır.)

## Görev 3 — Paket `__init__.py` düzeltmeleri

- `database/_init_.py` dosyasının adı yanlış (tek alt çizgi). `database/__init__.py`
  olarak yeniden adlandır (dosya boş, içeriği değişmeyecek).
- Şu klasörlerde `__init__.py` yoksa boş olarak oluştur: `mixins/`, `services/`,
  `ui/`, `screens/`, `security/`, `utils/`.

Doğrulama: ortak doğrulama komutu.

## Görev 4 — Mixin dosyalarındaki kopyala‑yapıştır importları ayıkla

`mixins/asset_mixin.py`, `mixins/calculator_mixin.py`, `mixins/debt_mixin.py`,
`mixins/transaction_mixin.py` dosyalarının başındaki import blokları birbirinin
kopyası ve çoğu import o dosyada hiç kullanılmıyor.

Her dosya için: dosyada gerçekten kullanılmayan importları sil. Yeni import
EKLEME, sadece kullanılmayanları kaldır. Emin olunamayan (ör. `.kv` dosyası
üzerinden dolaylı kullanılabilecek widget sınıfı) importlara dokunma.

Doğrulama: ortak doğrulama komutu + `.venv/bin/python -m py_compile mixins/*.py`.

## Görev 5 — BIST100 listesini ayrı veri modülüne çıkar

- `data/` klasörü ve boş `data/__init__.py` oluştur.
- `mixins/asset_mixin.py` içindeki `BIST100_STOCKS = [...]` listesini (yaklaşık
  100 tuple'lık blok, dosyanın başında) kes ve yeni `data/bist100.py` dosyasına
  taşı. Liste içeriğini birebir koru, hiçbir sembolü değiştirme.
- `mixins/asset_mixin.py`'ye `from data.bist100 import BIST100_STOCKS` ekle.
- Projede başka yerde `BIST100_STOCKS` kullanımı varsa (`grep -rn BIST100_STOCKS
  --include="*.py" .`) aynı import'a yönlendir.

Doğrulama: ortak doğrulama komutu + `.venv/bin/python -c "from data.bist100 import BIST100_STOCKS; print(len(BIST100_STOCKS))"` — sayı taşıma öncesiyle aynı olmalı.

## Görev 6 — Mini servisleri `services/queries.py` altında birleştir

Üç küçük dosya tek dosyada toplanacak; sınıf adları ve metod imzaları
DEĞİŞMEYECEK, sadece yer değiştirecekler:

- `services/category_service.py` → `CategoryService` sınıfı
- `services/transaction_history_service.py` → `TransactionHistoryService` sınıfı
- `screens/dashboard.py` → `DashboardService` sınıfı (bu dosya ekran değil,
  yanlış klasörde duran bir servis)

Yapılacaklar:

1. `services/queries.py` oluştur, üç sınıfı olduğu gibi buraya taşı
   (ortak `from database.db import get_connection` import'u tek sefer yazılır).
2. Eski üç dosyanın içeriğini geriye dönük uyumluluk shim'iyle değiştir; örn.
   `services/category_service.py` içeriği sadece şu olacak:
   `from services.queries import CategoryService  # geriye dönük uyumluluk`
   (diğer ikisi için de aynı kalıp, kendi sınıf adlarıyla).
3. Projedeki mevcut importlara DOKUNMA — shim'ler sayesinde çalışmaya devam
   ederler.

Doğrulama: ortak doğrulama komutu + `grep -rn "category_service\|transaction_history_service\|screens.dashboard" --include="*.py" .` ile listelenen her import'un hâlâ çalıştığını
`.venv/bin/python -c "from services.category_service import CategoryService; from services.transaction_history_service import TransactionHistoryService; from screens.dashboard import DashboardService"` komutuyla göster.

---

## Yapılmayacaklar (bilerek kapsam dışı — bunlara dokunma)

- `main.py`'yi bölme/küçültme
- `utils/crypto.py`, `security/security_service.py` ve şifrelemeyle ilgili her şey
- `mixins/` dosyalarını birbirleriyle birleştirme
- Finansal hesaplama içeren kod (`calculator_mixin.py` hesapları,
  `services/asset_service.py` kâr/zarar mantığı)

Bu kısımlar ayrıca ele alınıyor; çakışma olmaması için bu oturumda değiştirilmemeli.
