# v0.0.9 Phase 2 — Release Gate

## Final Phase 2 decision (2026-08-06)

**NO-GO.** This is an audit-only branch; no production correction has been
made. A release is forbidden until every P0/P1 below has a production fix,
a normal-CI regression test, and a fault/mutation recheck.

### P0 release blockers

1. P0-1 backup manifest/database authenticity.
2. P0-2 recurring charge idempotency (sequential and concurrent).
3. P0-3 recurring refund idempotency (sequential and concurrent).
4. P0-4 asset sale cross-write atomicity.
5. P0-5 debt payment cross-write atomicity.
6. P0-6 non-finite monetary value acceptance and persistent `-inf`/`NULL` corruption.
7. P0-7 credit-card check/write race permits debt 120 against a 100 limit.

### P1 release blockers

1. P1-1 restore must preserve DB, key and config as one generation on every failure path.
2. P1-2 interrupted migration must resume/rollback backfill deterministically.
3. Phase 1 A-1 exception-handler gate bypass.
4. Phase 1 A-2 exception baseline slack.
5. plaintext CSV `0644` privacy exposure on Linux/shared-user threat model.

### Required Phase 3 gates

* Move adversarial financial, property, concurrency and migration reproductions
  into normal CI once fixed; do not leave them audit-only.
* Pass v0.0.1–v0.0.8 populated migrations and restore failure matrix.
* Pass backup tamper and archive allow-list tests.
* Pass finite-domain matrix for every money entry point.
* Complete clean Linux package/AppImage smoke; complete real Windows installer,
  upgrade, file-lock, DPAPI and DPI checklist or document explicit risk acceptance.
* Run three-day RC: day 1 clean install/demo/reconciliation/backup; day 2
  navigation, locale/theme, recurring, asset refresh and logs; day 3 previous
  release upgrade, restore, persistence, uninstall/reinstall. Any P0/P1 resets RC.

Taban: `d5bd35f` · Tarih: 2026-08-06

## Karar: **NO-GO**

Altı P0 ve dört P1 doğrulandı. Hiçbiri düzeltilmedi (bu görevde üretim kodu
değiştirilmedi).

---

## P0 release blocker

| ID | Bulgu | Doğrudan kullanıcı etkisi |
|---|---|---|
| P0-1 | Backup manifest'i authenticated değil | Değiştirilmiş yedek sahte bakiyeyle geri yüklenir |
| P0-2 | Aynı vade iki kez tahsil ediliyor | Paranın iki kez çıkması |
| P0-3 | Aynı tahsilat iki kez iade ediliyor | Paranın iki kez girmesi |
| P0-4 | Varlık satışı atomik değil | Hem nakit hem varlık elde kalıyor |
| P0-5 | Borç ödemesi atomik değil | Ödenmemiş taksit ödenmiş sayılıyor |
| P0-6 | Infinity bakiyeyi bozuyor | Sessiz veri kaybı + yanlış net servet |

## P1 release blocker

| ID | Bulgu |
|---|---|
| P1-1 | Başarısız restore config'i geri almıyor (karma durum) |
| P1-2 | Migration yarıda kesilirse backfill bir daha çalışmıyor |
| P1-3 | İstisna kapısı tuple/attribute/alias biçimlerini görmüyor (Phase 1 A-1) |
| P1-4 | İstisna kapısı baseline slack'ini kontrol etmiyor (Phase 1 A-2) |

---

## GO için somut koşullar

**Düzeltmeler** — her biri önce kırmızı, sonra yeşil testle doğrulanmış:

- [ ] P0-2 recurring charge idempotency (idempotency anahtarı veya dönem kilidi)
- [ ] P0-3 recurring refund idempotency
- [ ] P0-4 varlık satışı tek SQLite transaction
- [ ] P0-5 borç ödemesi tek SQLite transaction
- [ ] P0-6 non-finite tutarlar servis sınırında `ValueError`
- [ ] P0-1 authenticated backup manifest (format v2, parola türevli HMAC)
- [ ] P1-1 restore rollback config'i kapsıyor
- [ ] P1-2 backfill crash-safe ve retry-safe
- [ ] P1-3 + P1-4 istisna kapısı

**Doğrulama:**

- [ ] Normal suite yeşil
- [ ] Adversarial reproduction'lar **yeşile döndü** (kusurlar kapandığı için)
- [ ] Property testleri normal suite'e veya CI'a taşındı
- [ ] Migration v0.0.1–v0.0.8 matrisi yeşil
- [ ] Fault injection sonrası rollback doğrulandı
- [ ] Backup tamper testi yeşil

**Kapsam:**

- [ ] Concurrency harness kuruldu, en az iki worker yarışı sınandı
- [ ] Resource leak ölçümü yapıldı (en az backend: thread, fd, connection)
- [ ] Migration fault injection en az 5 noktaya genişletildi

**Süreç:**

- [ ] Birkaç günlük RC/soak tamamlandı, P0/P1 çıkmadı
- [ ] Gerçek Windows test sonuçları **veya** açık risk kaydı mevcut

---

## NO-GO koşulları

1. Yukarıdaki P0'lardan herhangi biri açık.
2. Bir düzeltme mutation ile doğrulanamıyor.
3. Soak sırasında finansal değişmez ihlali, çift işlem veya veri kaybı.
4. Migration matrisinde veri değişimi.

---

## Windows gerçek donanım kontrol listesi

Bu maddeler CI ile kapatılamaz ve bu denetimde **kapsanmadı**:

- [ ] DPAPI anahtar saklama/okuma, keystore reddi davranışı
- [ ] Kurtarma akışı uçtan uca
- [ ] SmartScreen, antivirüs karantinası, dosya kilidi
- [ ] Kurulum / yükseltme / kaldırma / yeniden kurulum
- [ ] Uygulama açıkken yükseltme
- [ ] %125 / %150 / %200 DPI
- [ ] Gerçek Tab sırası ve klavye navigasyonu
