# v0.0.9 Phase 3 — Test Matrisi

HEAD: `493dd3c` · Normal suite: **741 test OK** (skip 2)

## Normal suite'e eklenen reliability testleri

| Test dosyası | Adet | Kapsam | Mutation doğrulandı |
|---|---|---|---|
| `test_restore_generation_atomicity.py` | 7 | 5 fault noktası, başarılı restore, bozuk/tanınmayan journal | **evet** — config rollback + journal konumu |
| `test_startup_recovery_integration.py` | 8 | sözleşme + **çağrı sırası** + fail-closed | **evet** — 3 mutation |
| `test_migration_retry_safety.py` | 4 | ALTER sonrası kesinti, idempotency, boş string, credit_limit | **evet** — backfill'i bloğa geri al |
| `test_exception_gate.py` | 19 | 5 geniş biçim, 4 takma ad, dar handler, 6 baseline vakası | **evet** — 4 bypass + slack |
| `test_asset_sale_cash_amount.py` | 4 | gerçek servis üzerinden quantization | **evet** — `fiat()` kaldır |

## Çağrı sırası kanıtı (P1-1)

```
recovery < key_load < database_init < config_store
```

Mutation sonuçları:

| Mutation | Kırılan assertion |
|---|---|
| Startup çağrısını kaldır | `'recovery' not found in [...]` |
| DB init sonrasına taşı | `'database_init' unexpectedly found` |
| Bozuk journal'ı yut | `StartupRecoveryError not raised` |

## Fault hook tetiklenme kanıtı

| Servis | Fault noktaları | Hook çağrıldı doğrulaması |
|---|---|---|
| `AssetSaleService.sell` | 4 | `assertEqual(fired, [hook_point])` |
| `DebtPaymentService.pay_auto` | 3 | aynı |

Mutation: servisten hook kaldırılınca → `Lists differ: [] != ['after_asset_write']`

## Migration matrisi

| Sürüm | state | fresh_schema | idempotent | user_version |
|---|---|---|---|---|
| v0.0.1 – v0.0.8 | True | True | True | **0** |

`user_version` hâlâ 0 — A-5 (P3) açık.

## Denetlenmeyen / açık alanlar

| Alan | Status |
|---|---|
| COMMITTED-cleanup crash senaryosu | **Open** |
| Connection cleanup (FD) | **Open** |
| Version mutation matrisi (16 vaka) | **Open** |
| Packaging/upgrade gate | **Open** |
| P2-6 asset açıklama | **Open** |
| Gerçek Windows runtime | **Blocked by environment** |
| Gerçek Tab/DPI/klavye | **Blocked by environment** |
| Dependency güvenlik taraması | **Not started** |
