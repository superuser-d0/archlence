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

> **FAZ KAPANDI** — bkz. [`DECIMAL_PHASE_CLOSEOUT.md`](DECIMAL_PHASE_CLOSEOUT.md).
> Baseline sınıflandırmasından geriye denetlenmemiş `MIGRATE` adayı kalmadı.
> Yalnızca `float()` var diye yeni migration yapılmaz; bu sınıflandırma ancak
> yeni kod ya da yeni kanıt çıktığında yeniden açılır.
>
> **Sayı notu:** ilk turda "109" raporlanmıştı; o, yorum ve docstring
> satırlarını da sayan bir grep'ti. AST ile baseline **101**.
>
> | | Sayı |
> |---|---|
> | İlk AST baseline | **101** |
> | Güncel canlı `float()` (`60c3620`) | **104** |
>
> Canlı sayının artması başarısızlık DEĞİL: domain aritmetiğindeki çağrılar
> kaldırılırken mevcut çıktı sözleşmesini korumak için kontrollü
> `float(fiat(...))` dönüşümleri eklendi (`calculate_pnl` 4, portföy 1). Ham
> `float()` sayısı bir kalite metriği değildir — metrik aritmetik doğruluğu,
> hassasiyet sınırı, tüketici semantiği ve iş kararlarının kararlılığıdır.

---

## Kategori dağılımı

| Kategori | Adet | Karar |
|---|---|---|
| 1. domain / business calculation | **0** | — (tamamı denetlendi) |
| 2. monetary persistence boundary | 20 | keep (bilinçli) |
| 3. SQLite REAL compatibility | 11 | keep |
| 4. UI / rendering | 9 | keep |
| 5. external API compatibility | 22 | keep |
| 6. **numerical algorithm / intentional float** | **11** | keep (ölçüldü) |
| 8. **bounded/display-only monetary arithmetic / intentional float** | **4** | keep (ölçüldü) |
| 7. ambiguous / needs investigation | 8 | investigate |
| **toplam** | **101** | |

İlk turda kategori 1'de 31 çağrı vardı. `projection_service`'in 11 çağrısı
kategori 6'ya taşındı, portföy toplamının 2 çağrısı Decimal'e geçirildi ve
kapanış turunda kalan **19** adayın tamamı sonuçlandı — hiçbiri sayı düşürmek
için değil, ölçülen sonuca göre.

**Sayım düzeltmesi:** bu satırda bir süre **18** yazdı. Kapanış turunda üyeler
AST ile tek tek sayıldı ve gerçek sayının **19** olduğu görüldü; fark, önceki
turda toplamı elle taşırken yapılan bir aritmetik hataydı.

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

## Kategori 1 — domain / business calculation (**0**)

**Boş.** Baseline'daki adayların tamamı ya migrate edildi ya da ölçülerek bir
`keep` kategorisine taşındı. Son 19 adayın tüketici semantiği kapanış turunda
incelendi: [`DECIMAL_PHASE_CLOSEOUT.md`](DECIMAL_PHASE_CLOSEOUT.md).

Migrate edilenler:

| Dosya :: fonksiyon :: kalıp | Kanıt |
|---|---|
| `services/asset_service.py :: calculate_pnl` | 0,045 × 15 = 0,675 → 0,67 yerine 0,68 (PR #84) |
| `services/asset_service.py :: fetch_active_non_try_total :: total += ...` | aynı sınıf, ekrana yansıyan bir kuruş (PR #88) |

## Kategori 8 — bounded/display-only monetary arithmetic / intentional float (4, keep)

`services/asset_service.py :: invalidate_asset_data_cache` — silinen kartı
snapshot'tan cerrahi çıkarırken yapılan `card_debt` çıkarması ve `net`
toplaması.

Kategori 6'dan (numerical algorithm) **ayrı tutuluyor**: orası RK4 gibi gerçek
bir sayısal yöntem tercihi. Buradaki gerekçe farklı:

- girdiler monetary boundary'de zaten kuruşa quantize (`round(x, 2)`),
- float aritmetiği kuruş sınırını geçemiyor — kuruşun tam katı sayıların
  toplamı/farkı yarım kuruş sınırına düşmez,
- sonuç kısa ömürlü bir UI snapshot'ı; bir sonraki warm-up değeri
  veritabanından yeniden hesaplıyor,
- hiçbir business decision'ın source-of-truth'u değil (tek tüketici iki etiket).

Ölçüm: 400.000 production-gerçekçi senaryoda gösterilen kuruş **hiç**
ayrışmadı.

> **Risk notu.** Ardışık cache mutasyonlarında (12 kart silme ölçüldü) ham
> `card_debt` değerinde ~**6,8e-13** artık kalabiliyor. Bugün zararsız, çünkü
> bu ham snapshot değerini kullanan bir predicate yok. İleride bu alan `> 0`
> ya da `== 0` gibi bir iş kuralında kullanılacaksa **önce monetary
> normalization uygulanmalıdır.**

## Ölü/temizlik adayı — Decimal işi DEĞİL

`services/asset_service.py :: get_active_non_try_assets :: purchase_price =
float(decrypt(...))`

Bu fonksiyonun tek üretim çağıranı `fetch_active_non_try_total` ve o yol
`purchase_price`'ı hiç okumuyor — her yenilemede varlık başına bir AES-GCM
çözme yapılıp sonuç atılıyor. Correctness sorunu değil, gereksiz iş.
Ayrı ve bağımsız bir temizlik adayı olarak duruyor.

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
