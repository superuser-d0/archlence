# Archlence — v0.0.9 Öncesi Derin Denetim

**Denetim tarihi:** 2026-08-06
**Denetim commit'i:** `d5bd35fd8c59b09ac3293e954101cb81e3c0e0c5`
**Denetim dalı:** `audit/v0.0.9-deep-review` (remote'a push EDİLMEDİ)
**Uygulama sürümü:** 0.0.8 (son etiket `v0.0.8`, `695b179`)

---

## 1. Yönetici özeti

Denetimin çıkış noktası şuydu: *mevcut 699 test ve CI kapıları hangi yanlış
davranışlara izin veriyor?*

Yöntem, test sayısını saymak değil **mutation testing** oldu: korunan davranış
bilerek bozuldu ve testlerin kırmızı olup olmadığı ölçüldü. Bir test, koruduğu
davranış bozulduğunda kırılmıyorsa kanıt sayılmadı.

**14 mutation uygulandı, 13'ü yakalandı, 1'i kaçtı.** Ayrı olarak istisna
kapısına 4 bypass sondası uygulandı; **4'ü de kapıdan görünmeden geçti.**

En önemli iki bulgu, v0.0.6'da bulunan "istisna baseline'ında 44 boş slot"
sorununun **yapısal olarak devam ettiğini** gösteriyor. O sürümdeki düzeltme
tek seferlik bir veri tazelemesiydi; kapının kendisi değişmedi ve aynı durum
kendiliğinden yeniden oluşabiliyor.

Ayrıca kendi yazdığım bir regresyon testinin (v0.0.8, #73) **totolojik** olduğu
ve koruduğunu iddia ettiği davranışı hiç doğrulamadığı tespit edildi.

**Release kararı:** v0.0.9 için P0 bulgusu yok. İki P1 bulgusu var; ikisi de
üretim davranışı değil **kalite kapısı** kusuru — yani kullanıcı verisini bugün
bozmuyorlar, ama gelecekteki kusurların fark edilmeden geçmesine izin veriyorlar.

---

## 2. Kapsam

**İncelenen alanlar**

| Alan | Derinlik |
|---|---|
| Test güvenilirliği / mutation | Tam — 14 mutation, tam suite'e karşı |
| İstisna kapısı (CI gate) | Tam — 4 bypass sondası + slack senaryosu |
| Finansal quantization yolları | Tam — taksit, varlık, borç, karar eşikleri |
| SQLite şema ve migration | Orta — v0.0.1/v0.0.4/v0.0.6 → current |
| Foreign key / referans bütünlüğü | Orta |
| Şifreli alan envanteri | Orta — write-path mutation ile |
| Sürüm/changelog tutarlılığı | Orta |

**İncelenmeyen alanlar** — bkz. bölüm 9.

---

## 3. Ortam

- Platform: Linux (CachyOS), Python 3.14.6 (yerel venv), CI Python 3.12
- Test komutu: `python run_tests.py` (CI ile aynı, `tests.yml:73`)
- Mutation izolasyonu: ayrı `git worktree` (`/tmp/archlence-mut`)
- Eski sürüm DB'leri: `v0.0.1`, `v0.0.4`, `v0.0.6` etiketlerinden ayrı worktree
- Gerçek kullanıcı verisine, anahtarına veya veri dizinine **dokunulmadı**

---

## 4. Metodoloji

1. Temel durum doğrulandı (temiz ağaç, `HEAD == origin/main`).
2. Test suite normal hâliyle koşuldu: **699 test, 2 skip, OK**.
3. Kritik davranışlar için mutation uygulandı, **tam suite** koşuldu.
   - Dar test modülüne karşı koşmak yanıltıcı çıktı: `şifreli-açıklama`
     mutation'ı dar modülde "kaçtı" göründü, tam suite'te yakalandı. Bütün
     sonuçlar tam suite'e karşı yeniden üretildi.
4. Kapılar için ayrıca **sözdizimsel bypass sondaları** uygulandı.
5. Eski sürüm DB'leri üretilip güncel kodla migrate edildi, öncesi/sonrası
   durum karşılaştırıldı.

---

## 5. Test güvenilirliği değerlendirmesi

### 5.1 Mutation sonuçları — YAKALANAN (13)

| Mutation | Hedef | Sonuç |
|---|---|---|
| `remaining_amount` anaparadan → `aylık × kalan` | `transaction_service` | FAILED ×4 |
| Varlık alımı quantize kaldır | `asset_purchase_service` | FAILED ×3 |
| Borç tutarı quantize kaldır | `database/db.py` | FAILED ×2 |
| Kart limiti `fiat()` → float | `account_service` | FAILED ×1 |
| Çekim `ROUND(...,2)` kaldır | `savings_service` | ERROR ×1 |
| Açıklama şifrelemesini atla | `transaction_service` | FAILED ×4 + ERROR |
| Ledger event yazma | `database/db.py` | FAILED ×7 + ERROR |
| "Hesap yok" koruması kaldır | `database/db.py` | FAILED ×2 |
| Cache anahtarından filtre çıkar | `main.py` | FAILED ×2 |
| Cache anahtarından revision çıkar | `main.py` | FAILED ×2 |
| Kategori generation kontrolü kaldır | `main.py` | FAILED ×1 |

Bu 11 davranış için testler **gerçek kanıt** sayılabilir.

### 5.2 Mutation sonuçları — KAÇAN (1)

**Taksit aylık tutarının Decimal quantization'ı.**

`monthly = fiat(decimal_from(amount) / installments)` satırı v0.0.8 öncesindeki
`round(float(amount) / installments, 2)` hâline geri alındığında **699 testin
tamamı geçmeye devam etti.**

Ayrıntı için bulgu **A-3**.

---

## 6. Doğrulanmış bulgular

### A-1 — İstisna kapısı sözdizimsel olarak bypass edilebiliyor

**Severity:** P1
**Durum:** Confirmed
**Etkilenen sürümler:** v0.0.6 – v0.0.8 (kapının eklendiği andan itibaren)
**Etkilenen dosya:** `scripts/audit_exception_handlers.py:97-101`

**Kök neden**

```python
broad = node.type is None or (
    isinstance(node.type, ast.Name)
    and node.type.id in {"Exception", "BaseException"}
)
```

Tespit yalnızca `ast.Name` düğümünü tanıyor. Aşağıdaki üç biçim işlevsel olarak
`except Exception:` ile aynı ama kapıya görünmez:

| Biçim | AST düğümü | Kapı görüyor mu |
|---|---|---|
| `except (Exception,):` | `ast.Tuple` | hayır |
| `except builtins.Exception:` | `ast.Attribute` | hayır |
| `except _Alias:` (`_Alias = Exception`) | `ast.Name`, id `_Alias` | hayır |

`except (Exception, OSError):` gibi gerçekçi bir çoklu-tip yakalaması da aynı
sebeple görünmez.

**Yeniden üretme**

`services/_bypass_probe.py` adında üç sondayı içeren bir dosya eklendi ve kapı
çalıştırıldı:

```
Exception baseline korundu: 144 handler
kapı exit=0
```

Üç yeni geniş handler eklenmiş olmasına rağmen sayı değişmedi.

**Mevcut testlerin neden yakalamadığı**

Kapı, `run_tests.py` içinde değil ayrı bir CI adımında koşuyor ve kendisi test
edilmiyor. Kapının doğru saydığını doğrulayan hiçbir test yok.

**Önerilen sistemik koruma**

- Tespiti `ast.Tuple` elemanlarını ve `ast.Attribute` sonlarını kapsayacak
  şekilde genişlet.
- Alias tespiti için modül düzeyindeki basit atamaları çöz (`X = Exception`).
- Kapının kendisi için bir test dosyası ekle: bilinen bypass biçimlerinin
  **sayıldığını** doğrulasın.

**v0.0.9 için gerekli mi:** Evet — kapı, projenin geniş-handler borcunu
büyütmeme sözünün tek mekanizması.

---

### A-2 — Baseline slack'i sessizce yeniden birikiyor (44-slot mekanizması yapısal)

**Severity:** P1
**Durum:** Confirmed
**Etkilenen dosya:** `scripts/audit_exception_handlers.py:190`

**Kök neden**

```python
additions = current - baseline
if additions or bare: raise SystemExit(1)
```

`Counter` çıkarması yalnızca **fazlalıkları** görür. `baseline > current` durumu
(yani boş slot) hiçbir zaman hata üretmez. Bu, v0.0.6'da bulunan 44 boş slotun
oluşma mekanizmasının ta kendisi ve **hâlâ açık**.

**Yeniden üretme**

```
Adım 1: main.py::set_language içindeki geniş handler daraltıldı
        (İYİ bir değişiklik), baseline güncellenmedi
        -> "Exception baseline korundu: 143 handler"  exit=0

Adım 2: AYNI fonksiyona yeni bir geniş handler eklendi
        -> "Exception baseline korundu: 144 handler"  exit=0
```

Yeni geniş handler **sessizce yutuldu**.

**Etki**

Her handler daraltma işlemi — yani projenin teşvik ettiği iyileştirme — bir
sonraki geniş handler için ücretsiz slot açıyor. Borç azaldıkça kapı zayıflıyor.

**Önerilen sistemik koruma**

Kapı `current == baseline` eşitliğini istesin. Azalma da hata olsun ve
"baseline'ı yeniden üret" mesajı versin. Bu, hem fazlalığı hem slack'i kapatır.

**v0.0.9 için gerekli mi:** Evet — A-1 ile birlikte tek düzeltme turunda.

---

### A-3 — Taksit aylık tutarının quantization'ı hiçbir test tarafından korunmuyor

**Severity:** P2
**Durum:** Confirmed
**Etkilenen dosya:** `tests/test_transaction_service.py:105-141`

**Kök neden**

v0.0.8'de (#73) eklenen `test_uneven_split_never_drifts_from_the_principal`
testinin ikinci assertion'ı **totolojik**:

```python
last       = remaining_amount - monthly * (count - 1)
total_paid = monthly * (count - 1) + last
assert total_paid == principal
```

Cebirsel olarak `total_paid == remaining_amount`, ve bir üst satırda zaten
`remaining_amount == principal` doğrulanmış. Yani ikinci assertion hiçbir yeni
bilgi taşımıyor; **taksitlerin toplamı hiç kontrol edilmiyor.**

**Sonuç:** `monthly`'nin nasıl yuvarlandığı test edilmiyor.

**Ölçülen fark**

`round(float(x)/n, 2)` ile `fiat(decimal_from(x)/n)` yarım-kuruş sınırında
ayrışıyor. Erişilebilir taksit aralığında (1–12) gerçekçi vakalar:

| Tutar | Taksit | `round(float)` | `fiat()` |
|---|---|---|---|
| 100,01 | 2 | 50,01 | **50,00** |
| 100,18 | 4 | 25,05 | **25,04** |
| 100,23 | 6 | 16,71 | **16,70** |
| 100,04 | 8 | 12,51 | **12,50** |
| 100,02 | 12 | 8,33 | **8,34** |

**Mevcut testlerin neden yakalamadığı**

Test vakaları (1000/3, 12500/12, 4999,90/7) ayrışma üretmeyen değerler. Vaka
seçimi yarım-kuruş sınırını hiç zorlamıyor.

**Önerilen sistemik koruma**

- Assertion'ı gerçek toplama dayandır: `monthly × (n−1) + son_taksit == anapara`
  ifadesinde `son_taksit` bağımsız hesaplansın.
- Yukarıdaki ayrışan vakalardan en az birini test vakası olarak ekle.
- Property-based test: her `(anapara, n)` çifti için toplam anaparaya eşit
  olmalı.

**v0.0.9 için gerekli mi:** Evet — üretim kodu doğru, ama koruması yok.

---

### A-4 — Foreign key kısıtı tanımlı ama zorlanmıyor

**Severity:** P2
**Durum:** Confirmed
**Etkilenen dosya:** `database/db.py::get_connection`

**Bulgu**

`transactions.account_id → accounts.id` FK kısıtı şemada **tanımlı**, ama
uygulamanın bağlantısında `PRAGMA foreign_keys = 0` (SQLite varsayılanı).

Doğrudan `INSERT` ile var olmayan bir hesaba işlem yazılabildi; öksüz kayıt
oluştu.

**Neden P1 değil**

Bugün UI'dan erişilebilen tek hesap silme yolu `delete_credit_card` ve o yol
`transactions`, `recurring_payments`, `balance_events` kayıtlarını **elle**
siliyor. Vadesiz hesaplar için silme yolu yok. Yani bugün ulaşılabilir bir
öksüz-kayıt senaryosu bulunamadı.

**Risk**

Tanımlı kısıt, korunuyormuş izlenimi veriyor. İleride bir vadesiz hesap silme
yolu eklenir ve elle cascade unutulursa hiçbir şey yakalamaz.

**Önerilen sistemik koruma**

`get_connection()` içinde `PRAGMA foreign_keys = ON`. Mevcut veride öksüz kayıt
olup olmadığı önce ölçülmeli (migration gerekebilir).

---

### A-5 — Şema sürüm işareti yok

**Severity:** P3
**Durum:** Confirmed

Üç eski sürümden migrate edilen DB'lerde de, taze kurulumda da
`PRAGMA user_version = 0`.

Migration tamamen "sütun var mı" kontrolüne dayanıyor. Sonuçları:

- Bir DB'nin hangi şema sürümünde olduğu bilinemiyor.
- **Downgrade tespit edilemiyor**: v0.0.9 ile açılmış bir profil v0.0.6 ile
  açılırsa, eski kod yeni sütunları görmezden gelir ve sessizce çalışır.
- Bilinmeyen bir gelecek şemaya karşı hızlı başarısızlık yok.

---

### A-6 — Yayınlanmamış değişiklikler CHANGELOG'da yok

**Severity:** P3
**Durum:** Confirmed

`v0.0.8` etiketinden sonra `main`'e iki commit girdi:

```
92e6655 fix(debts): record the total the ledger will actually pay
bf4e1be fix(pkgbuild): add verified v0.0.8 checksums
```

`92e6655` **kullanıcıya görünen finansal bir değeri değiştiriyor** (kayıtlı
toplam borç düşüyor). CHANGELOG'da `## Unreleased` bölümü yok ve bu değişiklik
hiçbir yerde kayıtlı değil.

---

## 7. Migration ve şema sonuçları

`v0.0.1`, `v0.0.4`, `v0.0.6` etiketlerinin kendi `init_db`'leriyle dolu DB
üretilip güncel kodla migrate edildi.

| Sürüm | Migration hatası | Bakiye | İşlem sayısı | Şifreli alan | İkinci koşum |
|---|---|---|---|---|---|
| v0.0.1 | yok | korundu | korundu | 3/3 çözülebilir | sorunsuz |
| v0.0.4 | yok | korundu | korundu | 3/3 çözülebilir | sorunsuz |
| v0.0.6 | yok | korundu | korundu | 3/3 çözülebilir | sorunsuz |

Migration bu vakalarda **temiz ve idempotent**. Fault injection (yarıda kesme,
disk-full, locked DB) uygulanmadı — bkz. bölüm 9.

---

## 8. Kusur ömrü gözlemleri

| Kusur | Eklendi | Bulundu | Etkilenen sürüm | Nasıl bulundu | Neden kaçtı |
|---|---|---|---|---|---|
| Taksit anapara sapması | 2026-07-22 (`eec10be`) | 2026-08-06 | v0.0.3–v0.0.7 (5) | Elle Decimal denetimi | Test `6000/6` kullanıyordu (tam bölünür) |
| İstisna baseline 44 slot | v0.0.5 daraltma turu | 2026-08-05 | v0.0.5–v0.0.6 | Eklenen handler'ın sessizce geçmesi | Kapı slack'i hiç kontrol etmiyor (A-2) |
| Taksit quantization koruması | 2026-08-06 (#73) | bu denetim | v0.0.8 | Mutation testing | Assertion totolojik (A-3) |

**Ortak desen:** üç vakada da kapı/test **kendi içinde tutarlıydı** ama
koruduğu şeye bağlı değildi. Kusurun ortalama ömrünü düşüren tek mekanizma
bu denetimde mutation testing oldu.

---

## 9. Test edilemeyen / denetlenmeyen alanlar

Bu alanlar **"geçti" sayılmamalıdır** — denetlenmediler.

| Alan | Sebep |
|---|---|
| Gerçek Windows DPAPI / OS keystore | Linux ortamı; simüle etmek kanıt değil |
| Windows SmartScreen, antivirüs, dosya kilidi | Gerçek donanım gerekiyor |
| Kurulum/upgrade/uninstall akışları | Windows makinesi yok |
| Concurrency ve yarış durumları | Deterministik harness kurulmadı |
| UI / localization / input fuzzing | Kapsanmadı |
| Backup/restore hata senaryoları | Kapsanmadı (mevcut 5 test dışında) |
| Performans ve kaynak sızıntısı | Ölçülmedi |
| Dependency güvenlik taraması | Yapılmadı |
| Price provider hata varyasyonları | Kapsanmadı |
| Migration fault injection | Yapılmadı |
| macOS | Hiç kapsanmadı |

---

## 10. v0.0.9 için önerilen kapsam

Yeni özellik önerilmiyor.

| Sıra | İş | Bulgu | Blocker |
|---|---|---|---|
| 1 | İstisna kapısı tespitini genişlet (tuple/attribute/alias) | A-1 | Evet |
| 2 | Kapıyı `current == baseline` eşitliğine çevir | A-2 | Evet |
| 3 | Kapının kendisi için test dosyası | A-1, A-2 | Evet |
| 4 | Taksit toplamı assertion'ını gerçek toplama bağla + ayrışan vaka | A-3 | Evet |
| 5 | `PRAGMA foreign_keys = ON` + mevcut öksüz kayıt taraması | A-4 | Hayır |
| 6 | `PRAGMA user_version` şema işareti + downgrade koruması | A-5 | Hayır |
| 7 | CHANGELOG `## Unreleased` bölümü | A-6 | Hayır |

1–4 arası tek bir düzeltme turudur ve hepsi **kalite kapısı** işidir; üretim
davranışını değiştirmezler.

---

## 11. Release önerisi

**P0 bulgusu yok.**

v0.0.9, 1–4 maddeleri tamamlandıktan sonra yayınlanabilir. Ancak bu denetim
**üretim davranışının tamamını kapsamadı** (bölüm 9). Bölüm 9'daki alanlar
kapatılmadan "stable" hedefine geçilmemeli.

Go/no-go koşulları için bkz. `V0_0_9_RELEASE_GATE.md`.
