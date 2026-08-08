# v0.0.9 — Windows Öncesi Kapı

**Dal:** `fix/v0.0.9-reliability` · **Taban:** `d5bd35f` (origin/main)
**Turun başlangıç HEAD'i:** `3551049` · **Turun sonu:** bkz. §12
**Karar:** **PRE-WINDOWS GO** (§13)

Bu tur yeni bir phase değil. Amacı tek bir belirsizliği kapatmaktı:
"connection cleanup" bulgusu üretim kodunda gerçekten düzeltildi mi, yoksa
yalnızca test mi eklenmişti? Cevap ikisi de değil — bulgunun kendisi yanlış
atfedilmişti. Ayrıntı §3.

---

## 1. Kaynak durumu

```
dal                fix/v0.0.9-reliability
başlangıç HEAD     3551049
origin/main        d5bd35f
çalışma ağacı      temiz
git diff --check   temiz
HEAD'de tag        yok
sürüm              0.0.9 / tag v0.0.9  (bump `acdccd1`; tag ve release YOK)
push / PR          yok
```

---

## 2. Phase 3 tam commit zinciri

`d5bd35f..3551049` arası 33 commit'in tur-tur dökümü
`V0_0_9_PHASE_3_CONTINUATION.md` → "Commit zinciri" bölümündedir. Bu turda
eklenen commit'ler §12'de.

---

## 3. Connection cleanup — yeniden değerlendirme

### Bulgunun geçmişi

| Kayıt | İçerik |
|---|---|
| Phase 2 (`V0_0_9_DEEP_AUDIT_PHASE_2.md` P2-7) | "Bağlantı temizliği GC'ye kalabiliyor", FD 4→14→21→71 (100 iterasyon), sonra 4. *Strong evidence P2* |
| Phase 3 (`94db19f`) | 7 operasyon türünde 100'er tekrar → delta 0. Yeniden üretilemedi; "davranış sabitlendi" denip kapatıldı |
| Atfedilen commit | `94db19f` — fakat bu commit YALNIZCA `tests/test_connection_cleanup.py` ekliyor |

Yalnız test eklemek üretim davranışını değiştirmez. Dolayısıyla üç
ihtimalden biri doğru olmalıydı: (A) üretim daha önce başka bir commit'te
düzeltilmişti, (B) Phase 2 harness'i yanılttı, (C) sızıntı hâlâ duruyordu.

### Sonuç: **Durum B — denetim harness'i yanlıştı**

Kök neden `scripts/audit/check_resource_leaks.py:56`:

```python
with get_connection() as conn:      # sqlite3'ün CM'i commit/rollback yapar, KAPATMAZ
```

Probe iterasyon başına bir bağlantı sızdırıyordu. Sızan `Connection`
nesneleri statement cache üzerinden referans döngüsüne girdiği için
descriptor'lar ancak generational GC koştuğunda geri veriliyordu —
"sonra GC ile 4'e düştü" gözleminin açıklaması tam olarak budur.

### Kanıt: aynı iş yükü, beş commit, aynı sonuç

Ölçüm aracı ortak (`fdbench.py`), Python 3.14.6, SQLite 3.53.4, her koşu
kendi geçici profilinde. `phase2` = eski probe kalıbı, `phase2c` = aynı
döngü `closing()` ile, `prod` = gerçek servis çağrıları (yazma + okuma).

| Commit | İş yükü | Baseline | 10 | 50 | 100 | GC öncesi | GC sonrası | DB rename | Sonuç |
|---|---|---|---|---|---|---|---|---|---|
| `d5bd35f` (Phase 3 ÖNCESİ taban) | phase2 | 4 | 14 | 54 | 104 | 104 | **4** | OK | sızdırıyor |
| `ac67447` (`94db19f^`) | phase2 | 4 | 14 | 54 | 104 | 104 | **4** | OK | sızdırıyor |
| `94db19f` (connection test commit'i) | phase2 | 4 | 14 | 54 | 104 | 104 | **4** | OK | sızdırıyor |
| `2bd5f0d` (Phase 3 teknik final) | phase2 | 4 | 14 | 54 | 104 | 104 | **4** | OK | sızdırıyor |
| `3551049` (tur başlangıcı) | phase2 | 4 | 14 | 54 | 104 | 104 | **4** | OK | sızdırıyor |
| beş commit'in tamamı | phase2c | 4 | 4 | 4 | 4 | 4 | 4 | OK | temiz |
| beş commit'in tamamı | prod | 4 | 4 | 4 | 4 | 4 | 4 | OK | temiz |

DB dosyasına işaret eden descriptor sayısı (`/proc/self/fd` readlink):
`phase2` iterasyon 100'de **100**, GC sonrası 0; `phase2c` ve `prod` her
kontrol noktasında **0**. Thread sayısı hepsinde 1.

Okunuşu:

- Ölçüm, Phase 3'ün ÖNCESİNDEKİ tabanla SONRASINDAKİ HEAD'de bit bit aynı.
  Üretim tarafında bu sayıyı etkileyen hiçbir şey değişmemiş.
- Farkı yaratan tek şey İŞ YÜKÜ: probe kalıbı sızdırıyor, gerçek servis
  çağrıları sızdırmıyor — Phase 3 öncesinde de sızdırmıyordu.
- Yani Phase 3'ün "delta 0" ölçümü doğruydu ama bir düzeltmenin sonucu
  değildi; farklı bir iş yükü ölçüyordu.

### Gerçek probe üzerinde doğrulama

`scripts/audit/check_resource_leaks.py`, aynı ağaçta, yalnız o tek satır
değiştirilerek:

```
tek satır geri alınmış:  fds 4 → 14 → 30 → 80 → (backup/GC sonrası) 4
düzeltilmiş:             fds 4 →  4 →  4 →  4 → 4
```

İlk satır P2-7'nin orijinal kaydıyla (`4→14→21→71→4`) aynı biçimdedir; ara
değerlerdeki fark yalnızca GC'nin ne zaman koştuğundan gelir.

### Yapılan değişiklikler

| Ne | Nerede | Commit |
|---|---|---|
| Harness düzeltmesi — 13 çağrı yeri `closing(get_connection()) as conn, conn` | `scripts/audit/*` (4 site), `scripts/dev/seed_readme_profile.py` (3), `scripts/audit/test_adversarial_reproductions.py` (7) | `28e43f0` |
| Sahiplik sözleşmesi testleri (15 test, açma/kapama sayar) | `tests/test_connection_ownership_contract.py` | `28e43f0` |
| Yanlış açıklamanın düzeltilmesi | `tests/test_connection_cleanup.py` docstring | `28e43f0` |

**Eski bulgu silinmedi.** P2-7 kaydı `V0_0_9_DEEP_AUDIT_PHASE_2.md` içinde
olduğu gibi duruyor; bu belge onu yeniden değerlendiriyor.

```
Original finding:   Strong evidence at the time (FD 4 -> 71 over 100 ops)
Re-evaluation:      Not reproducible with corrected harness
Root cause:         audit probe used `with get_connection() as conn:`,
                    which commits/rolls back but does not close
Production change:  None required for P2-7
```

---

## 4. Bu turda bulunan GERÇEK üretim bulgusu

Sahiplik haritası çıkarılırken ayrı bir eksik ortaya çıktı — P2-7 ile
ilgisi yok, ama aynı sınıftan.

| Alan | İçerik |
|---|---|
| **Bulgu** | `initialize_database()` bağlantıyı 6. satırda açıp 625. satırda kapatıyordu, arada `try/finally` YOKTU |
| **Erişilebilirlik** | Migration adımları bilerek fırlatabiliyor (`tests/test_migration_retry_safety.py` tam bu kesintiyi enjekte ediyor); fonksiyon süreç başına İKİ kez çağrılıyor (`main.py:442` açılış, `main.py:2129` sıfırlama) |
| **Etki** | Linux'ta bir descriptor. Windows'ta `finance.db` üzerinde kilit — yani bu sürümün sağlamlaştırdığı restore/rename adımını bloklardı |
| **Severity** | P2 — release blocker DEĞİL (istisna yolu gerektiriyor), ama Windows dosya-kilidi sınıfının tam ortasında |
| **Root cause** | 600 satırlık gövde tek bir fonksiyonda; kapatma en sonda düz bir ifade |
| **Production fix** | `dac9a15` — gövde `_initialize_database(conn)`'a alındı, `try/finally` sarmalayıcıda; ifadeler, sıraları ve commit noktaları aynı |
| **Regression test** | `28e43f0` — `test_initialize_database_leaves_no_open_connection`, `test_initialize_database_closes_when_a_migration_step_fails` |
| **Mutation kanıtı** | `finally` bloğu kaldırıldı → 2 test kırmızı; geri alındı → yeşil |

Statik tarama sonucu (55 çağrı yeri): 53 `try/finally`, 2 düz `close()`.
Düz olanlar `database/init_db.py` (yukarıda düzeltildi) ve
`generate_mock_data.py` (geliştirici aracı, paketlenmiyor — P3, dokunulmadı).
Dışarıdan bağlantı/cursor alıp kapatan hiçbir fonksiyon yok (sözleşme ihlali 0).

---

## 5. Connection regression / mutation sonucu

`tests/test_connection_ownership_contract.py` — 15 test, §6'daki 12 senaryonun
tamamı. FD saymak yerine `sqlite3.connect` sarmalanıp açma/kapama defterleniyor
(`opened == closed`), böylece ölçüm `/proc`'tan ve GC zamanlamasından bağımsız —
Windows'ta da aynı anlamı taşıyor.

| # | Senaryo | Sonuç |
|---|---|---|
| 1 | Internally owned, başarı yolu | PASS |
| 2 | Internally owned, istisna yolu | PASS |
| 3 | Externally supplied kapatılmıyor | PASS |
| 4 | Nested işlem dış bağlantıyı kapatmıyor | PASS |
| 5 | 100 okuma, explicit GC yok | PASS |
| 6 | 100 yazma, explicit GC yok | PASS |
| 7 | Migration sonrası handle yok | PASS |
| 7b | Migration ORTASINDA hata → yine kapanıyor | PASS |
| 8 | Backup round-trip sonrası DB rename edilebiliyor | PASS |
| 9 | Background thread kendi bağlantısını kapatıyor | PASS |
| 10 | Early-return yolu bırakmıyor | PASS |
| 11 | Cursor iterasyonu yarıda kesilince sözleşme korunuyor | PASS |
| 12 | Karma oturum sonunda açık bağlantı yok | PASS |
| + | Statik kapı: `with get_connection() as conn:` kod tabanında yok | PASS |
| + | Yasaklanan kalıbın gerçekten sızdırdığının kanıtı | PASS |

Mutation matrisi:

| Mutation | Beklenen | Gözlenen |
|---|---|---|
| `init_db` `finally` kaldır | kırmızı | **2 failure** |
| `account_service` ilk `finally: conn.close()` → `pass` | kırmızı | **2 failure** |
| `transaction_service` ilk `finally: conn.close()` → `pass` | kırmızı | **4 failure** |
| Anti-kalıp yeniden sokuldu | kırmızı | **1 failure** (statik kapı) |

Dört mutation da yakalandı, dördü de geri alındı. Kapı boş değil.

---

## 6. Version gate

```
scripts/check_version_consistency.py     exit 0 — 0.0.9 / tag v0.0.9
scripts/audit/version_mutation_matrix.py exit 0 — yakalanan=16 kaçan=0 uygulanamayan=0
```

Sürüm bump §15'te YAPILDI: Windows turunun önkoşuluydu, kozmetik değil.

---

## 7. Packaging / upgrade

`ddda5ed` ile kapandı ve bu turda yeniden okundu:

- `.github/workflows/build-windows.yml` hard-coded `0.0.1` fallback'i taşımıyor;
- `scripts/previous_release.py` önceki sürümü semantik sürüme göre seçiyor;
- `tests/test_previous_release_selection.py` bunu normal suite'te sabitliyor.

**Runtime doğrulaması yok** — gerçek installer üretimi ve gerçek upgrade
yalnızca Windows'ta yapılabilir. Bkz. §10.

---

## 8. Zorunlu CI — DÜZELTİLMİŞ STATÜ

Phase 3 belgeleri "Kalan reliability testleri zorunlu CI kapsamında" diyordu
ve `V0_0_9_PHASE_3_RELEASE_GATE.md` bu maddeyi `[x]` işaretlemişti. **Bu
iddia yanlıştı.**

`reliability-gates` job'ının kendisi sağlam — kontrol edildi:

| Kontrol | Sonuç |
|---|---|
| Adımlar gerçekten koşuyor (dosya varlığı kontrolü değil) | evet |
| 16 version mutation | koşuyor |
| Migration matrisi v0.0.1–v0.0.8 | koşuyor |
| Adversarial/regression grubu (6 modül) | koşuyor |
| Property testleri (hypothesis) | koşuyor |
| Hypothesis dev bağımlılığından kuruluyor | evet (`requirements-dev.txt`, `hypothesis==6.165.2`) |
| `continue-on-error` | job içinde YOK |
| `\|\| true` | YOK |
| Koşulsuz skip | YOK (`if: always()` yalnız artifact upload'ında) |
| PR/push tetikleyicisine bağlı | evet |

Ama branch protection ayrıca okundu (`gh api
repos/:owner/:repo/branches/main/protection`) ve `main` için zorunlu
status check listesi şu:

```
required_status_checks.contexts = ["build-windows", "test"]
```

`reliability-gates` bu listede **yok**. `test-windows`, `lint` ve
`visual-regression` de yok. Yani bu job'lar her PR'da KOŞUYOR ama merge'ü
BLOKLAMIYOR — kırmızı olsalar bile birleştirme yapılabilir.

**Statü: Açık — repo ayarı.** Kod tarafında yapılacak bir şey yok; düzeltme
GitHub'ın branch protection ayarında `reliability-gates` ve `test-windows`
eklenmesidir. Bu bir hesap/repo ayarı değişikliği olduğu için bu turda
YAPILMADI; kullanıcı kararı.

Ürün kusuru değil, süreç kapısı kusuru: yayımlanacak artifact'in
doğruluğunu etkilemiyor, ama "reliability CI zorunlu" cümlesini yanlış
kılıyor. Belgeler bu turda düzeltildi.

---

## 9. Açık non-Windows problemler

Aşağıdaki liste bu belgenin ilk yazımındaki hâliydi; **7 maddenin 6'sı
sonradan kapatıldı** (bkz. §14).

| # | İş | Sınıf | Durum |
|---|---|---|---|
| 1 | `reliability-gates` + `test-windows` branch protection'da zorunlu değil | P2 — süreç | **Açık** — repo ayarı, kullanıcı kararı |
| 2 | `generate_mock_data.py` bağlantıyı `try/finally` olmadan kapatıyor | P3 | Kapandı — `3908c51` |
| 3 | `user_version` şema işareti hâlâ 0 (A-5) | P3 → P2 | Kapandı — `63941a5` |
| 4 | Pyflakes backlog (bloklamayan tarama) | P3 | Kapandı — `82cdae0`, `6f3096e`, `a7e1938` |
| 5 | Geniş exception borcu (145 handler, kapı yeşil, borç büyümüyor) | P3 | **Açık** — bilinçli |
| 6 | `bandit` B608, `database/init_db.py` — tablo/kolon adları iç sabitler | P3 | Kapandı — `d5310ab` |
| 7 | Dependency güvenlik taraması (`pip-audit`) çalıştırılmadı | P3 → **P2** | Kapandı — `23985a7` |

**Açık P0 yok. Açık P1 yok. Release-blocker P2 yok.**

---

## 10. Yalnız Windows'ta doğrulanabilecek alanlar

Değişmedi; `V0_0_9_PHASE_3_RELEASE_GATE.md` kontrol listesi geçerli.

- DPAPI / gerçek key provider yaşam döngüsü
- Installer üretimi, kurulum, upgrade, uninstall, reinstall
- v0.0.8 → RC upgrade ve `previous_release.py`'nin runtime davranışı
- Yarım restore sonrası GERÇEK süreç kill ve açılış kurtarması
- Recovery dialog'un gerçek window provider ile render edilmesi
- Dosya kilitleri, antivirüs, SmartScreen
- Unicode/boşluklu kullanıcı yolları
- DPI %100/%125/%150/%200, klavye, Tab sırası
- Kapanış sonrası DB file-lock serbest kalması (bu turda Linux'ta `os.replace`
  ile doğrulandı — Linux'ta açık handle rename'i engellemediği için bu kanıt
  Windows'un YERİNE GEÇMEZ)

---

## 11. Tam doğrulama koşumu

Hepsi bu turun sonundaki ağaçta, `env -u PYTHONPATH`, Python 3.14.6.

| Kontrol | Exit | Sonuç |
|---|---|---|
| `python run_tests.py` | 0 | **796 test OK**, skip 2, ~53 s (tur başında 781) |
| `python -m compileall .` | 0 | temiz |
| `python scripts/check_version_consistency.py` | 0 | 0.0.8 / v0.0.8 |
| `python scripts/audit_exception_handlers.py` | 0 | temiz |
| `git diff --check` | 0 | temiz |
| `scripts/audit/version_mutation_matrix.py` | 0 | 16/16 yakalandı |
| `scripts/audit/check_schema_consistency.py` | 0 | v0.0.1–v0.0.8 state/fresh/idempotent True |
| adversarial + phase2 grubu (6 modül) | 0 | yeşil |
| `scripts.audit.test_phase2_financial_properties` | 0 | 6 test OK |
| `flake8 --select=F821,F822,F823,E722` | 0 | 0 ihlal |
| `mypy database/init_db.py` | 0 | temiz |
| `bandit` (değişen dosyalar) | 0 | 1 Medium, önceden mevcut (§9.6) |

Çalıştırılmayan kontroller — **Passed sayılmadı**:

| Kontrol | Neden |
|---|---|
| `ruff`, `pyright`, `pip-audit` | ortamda kurulu değil |
| SBOM / AppImage build / AppImage smoke | CI'da koşuyor, yerelde çalıştırılmadı |
| Gerçek Windows installer üretimi | Windows gerektiriyor |
| `check_financial_invariants.py` | `--db` ile gerçek profil ister; bu tur sentetik profil üretmedi |

---

## 12. Bu turda eklenen commit'ler

| Commit | Tür | İçerik |
|---|---|---|
| `dac9a15` | production fix | `initialize_database()` bağlantıyı her çıkış yolunda kapatıyor |
| `28e43f0` | test/harness | Denetim probe'unun sızıntısı düzeltildi (13 site) + 15 sahiplik testi |
| `670cd11` | docs | Bu belge + Phase 3 statü düzeltmeleri |
| `5af7fa0` | test | Statik kapı metin araması yerine AST ile tarıyor |
| *(bu commit)* | docs | Commit tablosunun kapatılması |

Push YOK · PR YOK · tag YOK · release YOK · version bump YOK.

`5af7fa0` hakkında not: `670cd11` sonrası tam suite koşumunda statik kapı
kendi açıklama docstring'ini yakaladı. Kapının kendisi doğru davranıyordu,
tarama yöntemi kabaydı — metin araması bir kalıbı AÇIKLAYAN yorumla onu
KULLANAN kodu ayırt edemiyor. AST taraması bu ayrımı yapıyor ve kapının
"kendi dosyasını atla" muafiyetini de gereksiz kılıyor. Mutation yeniden
doğrulandı.

---

## 13. Karar: **PRE-WINDOWS GO**

| Koşul | Durum |
|---|---|
| Açık non-Windows P0/P1 yok | ✅ |
| Release-blocker P2 yok | ✅ |
| Connection cleanup durumu kesin ve kanıtlı | ✅ — Durum B, beş commit'te ölçüldü |
| Tam suite yeşil | ✅ 796 OK |
| Reliability gates yeşil | ✅ (zorunluluk ayrı mesele — §8) |
| Migration matrisi yeşil | ✅ |
| Version/packaging gate yeşil | ✅ |
| Belgeler tutarlı | ✅ — bu turda düzeltildi |
| Çalışma ağacı temiz | ✅ |

§8'deki branch-protection eksiği GO'yu engellemiyor: yayımlanacak
artifact'in doğruluğunu değil, gelecekteki regresyonların ne kadar hızlı
yakalanacağını etkiliyor. Yine de Windows turundan önce kullanıcı
tarafından kapatılması önerilir.

**Windows doğrulamasına gönderilecek commit:** §14'ün son satırı.

---

## 14. Ek tur — opsiyonel/P3 kalemlerinin kapatılması

Kullanıcı isteğiyle §9'daki "bloklamayan" liste ele alındı. Biri
bloklamayan olmaktan çıktı.

### 14.1 Bağımlılık güvenlik taraması — P3 değil, P2

`pip-audit` hiç koşmamıştı (Phase 2'den beri *Not started*). İlk koşum
3 pakette **18 benzersiz** bulgu verdi:

| Paket | Sürüm | Bulgu | Yeni sürüm |
|---|---|---|---|
| pillow | 12.2.0 | 13 | 12.3.0 |
| cryptography | 48.0.0 | 4 | 50.0.0 |
| setuptools | 82.0.1 | 1 | 83.0.0 |

**Pillow'unkiler teorik değil, erişilebilir.**
`services/brand_icon_service.py` kullanıcının girdiği alan adı için üç
üçüncü-taraf ikon servisinden (`google/s2/favicons`, `icon.horse`,
`unavatar.io`) veri çekiyor ve yanıtı doğrudan `Image.open(BytesIO(payload))`
ile Pillow'a veriyor, ardından `resize` uyguluyor. Bulguların birkaçı tam
bu yollarda native heap OOB write: koordinat sınırları (PYSEC-2026-3451),
JPEG2000 tile birikimi (3496), `raw` codec mmap yolu (3493), rank filter
(3454). Bozulmuş bir ikon servisi ya da araya giren bir bağlantı yeterli.
Pillow `archlence.spec`'in excludes listesinde DEĞİL — Windows kurulum
paketiyle birlikte gidiyor.

cryptography transitif (keyring/SecretStorage); uygulamanın kendi şifrelemesi
pycryptodome kullanıyor, dolayısıyla erişilebilirlik daha düşük — ama
wheel'ler OpenSSL'i statik linkliyor ve onlar da paketleniyor.

Regresyon kanıtı: yükseltilmiş pin'lerle kurulan izole ortam ile orijinal
pin'lerle kurulan kontrol ortamı **birebir aynı** sonucu veriyor; projenin
kendi ortamında tam suite 796 → yeşil. Yükseltme sonrası tarama temiz.

Tarama artık `reliability-gates` içinde **bloklayan** adım. `continue-on-error`
BİLEREK yok: bu bulgular tam da bilgilendirici bırakıldığı için birikmişti.

### 14.2 A-5 — şema kuşağı işareti ve downgrade koruması

`PRAGMA user_version` sıfırdı; veritabanı hangi yapı tarafından yazıldığını
söylemiyordu, dolayısıyla eski bir yapı yeni bir profili açıp tanımadığı
sütunları yok sayarak üzerine yazabilirdi.

`SCHEMA_VERSION = 1` kondu. Kontrol her şeyden ÖNCE (tek bir `CREATE TABLE`
bile çalışmadan), işaret ise EN SONDA ve koşulsuz — böylece yarım kalan
kurulum kendini tamamlanmış saymıyor, fresh ile upgraded aynı değeri
taşıyor. Açılış fail-closed: sürüm numaraları log'a, kullanıcıya sabit metin.

Mevcut hiçbir kurulumda tetiklenemez (hepsi 0 taşıyor, 0 < 1); yalnız daha
yeni bir yapıdan geri dönüşte devreye girer.

Migration matrisi: v0.0.1–v0.0.8'in **sekizi de** `user_version=1`'e göç
ediyor, `fresh_schema=True` korunuyor.

### 14.3 Pyflakes backlog: 115 → 0

15 F401 ölü import; 100 F841'in 98'i kullanılmayan `except ... as e` bağı.
Kalan 2'si servis katmanına taşınmış işin ölü kopyasıydı ve ayrışma riskiydi:
`asset_mixin`'in kullanılmayan satış açıklaması (`AssetSaleService.sell`
`8b1744e`'den beri kendisi yazıyor) ve `recurring_mixin`'in kullanılmayan
`is_active` hesabı (`DebtPaymentService.pay_auto` aynı transaction içinde
karar veriyor).

Backlog 0 olduğu için CI adımı `continue-on-error`'dan kurtarıldı ve tam
pyflakes kümesi artık blokluyor. Workflow'da hiç `continue-on-error` kalmadı.

### 14.4 Ek turun commit'leri

| Commit | Tür | İçerik |
|---|---|---|
| `23985a7` | security | pillow/cryptography/setuptools yükseltmesi + zorunlu `pip-audit` |
| `d5310ab` | refactor | defter baseline sorgusunun tanımlayıcı allow-list'i (bandit B608) |
| `3908c51` | fix | `generate_mock_data.py` bağlantı kapatma |
| `82cdae0` | chore | 15 kullanılmayan import |
| `6f3096e` | chore | 100 F841; ikisi ölü servis kalıntısı |
| `a7e1938` | ci | tam pyflakes kümesi bloklayan hâle getirildi |
| `63941a5` | fix | A-5 şema kuşağı işareti + downgrade reddi |
| *(bu commit)* | docs | bu bölüm + CHANGELOG |

### 14.5 Ek tur sonrası doğrulama

```
normal suite         809 test OK (skip 2)     ← turun başında 796
TAM pyflakes         0  (artık zorunlu)
bloklayan lint       0
pip-audit            temiz
istisna kapısı       145 handler yeşil
16 version mutation  16/16
migration matrisi    v0.0.1–v0.0.8 · fresh_schema=True · user_version=1
adversarial+phase2   21 test OK
property             6 test OK
sürüm kapısı         0.0.9 / tag v0.0.9
compileall           temiz
git diff --check     temiz
```

Karar değişmedi: **PRE-WINDOWS GO**. Açık tek non-Windows madde branch
protection ayarı (§9.1) ve bilinçli exception borcu (§9.5).

---

## 15. Sürüm bump'ı — Windows turunun önkoşuluydu

Plan "Windows → soak → bump" idi. Bu sırayla Windows turu YAPILAMAZDI:
`APP_VERSION` 0.0.8 kaldıkça RC installer `ArchlenceSetup-0.0.8.exe` adıyla
ve 0.0.8 damgasıyla üretilecekti, dolayısıyla Windows kontrol listesindeki
"doğru RC sürümü gösteriliyor" ve "uninstall entry doğru güncelleniyor"
maddelerinin doğrulayacağı bir şey olmayacaktı. Daha kötüsü,
`previous_release.py` tabanı merkezi sürümden türettiği için upgrade smoke
testi **v0.0.7 → 0.0.8**'i sınayacaktı — yani `ddda5ed`'in var olma
sebebini ıskalayacaktı. Elle sürüm geçmek de mümkün değil: workflow
merkezi kaynakla uyuşmayan girdiyi reddediyor.

Bump `acdccd1` ile yapıldı, beş kaynak birden: `utils/version.py`,
`installer/archlence.iss`, `build-windows.yml` default, `PKGBUILD`,
`CHANGELOG.md`. Sürüm kapısı git tag'i aramıyor — kaynakta bump ≠ release.

Doğrulama: `previous_release.py --target 0.0.9` artık **`v0.0.8`** dönüyor.

`PKGBUILD` checksum'ları v0.0.8'deki yönteme uyularak kasıtlı geçersiz
(tamamı sıfır) placeholder'a çevrildi; `SKIP` DEĞİL, çünkü `SKIP`
doğrulamayı kapatır. Gerçek hash'ler yayın sonrası ayrı commit'le girer
(v0.0.8'de `bf4e1be` böyle yapmıştı).

### 15.1 Bump'ın ortaya çıkardığı bulgu: matris kendi kendini geçersiz kılıyormuş

Bump commit'lendikten SONRA 16 vakalık sürüm mutation matrisi
**10 yakalandı / 3 kaçtı / 3 uygulanamadı**'ya düştü.

Sebep: altı vaka aranan dizeyi `0.0.8` olarak SABİT yazmıştı.

- 02, 03, 05 → desen artık yok, "uygulanamadı";
- 07, 09, 10 → desen CHANGELOG'un **tarihsel** `## [0.0.8]` bölümünde
  hâlâ var; mutation oraya uygulandı, kapı haklı olarak umursamadı,
  vaka "KAÇTI" raporladı.

Yani sürüm kapısını sınayan araç her sürüm bump'ında kendini geçersiz
kılıyordu — ve 0.0.8'de kusursuz görünüyordu. Denetimin tekrar eden
teması: yeşil raporlayan ama bir şey ölçmeyen kapı.

Düzeltme `329dfc1`: sürüm artık **sınanan ağaçtan** okunuyor (import
değil, ayrıştırma — worktree'nin sürümü farklı olabilir), yer tutucu
`@@VERSION@@`. Yer tutucu bilerek `{v}` DEĞİL: iki vaka workflow'un
gerçek `${v}` kabuk değişkenini arıyor ve `str.format` onları
`$0.0.9`'a çevirip sessizce uygulanamaz kılardı — aynı hatanın bir kat
aşağısı.

`tests/test_version_gate_matrix_contract.py` (4 test) sabit sürümün ve
`{v}` çakışmasının geri gelmesini engelliyor; iki yönlü mutation ile
doğrulandı. Matris 0.0.9'da tekrar **16/16**.

### 15.2 Bump sonrası doğrulama

```
normal suite         813 test OK (skip 2)
sürüm kapısı         0.0.9 / tag v0.0.9
16 version mutation  16/16 (0.0.9 üzerinde)
upgrade tabanı       previous_release(0.0.9) = v0.0.8
release notes        CHANGELOG'dan üretilebiliyor (160 satır, 8 zorunlu başlık)
migration matrisi    v0.0.1–v0.0.8 · user_version=1
TAM pyflakes         0 · pip-audit temiz · compileall temiz
tag / release        YOK
```

**Windows doğrulamasına gönderilecek commit: bu belgenin commit'i.**
