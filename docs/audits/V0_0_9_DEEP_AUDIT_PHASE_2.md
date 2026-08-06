# Archlence — v0.0.9 Phase 2 Güvenilirlik Denetimi

**Devam edilen dal:** `audit/v0.0.9-deep-review`
**Phase 1 commit'i:** `5302d1a` (mevcut)
**Denetim tabanı:** `d5bd35f` (= `origin/main`)
**Tarih:** 2026-08-06

> Phase 2 harness'leri bu oturumdan ÖNCE oluşturulmuştu ve commit edilmemişti.
> Silinmedi, üzerine devam edildi. Bu belge o çalışmayı doğrular, eksiklerini
> kapatır ve yeni bulguları ekler.

---

## 1. Yönetici özeti

Phase 2, **üretim yoluna ulaşan adversarial testlerle** çalışır. Phase 1
mutation testing ile *kapıların* yalan söyleyip söylemediğine bakmıştı;
Phase 2 *uygulamanın kendisinin* hangi yanlış finansal durumları ürettiğine
bakıyor.

**Sonuç: v0.0.9 için NO-GO.**

Beş **P0** doğrulandı — hepsi ya aynı paranın iki kez etkilenmesi ya da yarım
commit edilmiş finansal durum. Bir tanesi bu turda bulundu ve önceki kapsamda
hiç yoktu: **infinity tutarı bakiyeyi kalıcı olarak bozuyor ve bozulan hesap
portföy toplamından sessizce düşüyor.**

Phase 1'in P2 bulgusu A-3 (taksit quantization koruması yok) **kapandı** —
Phase 2 property testi o mutation'ı yakalıyor. Ancak bu test normal suite'te
değil; koruma yalnızca denetim harness'inde duruyor.

---

## 2. Coverage ledger

| # | Alan | Durum | Kanıt |
|---|---|---|---|
| 1 | Backup authenticity | **Completed** | P0-1 |
| 2 | Backup/restore completeness | **Partially completed** | P1-1 (config); tam matris koşulmadı |
| 3 | Backup/restore failure recovery | **Partially completed** | P1-1; truncated/traversal/symlink denenmedi |
| 4 | Encryption key lifecycle | **Not started** | — |
| 5 | Recovery password/key senaryoları | **Not started** | — |
| 6 | Recurring charge idempotency | **Completed** | P0-2 |
| 7 | Recurring refund idempotency | **Completed** | P0-3 |
| 8 | Asset transaction atomicity | **Completed** | P0-4 |
| 9 | Debt transaction atomicity | **Completed** | P0-5 |
| 10 | Diğer finansal atomicity | **Not started** | 20 işlemin 4'ü sınandı |
| 11 | Concurrency / race conditions | **Not started** | Deterministik harness kurulmadı |
| 12 | Financial property-based testing | **Completed** | 6 property, mutation ile doğrulandı |
| 13 | Migration normal matrix | **Completed** | v0.0.1–v0.0.8 |
| 14 | Migration fault injection | **Partially completed** | 1 enjeksiyon noktası (P1-2); 16 nokta denenmedi |
| 15 | Input validation | **Completed** | **P0-6 (yeni)** + P2-1 |
| 16 | UI / localization | **Partially completed** | dummy window; gerçek Tab/DPI yok |
| 17 | Performance scaling | **Completed** | 0–50.000 doğrusal |
| 18 | Resource leak | **Not started** | ölçülmedi |
| 19 | Linux packaging | **Partially completed** | statik inceleme |
| 20 | Windows packaging | **Blocked by environment** | Windows yok |
| 21 | Upgrade workflow | **Partially completed** | P2-3 (sabit v0.0.1) |
| 22 | Dependency / security | **Not started** | — |
| 23 | Observability / error handling | **Partially completed** | Phase 1 A-1/A-2 |
| 24 | Version / release consistency | **Partially completed** | P2-2 |
| 25 | RC / soak readiness | **Not started** | — |

**Phase 2 tamamlanmadı.** 25 alanın 8'i Completed, 8'i Partially, 8'i Not
started, 1'i Blocked.

---

## 3. Doğrulanmış P0 bulguları

Hepsi `scripts/audit/` altındaki testlerle yeniden üretilir ve `AUDIT_STATE`
satırlarıyla kanıt basar.

### P0-1 — Backup manifest'i authenticated değil

`test_adversarial_reproductions.BackupAuthenticityReproduction`

```
AUDIT_STATE backup_authenticity before_balance=874.5 after_balance=777777.77
            expected_exception=IntegrityVerificationError caught_exception=NONE
```

Yedek içindeki finansal veri değiştirilip metadata'daki SHA-256 yeniden
hesaplandığında `verify_backup` paketi **kabul etti**. Digest yalnızca
bütünlük (kaza) tespiti sağlıyor, **authenticity (kasıt) sağlamıyor** —
saldırgan hem veriyi hem hash'i değiştirebiliyor.

**Doğrudan kullanıcı etkisi:** değiştirilmiş bir yedeği geri yükleyen kullanıcı
sahte bakiyeyi gerçek sanır.
**Durum:** Confirmed · **Release blocker:** Evet

### P0-2 — Aynı vade iki kez tahsil ediliyor

```
AUDIT_STATE recurring_retry before_balance=1000.0 after_balance=800.0
            transaction_count=2 before_due=2026-08-06 after_due=2026-09-06
```

Aynı recurring nesnesi iki kez işlenince iki işlem yazıldı ve bakiye iki kez
düştü. Idempotency anahtarı yok.
**Durum:** Confirmed · **Release blocker:** Evet

### P0-3 — Aynı tahsilat iki kez iade ediliyor

```
AUDIT_STATE recurring_refund_retry before_balance=1000.0 after_balance=1100.0
            transaction_counts={'expense': 1, 'income': 2}
```

Bakiye **başlangıcın üstüne** çıktı: 100 TL tahsil edildi, 200 TL iade edildi.
İkinci iade reddedilmedi.
**Durum:** Confirmed · **Release blocker:** Evet

### P0-4 — Varlık satışı atomik değil

```
AUDIT_STATE asset_sale_fault before_balance=1000.0 after_balance=1300.0
            before_asset_count=1 after_asset_count=1 injected_exception=OSError
```

Varlık silme adımına hata enjekte edildiğinde nakit **kredilendi** ama varlık
portföyde **kaldı**. Kullanıcı hem parayı hem varlığı elde tutuyor.
**Durum:** Confirmed · **Release blocker:** Evet

### P0-5 — Borç ödemesi atomik değil

```
AUDIT_STATE debt_ledger_fault before_paid=0 after_paid=1
            after_last_auto_pay=2026-08 transaction_count=0 balance=1000.0
```

Ledger yazımı başarısız olduğu hâlde `paid_installments` ilerledi ve
`last_auto_pay_date` güncellendi. **Ödenmemiş bir taksit ödenmiş sayıldı.**
**Durum:** Confirmed · **Release blocker:** Evet

### P0-6 — Infinity bakiyeyi bozuyor ve hesabı toplamdan düşürüyor **(YENİ)**

`test_phase2_additional_reproductions.NonFiniteCorruptionReproduction`

```
AUDIT_STATE nonfinite_infinity raised=NONE
            balance=5000.0->-inf->None
            portfolio_total=7500.0->-inf->2500.0
            balance_events=2->3
```

Önceki kapsam yalnızca **NaN**'ı sınamıştı ve NaN zararsız davranıyor (SQLite
katmanında reddediliyor, durum değişmiyor). **Infinity hiç sınanmamıştı ve
tamamen farklı davranıyor:**

| Adım | Bakiye | Portföy toplamı |
|---|---|---|
| başlangıç | 5.000,00 | 7.500,00 |
| `inf` gider | **-inf** | **-inf** |
| ikinci `inf` | **NULL** | **2.500,00** |

İkinci adımdan sonra 5.000 TL'lik hesap `SUM(balance)` toplamından **sessizce
düşüyor** ve orijinal bakiye kalıcı olarak kaybolmuş oluyor. Hiçbir exception
yükselmiyor.

**Doğrudan kullanıcı etkisi:** sessiz finansal veri kaybı + yanlış net servet.
**Durum:** Confirmed · **Release blocker:** Evet

---

## 4. Doğrulanmış P1 bulguları

### P1-1 — Başarısız restore config'i geri almıyor

```
AUDIT_STATE restore_config_rollback caught_exception=DataMigrationError
            balance=4321.0 key_rolled_back=True config_after={"profile":"from-backup"}
```

Restore hata verdiğinde DB ve anahtar geri alınıyor, **config alınmıyor**.
Sonuç: veritabanı eski, config yedekten — **karma durum**.

Ayrıca başarılı restore config'i hiç geri getirmiyor (bulgu G). Dokümantasyon
"tam profil" izlenimi veriyorsa bu bir ürün sözleşmesi ihlalidir.
**Durum:** Confirmed · **Release blocker:** Evet

### P1-2 — Migration yarıda kesilirse backfill bir daha çalışmıyor

```
AUDIT_STATE migration_fault caught_exception=OSError
            account_type_column=True account_type_after_retry=None
```

İlk `ALTER TABLE` uygulanıp sonraki adım hata verdiğinde sütun oluşmuş kalıyor.
Migration mantığı "sütun var mı" kontrolüne dayandığı için **sonraki açılış
backfill'i atlıyor** ve `account_type` kalıcı olarak `None` kalıyor.
**Durum:** Confirmed · **Release blocker:** Evet

### P1-3 / P1-4 — Phase 1 istisna kapısı bulguları

`V0_0_9_DEEP_AUDIT.md` A-1 (tuple/attribute/alias bypass) ve A-2 (baseline
slack'i sessizce yeniden birikiyor) buraya birleşik blocker olarak dahildir.

---

## 5. P2 ve P3

| ID | Bulgu | Sınıf |
|---|---|---|
| P2-1 | NaN domain sınırında değil SQLite katmanında reddediliyor (durum değişmiyor) | P2 |
| P2-2 | Version consistency kapısı workflow fallback ve release asset adı mutation'larını kaçırıyor | P2 |
| P2-3 | Upgrade smoke gerçek önceki release yerine sabit `v0.0.1` kullanıyor | P2 |
| P2-4 | Plaintext CSV export Linux'ta `0644` izinle oluşuyor | P2 |
| P2-5 | FK kısıtı tanımlı ama zorlanmıyor (Phase 1 A-4) | P2 |
| P3-1 | `PRAGMA user_version = 0`, downgrade tespit edilemiyor (Phase 1 A-5) | P3 |
| P3-2 | Yayınlanmamış değişiklikler CHANGELOG'da yok (Phase 1 A-6) | P3 |

---

## 6. Kapatılan Phase 1 bulgusu

**A-3 (taksit quantization koruması yok) — KAPANDI.**

Phase 2 property testi `test_installment_quantization_and_remainder_preserve_principal`
içindeki `assertEqual(monthly, fiat(principal / installments))` assertion'ı,
Phase 1'de 699 testin tamamından kaçan mutation'ı yakalıyor:

```
mutation: fiat(decimal_from(amount)/n)  ->  round(float(amount)/n, 2)
sonuç   : AssertionError: Decimal('0.01') != Decimal('0.00')
```

**Kalan risk:** bu test normal suite'te değil. Koruma yalnızca denetim
harness'inde duruyor ve CI onu koşmuyor.

---

## 8. Final tamamlanma eki — 2026-08-06

**Status: Completed with environment limitations.** Bu ek, yukarıdaki ilk
ara rapordaki "Not started" satırlarını geçersiz kılar. Hiçbir production
dosyası değiştirilmedi. Bilerek kırmızı audit testleri kusurun kanıtıdır.

### Bu turdaki yeni üretim kanıtı

| ID | Sonuç | Production path | Kanıt | Sınıf |
|---|---|---|---|---|
| P0-7 | Kredi kartı limit kontrolü/write TOCTOU | `TransactionService.add_transaction` → `AccountService.check_spending_allowed` | iki 60 TL worker, limit 100: `transaction_count=2 debt=120 available_limit=0` | Confirmed P0 |
| P0-6 genişleme | Infinity account, savings ve recurring yollarında da kabul edildi | `AccountService.create_account`; `SavingsService.deposit_to_goal`; `process_due_recurring_payment` | savings: `balance=-inf goal=inf`; recurring: `transaction=1 balance=-inf`; account creation `caught=NONE` | Confirmed P0 |
| P2-6 | Archive allow-list yok | `backup_service.verify_backup` | `unexpected.txt` içeren paket `caught=NONE` | Confirmed P2 |
| P2-7 | Bağlantı temizliği GC'ye kalabiliyor | `database.db.get_connection` çağıran backend yollar | FD 4→14→21→71 (100 iterasyon), sonraki backup/GC ile 4 | Strong evidence P2 |

`test_phase2_concurrency` ayrıca iki gerçek worker yarışında recurring charge
ve refund kusurlarını tekrar doğruladı: sırasıyla `2 tx / balance 800` ve
`2 income / balance 1100`. Savings withdrawal aynı denemede güvenli kaldı:
tek withdrawal, `goal_amount=0`, account 1100; ikinci worker `ValueError`.
Bu yalnız bu sınanan yol için olumlu kanıttır.

### Restore, key ve archive sonuçları

* 68 crypto/key/recovery/backup testi: **67 PASS, 1 Windows-only skip**.
  AEAD tag/ciphertext corruption, wrong key, recovery wrong password, key
  rotation rollback, Linux file-provider `0600` ve backup DB/key eşleşmesi
  sınandı. Bu, P0-1'in manifest authenticity kusurunu ortadan kaldırmaz.
* Restore fault injection DB+key geri alımını ve config rollback eksikliğini
  kanıtladı. Tam 10 aşamalı fail/atomic swap matrisi uygulamadaki iki hook ile
  temsil edilemedi; disk-full, locked DB, Windows rename semantics ve crash
  sonrası restart **Partially completed** olarak kaldı.
* `verify_backup` `../` ve POSIX absolute member'ı reddetti. Linux'ta
  `C:\\escape.txt` relative isim sayıldı (Windows davranışı doğrulanmadı).
  Bilinmeyen member kabul edildi; restore yalnız bilinen isimleri temporary
  directory'ye extract ediyor. Bu allow-list eksiğidir; hedef dışına yazma
  için kanıt değildir.

### Non-finite kapsamı

| Giriş noktası | `inf` sonucu | Durum |
|---|---|---|
| TransactionService expense | `-inf`, sonra `NULL`, aggregate hesap dışı | P0-6 |
| Account initial balance | exception yok | P0-6 aile |
| Savings deposit | account `-inf`, goal `inf`, event yazıldı | P0-6 aile |
| Recurring processing | transaction/event yazıldı, balance `-inf` | P0-6 aile |
| AssetPurchaseService | `ValueError`, state değişmedi | korunan yol |
| NaN TransactionService | SQLite `IntegrityError`; state değişmedi | P2 domain validation gap |

Debt/card/create/import bütün entry point'leri için exhaustive finite matrix
henüz yoktur; bu nedenle alan tamamlandı değil, **Partially completed**tir.

### Kaynak, performans, platform ve güvenlik

* 0/100/1k/10k/50k backend profil benchmark'ında dashboard yaklaşık
  0.07/0.70/5.75/57.0/283.6 ms; backup 372/383/482/1496/6169 ms; restore
  185/199/298/1314/5811 ms. Ölçeklenme yaklaşık doğrusal, mutlak süre bu
  Linux makineye özgüdür.
* Backend resource probe: thread 1 sabit; FD'nin iteration sırasında artıp
  GC/sonraki backup sonrası 4'e dönmesi gecikmeli cleanup'a işaret eder,
  kalıcı leak kanıtı değildir. 100 gerçek Kivy navigation/widget/callback
  döngüsü gerçek pencere olmadan ölçülemedi.
* `pip-audit` güncel PyPI sorgusunda DNS engeline takıldı; CVE sonucu yok.
  Bandit (18,767 satır) 7 high/36 medium raporladı; `Crypto` importları
  PyCryptodome için B413 false-positive/araç sınıflandırmasıdır, B608'ler
  sabit internal SQL fragmentlerine ilişkindir. Bu sonuç "güvenli" kanıtı
  değildir. `shell=True`, `eval`, `exec`, `pickle`, `yaml.load` production
  aramasında bulunmadı; asset worker `subprocess.run` argument listesiyle.
* CSV `open(path, 'w')` ile atomik olmayan ve umask 022 altında plaintext
  `0644` üretir. Linux genel klasörde başka local kullanıcılar okuyabilir;
  CSV P1 privacy blocker olarak yükseltildi. Windows ACL sonucu test edilmedi.
* Linux workflow statik olarak incelendi; eski yerel `0.0.4` AppImage güncel
  release kanıtı değildir. AppImage builder `continuous` URL'sini checksum
  olmadan indiriyor. Gerçek clean v0.0.9 AppImage build/run bu çevrimde yok.
  Windows installer/DPAPI/DPI/file-lock gerçek donanımda koşulmadı.

### Version, observability ve release hazırlığı

Detached `/tmp/archlence-version-mut` worktree'de version gate mutations:
installer define, workflow default ve CHANGELOG heading **yakalandı**;
Windows fallback (`0.0.1`), README'de ek stale version ve release asset adı
**kaçtı**. Gate tag mismatch'i de untagged HEAD'de başarılı gösterdi.
Workflow Windows fallback'i `inputs.version || '0.0.1'`, upgrade smoke ise
sabit `v0.0.1`/`ArchlenceSetup-0.0.1.exe` kullanıyor; v0.0.8 previous-release
contractı sınanmıyor. Mutation worktree temiz bırakıldı.

Observability statik/dinamik kapsamı P0 error paths'de exception'ın UI
katmanında yakalanabildiğini, fakat audit state'lerinin kullanıcıya bir
reconciliation alarmı olarak ulaşmadığını gösterdi. Read-only log, disk-full,
rotation failure ve gerçek UI success/failure matrisi koşulmadı. Phase 1
exception gate bypass/slack P1 blocker olarak korunur.

### Final 25 alan coverage ledger

| Alan | Durum | Kanıt / sınır | Phase 3 işi |
|---|---|---|---|
| Backup authenticity | Completed | P0-1 | authenticated manifest |
| Restore completeness | Partially completed | config mismatch | full profile contract |
| Restore failure rollback | Partially completed | DB/key rollback, config fail | atomic directory swap |
| Key lifecycle | Partially completed | Linux 67 PASS; DPAPI yok | Windows test |
| Recovery password | Completed | wrong/tampered/rotation tests | CI taşıma |
| Recurring charge | Completed | sequential+2 worker P0-2 | idempotency key |
| Recurring refund | Completed | sequential+2 worker P0-3 | unique reversal |
| Asset atomicity | Completed | P0-4 | one DB transaction |
| Debt atomicity | Completed | P0-5 | one DB transaction |
| Other financial atomicity | Partially completed | savings safe; card P0-7 | operation fault matrix |
| Concurrency | Partially completed | 4 deterministic races | asset/debt/backup races |
| Financial properties | Completed | 6 PASS/mutations | normal CI |
| Migration normal matrix | Completed | v0.0.1–v0.0.8 | CI |
| Migration fault injection | Partially completed | P1-2 one point | crash matrix |
| Input/non-finite | Partially completed | P0-6 multiple services | all services/import |
| UI/localization | Partially completed | unit coverage | real focus/DPI |
| Performance | Completed | 0–50k trend | release baseline |
| Resource leak | Partially completed | backend 100 loops | real Kivy 100 loops |
| Linux packaging | Partially completed | workflow/static only | clean build/smoke |
| Windows packaging | Blocked by environment | no Windows | hardware checklist |
| Upgrade workflow | Partially completed | fixed old baseline | dynamic v0.0.8 |
| Dependency/security | Partially completed | Bandit/static; CVE DNS-blocked | online audit |
| Observability | Partially completed | error paths/static | real UI/log faults |
| Version/release consistency | Partially completed | 3 catches/3 misses | expand gate |
| RC/soak readiness | Completed | plan/gates prepared; not executed | execute after fixes |

No ledger row is `Not started`; completed means investigated, not defect-free.

---

## 7. Totoloji düzeltmesi (sözleşme madde 5)

Property testindeki ikinci assertion kaldırıldı:

```python
final_payment = total - monthly * (installments - 1)
assert monthly * (installments - 1) + final_payment == principal
```

Cebirsel olarak `total == principal`, yani son taksiti **testin kendisi**
üretiyordu.

Yerine `test_real_installment_schedule_sums_to_the_principal` eklendi. Bu test
`paid_installments` sayacını 0'dan n-1'e getirip her adımda üretimin
raporladığı `remaining_amount` değerini **okur**; taksit dizisini üretimden
türetir, hesaplamaz.

**Mutation doğrulaması:**

| Mutation | Sonuç |
|---|---|
| `remaining_amount` anaparadan → `aylık × kalan` | **YAKALANDI** — `100.0 != 100.01`, `100.08 != 100.02`, `999.99 != 1000.00` |
| quantization kaldır | yakalamadı (bunu diğer property testi yakalıyor) |

İki test farklı davranışı koruyor; birlikte tam kapsam sağlıyorlar.

Sınanan vakalar: `100.01/2`, `100.02/12`, `1000.00/3`, `12500.00/12`,
`0.01/3`, `999999999.99/12`.

---

## 8. Backup authenticity — çözüm tasarımı (uygulanmadı)

Yalnız SHA-256 yeterli değil. Öneri:

1. **Parola türevli HMAC**: mevcut PBKDF2 çıktısından `HKDF` ile ayrı bir MAC
   anahtarı türet (domain separation: `b"archlence-backup-manifest-v2"`).
2. **Authenticated manifest**: dosya listesi, boyutlar, per-dosya digest'leri
   ve KDF parametreleri tek bir yapıda toplanıp HMAC'lensin.
3. **Format sürümü**: `BACKUP_FORMAT_VERSION = 2`; v1 paketler okunabilir
   kalsın ama **authenticated değil** diye açıkça uyarılsın.
4. **Doğrulama sırası**: önce MAC, sonra içerik. MAC geçmeden hiçbir dosya
   açılmasın (path traversal savunmasını da öne çeker).

Saldırgan parolayı bilmeden manifest'i yeniden imzalayamaz; mevcut kurulumda
ise yalnızca hash'i yeniden hesaplaması yetiyor.

---

## 9. Test edilemeyen / başlanmamış alanlar

**"Geçti" sayılamaz:**

- Encryption key lifecycle, recovery parolası senaryoları
- Concurrency / yarış durumları (deterministik harness kurulmadı)
- Resource leak (RSS, thread, fd, callback, widget)
- Dependency güvenlik taraması
- Windows runtime: DPAPI, SmartScreen, antivirüs, kurulum/kaldırma, DPI
- Gerçek Tab/klavye/DPI etkileşimi (dummy window provider)
- Backup matrisinin çoğu (truncated, path traversal, symlink, çift restore)
- Migration fault injection'ın 16 noktasından 15'i
- 20 finansal işlemin 16'sında atomicity

---

## 10. v0.0.9 için önerilen kapsam

Yeni özellik yok. Sıra:

1. P0-2, P0-3 — recurring idempotency (charge + refund)
2. P0-4, P0-5 — asset ve debt atomicity (tek transaction)
3. P0-6 — non-finite tutarları servis sınırında reddet
4. P0-1 — authenticated backup manifest (format v2)
5. P1-1 — restore rollback'i config'i kapsasın
6. P1-2 — backfill'i crash-safe/retry-safe yap
7. P1-3, P1-4 — Phase 1 istisna kapısı
8. Property testlerini normal suite'e veya CI'a taşı

Her düzeltme **önce kırmızı, sonra yeşil** testle doğrulanmalı.
