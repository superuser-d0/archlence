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
