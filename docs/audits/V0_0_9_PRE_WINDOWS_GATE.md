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
sürüm              0.0.8 / tag v0.0.8  (bump YAPILMADI)
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
scripts/check_version_consistency.py     exit 0 — 0.0.8 / tag v0.0.8
scripts/audit/version_mutation_matrix.py exit 0 — yakalanan=16 kaçan=0 uygulanamayan=0
```

Sürüm bump YAPILMADI (kasıtlı).

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

| # | İş | Sınıf | Release blocker |
|---|---|---|---|
| 1 | `reliability-gates` + `test-windows` branch protection'da zorunlu değil | P2 — süreç | Hayır (ürün etkilemiyor) |
| 2 | `generate_mock_data.py` bağlantıyı `try/finally` olmadan kapatıyor | P3 — geliştirici aracı | Hayır |
| 3 | `user_version` şema işareti hâlâ 0 (A-5) | P3 | Hayır |
| 4 | Pyflakes backlog (bloklamayan tarama) | P3 | Hayır |
| 5 | Geniş exception borcu (145 handler, kapı yeşil, borç büyümüyor) | P3 | Hayır |
| 6 | `bandit` B608, `database/init_db.py:549` — tablo/kolon adları iç sabitler, kullanıcı girdisi değil | P3 — önceden mevcut | Hayır |
| 7 | Dependency güvenlik taraması (`pip-audit`) çalıştırılmadı — araç ortamda yok | P3 | Hayır |

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
| *(bu commit)* | docs | Bu belge + Phase 3 statü düzeltmeleri |

Push YOK · PR YOK · tag YOK · release YOK · version bump YOK.

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

**Windows doğrulamasına gönderilecek commit:** bu belgenin commit'i
(§12'nin üçüncü satırı) — yani bu turun son HEAD'i.
