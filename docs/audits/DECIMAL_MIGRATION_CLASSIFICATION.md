# `float()` kullanımlarının sınıflandırması — Decimal geçişinin kaynağı

**Taban:** `main` = `12e28bf` · **Kapsam:** `services/`, `database/`, `utils/`
**Yöntem:** grep değil **AST** (`ast.Call` → `Name(id="float")`)

Bu belge geçişin kaynak listesi. Bir çağrının hangi kategoride olduğu
değiştiğinde burası güncellenir; kararın gerekçesi ilgili denetim belgesine
bağlanır.

> **Sayı notu:** ilk turda "109" olarak raporlanmıştı; o, yorum ve docstring
> satırlarını da sayan bir grep'ti. AST ile gerçek çağrı sayısı **101**.

---

## Kategori dağılımı

| Kategori | Adet | Karar |
|---|---|---|
| 1. domain / business calculation | **20** | migrate |
| 2. monetary persistence boundary | 20 | keep (bilinçli) |
| 3. SQLite REAL compatibility | 11 | keep |
| 4. UI / rendering | 9 | keep |
| 5. external API compatibility | 22 | keep |
| 6. **numerical algorithm / intentional float** | **11** | keep (ölçüldü) |
| 7. ambiguous / needs investigation | 8 | investigate |
| **toplam** | **101** | |

İlk turda kategori 1'de 31 çağrı vardı. `projection_service`'in 11 çağrısı
ölçüm sonrasında kategori 6'ya taşındı (aşağıda), geriye **20** kaldı.

---

## Kategori 6 — numerical algorithm / intentional float (11)

`services/projection_service.py` — RK4 servet projeksiyonu ve senaryo
aritmetiği. **Ölçülerek** bu kategoriye alındı; varsayımla değil.

| Satır | Değer |
|---|---|
| 17-20 | `initial_wealth`, `daily_income`, `daily_expense`, `r` — girdi normalizasyonu |
| 70-75 | `base_balance`, `base_income`, `base_expense`, `income_pct`, `expense_pct`, `adjustment` |
| 111 | `r` — senaryo çıktısındaki oran |

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

| Yer | Değer | Durum |
|---|---|---|
| `asset_service.py:1165` (×2) | `total += float(qty) * float(price)` — portföy toplamı | **sıradaki dilim** |
| `asset_service.py:979-980` (×2) | miktar, alış fiyatı (decrypt → float) | sıradaki dilim |
| `asset_service.py:160,161,163,165` (×4) | nakit, kart borcu, net servet düzeltmesi | bekliyor |
| `db.py:264,265` (×2) | borç toplamı, aylık taksit | bekliyor |
| `db.py:310,311,344,345` (×4) | alış fiyatı, miktar | bekliyor |
| `db.py:416,515` (×2) | işlem tutarı | bekliyor |
| `history_service.py:202` | birikim hedefleri toplamı | bekliyor |
| `insights_service.py:58` | `_safe_decrypt_float` | bekliyor — fan-out yüksek |
| `calendar_service.py:58` | tutar | bekliyor |
| `recurring_service.py:229,397` (×2) | tutar | bekliyor |

`transaction_service.py:250,317,489,568,609` ve `price_service.py:492,493`
tamamlanan dilimlerle birlikte çözüldü ya da kategori değiştirdi; ayrıntı
ilgili PR'larda.

---

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

| Yer | Durum |
|---|---|
| `asset_service.py:589,590` | Float eşitlik karşılaştırması — **araştırıldı, reproduction yok**, dokunulmadı. Bkz. `tests/test_portfolio_cache_identity.py` |
| `asset_service.py:1017,1075,1076,1101,1102` | Fiyat cache haritası: kaynak dış API, tüketici portföy aritmetiği. Sınırın hangi tarafında durduğuna karar verilmeli |
| `migration_service.py:262` | CSV içe aktarma; `float()` kasıtlı, `math.isfinite` ile inf/nan eleniyor. `Decimal("nan")` sessizce üretileceği için dönüşüm güvenliği AZALTABİLİR |

---

## Tamamlanan dilimler

| Dilim | Sonuç | Kayıt |
|---|---|---|
| `calculate_pnl` | Decimal'a geçti; 0,045×15 gibi yarım kuruş sınırlarında bir kuruş düzeldi | PR #84 |
| `projection_service` | **Keep float** (ölçüldü) | [`PROJECTION_FLOAT_AUDIT.md`](PROJECTION_FLOAT_AUDIT.md), PR #87 |
| Portföy toplamı | denetim bekliyor | — |
