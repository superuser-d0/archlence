# v0.0.9 Phase 2 — Release Gate

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
