# `float()` kullanımlarının sınıflandırması — Decimal geçişinin kaynağı

**Taban:** `main` = `12e28bf` · **Kapsam:** `services/`, `database/`, `utils/`
**Yöntem:** grep değil **AST** (`ast.Call` → `Name(id="float")`)

Bu belge geçişin kaynak listesi. Bir çağrının hangi kategoride olduğu
değiştiğinde burası güncellenir; kararın gerekçesi ilgili denetim belgesine
bağlanır.

## Referans biçimi

Aktif kalemlerin kimliği **dosya + fonksiyon + kod kalıbı**:

```
services/asset_service.py :: fetch_active_non_try_total :: total += float(asset["quantity"]) * float(price)
```

Satır numarası varsa yalnız parantez içinde, yardımcı bilgidir — kimlik değil.
Sebebi ölçülerek görüldü: bu belgenin ilk taslağındaki `asset_service.py`
satır numaraları, `calculate_pnl` geçişi (PR #84) dosyayı uzattığı için
**tek bir merge sonrasında** kaymıştı. Kod kalıbı ise `grep` ile bulunabilir
ve fonksiyon adı yeniden adlandırılmadıkça sabit kalır.

> **Sayı notu:** ilk turda "109" olarak raporlanmıştı; o, yorum ve docstring
> satırlarını da sayan bir grep'ti. AST ile gerçek çağrı sayısı **101**.

---

## Kategori dağılımı

| Kategori | Adet | Karar |
|---|---|---|
| 1. domain / business calculation | **18** | migrate |
| 2. monetary persistence boundary | 20 | keep (bilinçli) |
| 3. SQLite REAL compatibility | 11 | keep |
| 4. UI / rendering | 9 | keep |
| 5. external API compatibility | 22 | keep |
| 6. **numerical algorithm / intentional float** | **11** | keep (ölçüldü) |
| 7. ambiguous / needs investigation | 8 | investigate |
| **toplam** | **101** | |

İlk turda kategori 1'de 31 çağrı vardı. `projection_service`'in 11 çağrısı
ölçüm sonrasında kategori 6'ya taşındı, portföy toplamının 2 çağrısı ise
Decimal'e geçirildi — geriye **18** kaldı. İkisi de sayı düşürmek için değil,
ölçülen sonuca göre.

---

## Kategori 6 — numerical algorithm / intentional float (11)

`services/projection_service.py` — RK4 servet projeksiyonu ve senaryo
aritmetiği. **Ölçülerek** bu kategoriye alındı; varsayımla değil.

| Dosya :: fonksiyon :: kalıp | Adet |
|---|---|
| `services/projection_service.py :: project_wealth_series :: float(initial_wealth / daily_income / daily_expense / r)` | 4 |
| `services/projection_service.py :: simulate_scenario :: float(base_balance / base_daily_income / base_daily_expense / income_delta_pct / expense_delta_pct / one_time_adjustment)` | 6 |
| `services/projection_service.py :: simulate_scenario :: "r": float(r)` (çıktı sözlüğü) | 1 |

Karar: **Keep float**. Ölçümün özeti:

- `r = 0`'da RK4'ün kesme hatası **yapısal olarak sıfır**, yani orada
  gözlenen her sapma saf temsil hatası.
- Varsayılan `r = 0.0001`'de float temsil hatası kesme hatasını **50–1.200 kat
  geçiyor** — yani "sayısal yöntem zaten daha çok kaybediyor" savunması bu
  parametrede geçerli DEĞİL.
- Buna rağmen 22 vakanın 21'inde kuruş aynı; `difference` ve `goes_negative`
  kararları hiç değişmiyor; float-baskın vakalarda bağıl hata ~1e-16.
- Decimal çekirdek 4,1× daha pahalı ve ölçülebilir bir ürün kazancı yok.

Tam ölçüm ve gerekçe: [`PROJECTION_FLOAT_AUDIT.md`](PROJECTION_FLOAT_AUDIT.md).
Yeniden üretmek için: `python -m scripts.audit.measure_projection_precision`.

**Bu kategori "external API compatibility" DEĞİLDİR.** Oradaki değerler
kaynakta zaten float; buradakiler bizim ürettiğimiz sayılar ve float olmaları
bilinçli bir sayısal tercih.

---

## Kategori 1 — domain / business calculation (20, migrate)

Kalan gerçek aday listesi. Değer bu noktadan sonra **Python'da aritmetiğe**
giriyor.

| Dosya :: fonksiyon :: kalıp | Adet | Değer | Durum |
|---|---|---|---|
| `services/asset_service.py :: get_active_non_try_assets :: quantity = float(decrypt(row["quantity"], SECRET_KEY))` | 1 | miktar — **ölçüldü, kaybı sıfır**; saklanan metin zaten bir float'ın repr'ı. Kategori 3'e taşınmayı hak ediyor, ayrı turda | 
| `services/asset_service.py :: get_active_non_try_assets :: purchase_price = float(decrypt(row["purchase_price"], SECRET_KEY))` | 1 | alış fiyatı — **kapsam dışı çıktı**: piyasa değeri yolu bunu hiç okumuyor. Ayrıca kullanılmayan çözme, temizlik adayı | 
| `services/asset_service.py :: invalidate_asset_data_cache :: float(old_summary.get(...))` | 4 | nakit, kart borcu, net servet düzeltmesi | bekliyor |
| `database/db.py :: get_active_debts :: float(decrypt(r["total_amount"] / r["monthly_payment"], SECRET_KEY))` | 2 | borç toplamı, aylık taksit | bekliyor |
| `database/db.py :: get_all_assets :: float(decrypt(r["purchase_price"] / r["quantity"], SECRET_KEY))` | 2 | alış fiyatı, miktar | bekliyor |
| `database/db.py :: get_asset_by_id :: float(decrypt(r["purchase_price"] / r["quantity"], SECRET_KEY))` | 2 | alış fiyatı, miktar | bekliyor |
| `database/db.py :: get_asset_transaction_history :: dec_amount = float(decrypt(str(r["amount"]), SECRET_KEY))` | 1 | işlem tutarı | bekliyor |
| `database/db.py :: get_active_recurring_payments :: dec_amount = float(decrypt(r["amount"], SECRET_KEY))` | 1 | tutar | bekliyor |
| `services/history_service.py :: get_balance_at :: sum(float(v) for v in ...savings_goals...)` | 1 | birikim hedefleri toplamı | bekliyor |
| `services/insights_service.py :: _safe_decrypt_float :: return float(decrypt_decimal(...))` | 1 | tutar | bekliyor — **fan-out yüksek**, `statistics.fmean`/`pstdev` dahil çok sayıda tüketici |
| `services/calendar_service.py :: get_day_transactions :: amount = float(decrypt(str(row["amount"]), SECRET_KEY))` | 1 | tutar | bekliyor |
| `services/recurring_service.py :: _plain_amount :: return float(decrypt(str(raw), SECRET_KEY))` | 1 | tutar | bekliyor |

`transaction_service` ve `price_service`'teki kalemler tamamlanan dilimlerle
birlikte çözüldü ya da kategori değiştirdi; ayrıntı ilgili PR'larda.

---

---

> **Aşağıdaki "keep" kategorileri satır numarasıyla listeleniyor ve bunlar
> anlık görüntüdür.** Bilerek yeniden biçimlendirilmediler: bu kalemlerde
> karar verilmiş durumda, yani kimse onları kod içinde bulmak zorunda değil.
> Aktif olan kalemler (kategori 1, 6, 7) yukarıda dosya + fonksiyon + kalıp
> ile tanımlı. Bir "keep" kalemi yeniden gündeme gelirse aynı biçime çevrilir.

## Kategori 2 — monetary persistence boundary (20, keep)

Kalıp: `float(fiat(x))` — Decimal ile karar verilmiş, kuruşa yuvarlanmış değer
`REAL` sütuna yazılmadan hemen önce düşürülüyor. `sqlite3`'ün `Decimal`
adaptörü yok; bunlar borç değil, bilinçli sınır.

`transaction_service.py:89` · `db.py:601` · `db.py:120,121` ·
`savings_service.py:38,39,111,175` · `account_service.py:67,68` ·
`asset_sale_service.py:60,62` · `asset_purchase_service.py:91` ·
`debt_payment_service.py:21` · `recurring_service.py:195,245` ·
`transaction_service.py:458,459,463`

## Kategori 3 — SQLite REAL compatibility (11, keep)

Sütun zaten `REAL`; gelen değer zaten ikili float. `Decimal`'a çevirmek kaybı
geri getirmez, yalnız yerini gizler. Ölçümü:
[`V0_0_9_PRE_WINDOWS_GATE.md`](V0_0_9_PRE_WINDOWS_GATE.md) ve
`scripts/audit/measure_real_column_drift.py`.

## Kategori 4 — UI / rendering (9, keep)

`formatters.py:89,93,107,157` · `account_service.py:395,396` ·
`dashboard_period_service.py:48` · `insights_service.py:589` ·
`key_provider.py:195`

## Kategori 5 — external API compatibility (22, keep)

pandas `Series` / yfinance / CoinGecko / Frankfurter dönüşleri ve hesap
makinesi AST'si zaten float üretiyor. `Decimal`'a çevirmek **yanlış bir
kesinlik izlenimi** verir: kaynak veri o hassasiyette değil.

## Kategori 7 — ambiguous / needs investigation (8)

| Dosya :: fonksiyon :: kalıp | Adet | Durum |
|---|---|---|
| `services/asset_service.py :: _read_cached_portfolio :: float(entry.get("quantity", -1)) != float(asset.get("quantity", 0))` | 4 | Float eşitlik karşılaştırması — **araştırıldı, reproduction yok**, dokunulmadı. JSON/SQLite/decrypt round-trip'lerinin üçü de kayıpsız; gerçek yol iki okumada da HIT. Bkz. `tests/test_portfolio_cache_identity.py` |
| `services/asset_service.py :: _read_cached_prices :: {row["symbol"]: float(row["price"]) ...}` | 1 | Fiyat cache haritası: kaynak dış API, tüketici portföy aritmetiği. Sınırın hangi tarafında durduğuna karar verilmeli — **portföy toplamı denetiminde ele alınacak** |
| `services/asset_service.py :: _fetch_live_try_prices :: prices[full_code] = float(value)` / `1.0 / float(rate)` | 4 | Aynı sınır sorusu; dış sağlayıcıdan gelen fiyatlar | 
| `services/migration_service.py :: parse_transactions_csv :: amount = float(raw_amount)` | 1 | CSV içe aktarma; `float()` kasıtlı, hemen ardından `math.isfinite` ile inf/nan eleniyor. `Decimal("nan")` sessizce üretileceği için dönüşüm güvenliği **azaltabilir** |

---

## Tamamlanan dilimler

| Dilim | Sonuç | Kayıt |
|---|---|---|
| `calculate_pnl` | Decimal'a geçti; 0,045×15 gibi yarım kuruş sınırlarında bir kuruş düzeldi | PR #84 |
| `projection_service` | **Keep float** (ölçüldü) | [`PROJECTION_FLOAT_AUDIT.md`](PROJECTION_FLOAT_AUDIT.md), PR #87 |
| Portföy toplamı | **Decimal'e geçti** — `quantity × price` yuvarlama sınırında bir kuruş kaybediyordu (15 × 0,045 → 0,67 yerine 0,68). Çıktı sınırı `float(fiat(total))`; `float(total)` tek başına hatayı geri getiriyordu | [`PORTFOLIO_TOTAL_AUDIT.md`](PORTFOLIO_TOTAL_AUDIT.md), PR #88 |
