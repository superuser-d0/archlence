# v0.0.9 Phase 3 — Devam Noktası

**Dal:** `fix/v0.0.9-reliability` · **HEAD:** `bfb2b37` · **Taban:** `d5bd35f`
**Durum:** Phase 3 TAMAMLANMADI · **Karar: RC NO-GO**

## Bu turda tamamlanan

`bfb2b37 test: restore regression coverage lost to the atomicity refactor`

Bu commit üç sessiz arıza kapattı:

1. **Normal suite kırmızıydı** (3 hata) — `tests/test_asset_sale_cash_amount.py`
   kaldırılmış bir yolu mock'luyordu, kuruş yuvarlama koruması devre dışıydı.
2. **P0-4/P0-5 reproduction'ları bayattı** — fault hiç tetiklenmiyordu.
3. **İstisna kapısı kırmızıydı** (8 handler) ve fark edilmemişti.

## Kapanış kanıtı — P0

| ID | Durum | Kanıt |
|---|---|---|
| P0-1 backup authenticity | **Closed** | reproduction PASS |
| P0-2 charge idempotency | **Closed** | reproduction PASS |
| P0-3 refund idempotency | **Closed** | reproduction PASS |
| P0-4 asset atomicity | **Closed** | 4 fault noktası, tam rollback |
| P0-5 debt atomicity | **Closed** | 3 fault noktası, tam rollback |
| P0-6 non-finite | **Closed** | reproduction PASS + nonfinite matrisi |

## Açık blocker — P1

| ID | Durum | Kalan iş |
|---|---|---|
| P1-1 restore generation atomicity | **Open** | Sözleşme madde 4 |
| P1-2 migration crash recovery | **Open** | Sözleşme madde 5 |
| P1-3 kapı bypass'ı (tuple/attribute/alias) | **Open** | Sözleşme madde 6 |
| P1-4 kapı slack'i | **Open** | Sözleşme madde 6 |

## Yeni bulgu (bu turda)

**P2-6 — Satış açıklaması ayrıntı kaybetti.** `96049ee` sonrası defter
açıklaması `"Test (TST) satıldı"`; miktar, birim fiyat ve K/Z bilgisi
kayboldu. v0.0.8'de
`"... — 0.12345678 adet, birim fiyat 2.456,78 ₺ (K/Z: +56,40)"` idi.
`mixins/asset_mixin.py` hâlâ zengin `desc` kuruyor ama `AssetSaleService`
kendi açıklamasını yazdığı için o değer **kullanılmıyor**.
Üretim düzeltmesi yapılmadı — ürün kararı gerekiyor.

## Sonraki devam noktası (dosya/görev düzeyinde)

1. **`services/backup_service.py`** — restore'u staging + durable journal ile
   tek generation'a çevir (madde 4). Fault noktaları: DB/key/config
   replacement sonrası, post-verification, success marker öncesi.
   Yeni testler `tests/` altına.
2. **`database/init_db.py`** — `PRAGMA user_version` + migration journal,
   idempotent backfill (madde 5). `scripts/audit/test_migration_fault_injection.py`
   düzeltme sonrası PASS olmalı ve `tests/` altına taşınmalı.
3. **`scripts/audit_exception_handlers.py`** — `ast.Tuple`/`ast.Attribute`/
   alias tanıma + `current == baseline` eşitliği (madde 6). Kapının kendi
   testleri `tests/` altına.
4. **`database/db.py::get_connection`** — deterministik kapatma (madde 7).
5. **`scripts/check_version_consistency.py`** — mutation matrisi (madde 8).
6. **`.github/workflows/build-windows.yml`** — `0.0.1` fallback'i kaldır,
   upgrade smoke gerçek önceki sürümü seçsin (madde 9).
7. **CHANGELOG `## Unreleased`** + `docs/` güncellemeleri (madde 11).

## Doğrulama durumu

```
normal suite      703 test OK (skip 2)
bloklayan lint    0
istisna kapısı    145 handler (bilinçli +1)
sürüm kapısı      0.0.8 / tag v0.0.8
adversarial       6/6 PASS
compileall        temiz
git diff --check  temiz
```

Push/PR/tag/release YOK. Sürüm bump YOK.
