# v0.0.9 Phase 3 — Test Matrisi

> **BU BELGE BİR ANLIK GÖRÜNTÜDÜR — `493dd3c` HEAD'inde yazıldı.**
> Aşağıdaki "Denetlenmeyen / açık alanlar" tablosu O AN doğruydu;
> **bugünün statüsü değildir.** Güncel durum:
> `V0_0_9_PHASE_3_CONTINUATION.md` ve `V0_0_9_PRE_WINDOWS_GATE.md`.

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

| Alan | Status (`493dd3c`) | Sonradan |
|---|---|---|
| COMMITTED-cleanup crash senaryosu | **Open** | Kapandı — `efadc1c` |
| Connection cleanup (FD) | **Open** | Kapandı — `28e43f0`; FD ölçümünün yerini açma/kapama sayımı aldı |
| Version mutation matrisi (16 vaka) | **Open** | Kapandı — `5d05084` + `1223935` |
| Packaging/upgrade gate | **Open** | Kapandı — `ddda5ed` |
| P2-6 asset açıklama | **Open** | Kapandı — `8b1744e` |
| Gerçek Windows runtime | **Blocked by environment** | Hâlâ blocked |
| Gerçek Tab/DPI/klavye | **Blocked by environment** | Hâlâ blocked |
| Dependency güvenlik taraması | **Not started** | Hâlâ açık — P3, araç ortamda yok |
