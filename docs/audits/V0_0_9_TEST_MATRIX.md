# v0.0.9 Denetim — Test Matrisi

Denetim commit'i: `d5bd35f` · Tarih: 2026-08-06

**Mutation sütunu**, korunan davranış bilerek bozulduğunda testin kırmızı olup
olmadığını gösterir. `—` işareti mutation uygulanmadığını belirtir ve **kanıt
yokluğu** anlamına gelir, geçme anlamına gelmez.

## Finansal doğruluk

| Senaryo | Beklenen değişmez | Sonuç | Mutation | Kanıt |
|---|---|---|---|---|
| Taksit kalan borcu anaparadan türetiliyor | `kalan = anapara − aylık × ödenen` | geçti | **doğrulandı** (FAILED ×4) | `test_transaction_service` |
| Taksit aylık tutarı Decimal ile bölünüyor | `fiat(Decimal(x)/n)` | geçti | **KAÇTI** | bulgu A-3 |
| Varlık alımı nakit tutarı kuruşa yuvarlanıyor | `fiat(fiyat × miktar)` | geçti | **doğrulandı** (FAILED ×3) | `test_asset_purchase_flow` |
| Varlık satışı nakit tutarı kuruşa yuvarlanıyor | aynı | geçti | — | `test_asset_sale_cash_amount` |
| Borç tutarları saklanırken yuvarlanıyor | `fiat()` | geçti | **doğrulandı** (FAILED ×2) | `test_debt_amount_quantisation` |
| Borç toplamı = aylık × vade | `total == monthly × n` | geçti | — | `test_debt_total_matches_ledger` |
| Kart limiti kuruş hassasiyetinde | `fiat(a) > fiat(b)` | geçti | **doğrulandı** (FAILED ×1) | `test_money_decisions_precision` |
| Birikim çekimi kuruş hassasiyetinde | `ROUND(...,2)` | geçti | **doğrulandı** (ERROR ×1) | `test_money_decisions_precision` |
| Hedef tamamlanması kuruş hassasiyetinde | `ROUND(...,2)` | geçti | — | `test_money_decisions_precision` |

## Defter (ledger) bütünlüğü

| Senaryo | Beklenen değişmez | Sonuç | Mutation | Kanıt |
|---|---|---|---|---|
| Her bakiye değişimi ledger event yazar | balance ↔ event eşleşir | geçti | **doğrulandı** (FAILED ×7) | tam suite |
| Var olmayan hesaba yazım reddedilir | `rowcount == 0 → raise` | geçti | **doğrulandı** (FAILED ×2) | tam suite |
| Kart silme cascade yapıyor | öksüz kayıt kalmaz | geçti | — | elle inceleme |
| FK kısıtı zorlanıyor | `PRAGMA foreign_keys = ON` | **başarısız** | — | bulgu A-4 |

## Şifreleme

| Senaryo | Beklenen değişmez | Sonuç | Mutation | Kanıt |
|---|---|---|---|---|
| Write path şifrelemeyi atlarsa yakalanır | envanter gerçek yazıma bağlı | geçti | **doğrulandı** (FAILED ×4+ERROR) | `test_encrypted_field_inventory` |
| Envanterdeki her tablo gerçekten yazılıyor | 6 tablo / 13 sütun | geçti | — | aynı dosya |
| Migration şifreli alanları koruyor | çözülebilirlik | geçti | — | migration koşumu |

## Cache ve stale sonuç

| Senaryo | Beklenen değişmez | Sonuç | Mutation | Kanıt |
|---|---|---|---|---|
| Cache anahtarı dönem filtresini içerir | filtre değişince yeniden hesap | geçti | **doğrulandı** (FAILED ×2) | tam suite |
| Cache anahtarı revision içerir | veri değişince yeniden hesap | geçti | **doğrulandı** (FAILED ×2) | tam suite |
| Eski kategori yüklemesi yenisini ezmez | generation token | geçti | **doğrulandı** (FAILED ×1) | tam suite |

## Şema ve migration

| Senaryo | Veri profili | Sonuç | Kanıt |
|---|---|---|---|
| v0.0.1 → current | 1 hesap, 3 şifreli işlem | geçti | bakiye/sayı/çözülebilirlik korundu |
| v0.0.4 → current | aynı | geçti | aynı |
| v0.0.6 → current | aynı | geçti | aynı |
| Migration idempotent | aynı | geçti | ikinci koşum sorunsuz |
| `user_version` işareti | — | **başarısız** | bulgu A-5 |
| Migration fault injection | — | **denenmedi** | — |
| Dolu/gerçekçi eski profil | — | **denenmedi** | — |

## CI kapıları

| Kapı | Beklenen davranış | Sonuç | Kanıt |
|---|---|---|---|
| Yeni geniş handler (yeni fonksiyon) | kırılır | geçti | v0.0.6'da doğrulanmıştı |
| `except (Exception,)` | kırılmalı | **başarısız** | bulgu A-1 |
| `except builtins.Exception` | kırılmalı | **başarısız** | bulgu A-1 |
| `except _Alias` | kırılmalı | **başarısız** | bulgu A-1 |
| Baseline slack'i | kırılmalı | **başarısız** | bulgu A-2 |
| Slack'e sızan yeni handler | kırılmalı | **başarısız** | bulgu A-2 |
| Sürüm tutarlılığı | kırılır | geçti | `0.0.8 / tag v0.0.8` |
| Bloklayan lint | 0 bulgu | geçti | `F821,F822,F823,E722` |

## Denetlenmeyen alanlar

Aşağıdaki satırların hiçbiri çalıştırılmadı. **Boş sonuç, geçti değildir.**

| Alan | Durum |
|---|---|
| Concurrency / yarış durumları | denetlenmedi |
| UI, localization, input fuzzing | denetlenmedi |
| Backup/restore hata senaryoları | denetlenmedi |
| Performans, kaynak sızıntısı | denetlenmedi |
| Windows paketleme ve kurulum | ortam yok |
| DPAPI / OS keystore | ortam yok |
| Dependency güvenlik taraması | denetlenmedi |
| Price provider hata varyasyonları | denetlenmedi |
