# Portföy piyasa değeri toplamı — ölçüm ve karar: **Decimal çarpım + Decimal akümülatör**

**Tarih:** 2026-08-11 · **Taban:** `main` = `8f969d3`
**Denetlenen:** `services/asset_service.py :: fetch_active_non_try_total`
**Kapsam:** güncel piyasa değeri. Maliyet/K/Z bu denetimin konusu değil.

---

## 1. Üç katman ayrı ölçüldü

```
A = mevcut üretim   float(decrypt_text) * float(price), float birikim
B = aritmetik-only  Decimal(str(float_qty)) * Decimal(str(price)), Decimal birikim
C = kaynak-koruyan  Decimal(decrypt_text)  * Decimal(str(price)), Decimal birikim

|A−B| = çarpım + birikim sırasında float'ın eklediği hata
|B−C| = miktarın decrypt sonrası ERKEN float'a düşürülmesinin kaybı
```

Fiyat üç modelde de `Decimal(str(price_float))`: fiyat SQLite `REAL`
sütunundan ve dış sağlayıcılardan float olarak geliyor. **Upstream'de kaybolan
hassasiyet burada geri getirilemez**; olmayan kesinlik icat edilmedi.

| Katman | Ölçülen hata | Kuruşa yansıyor? | Prod-gerçekçi? | Karar |
|---|---|---|---|---|
| decrypt metni → float quantity | **0** — tüm vakalarda `\|B−C\| = 0` | hayır | — | dokunulmadı |
| `quantity × price` | 1e-16 ham, **yuvarlama sınırında 1 kuruş** | **evet** | **evet** | **Decimal** |
| N değer birikimi | n=1000'de 1,34e-8 (1,3e-6 kuruş) | hayır | evet | Decimal (bedava) |
| toplama sırası | üç sırada da aynı | hayır | evet | dokunulmadı |
| callback / çıktı sınırı | ham float, yuvarlama yok | **evet, dolaylı** | evet | `float(fiat(total))` |

## 2. `decrypt → float` katmanının kaybı sıfır — ve sebebi yapısal

`|B−C| = 0` çıktı, ölçülen her portföyde. Sebep yazma yolunda:

```python
# asset_purchase_service.create_purchase
qty = float(quantity)              # float'a BURADA düşüyor
... encrypt(str(qty), SECRET_KEY)  # saklanan metin bir float'ın repr'ı
```

Miktar diske yazılırken zaten float'tan geçtiği için `Decimal(metin)` ile
`Decimal(str(float(metin)))` birebir aynı. Okuma tarafında "erken float'a
düşürme kaybı" yok; kayıp (varsa) yazmada olmuş.

Satış yolu farklı — `remaining = owned - sold` Decimal'de hesaplanıp
`str(Decimal)` yazılıyor, yani saklanan metin teorik olarak bir double'ın
kısa gösteriminden daha fazla haneli olabilirdi. Ölçüldü: `0,10 − 0,03 →
"0.07"`, orada da `|B−C| = 0`. Miktarlar politika gereği en fazla 8 ondalık
taşıdığı için üretilemedi.

**Sonuç:** miktarı upstream'de Decimal olarak korumak (seçenek D) ölçümle
desteklenmiyor.

## 3. Çarpım katmanı — gerçek kuruş farkı, gerçek politika içinde

| Vaka | A (mevcut) | C (exact) | A kuruş | C kuruş |
|---|---|---|---|---|
| 15 kripto × 0,045 TL | 0.6749999999999999 | 0,6750 | **0,67** | **0,68** |
| 3 hisse × 1,005 TL | 3.0149999999999997 | 3,0150 | **3,01** | **3,02** |
| 0,00000015 × 4.500.000 TL | 0.6749999999999999 | 0,675000000 | **0,67** | **0,68** |
| 2,675 gram altın × 1,00 TL | 2.675 | 2,6750 | 2,68 | 2,68 |
| 7 hisse × 12,345 TL | 86.415 | 86,4150 | 86,42 | 86,42 |

Üçü de politikaya uygun: kripto 8 hane, hisse 6 hane, fiyatlar iki-üç ondalık.
Tek bir uydurma örnek değil.

## 4. Birikim ve sıra — üretilemedi

- Gerçekçi n=1, 2, 10, 100, 1000: `|A−B|` en fazla 1,34e-8 → **1,3e-6 kuruş**.
- Sıra bağımlılığı: DB sırası / küçükten büyüğe / büyükten küçüğe — n=10, 100,
  1000'de ve sentetik "1 devasa + 999 mikro" portföyünde **üçü de aynı kuruş**.
- Sentetik uçlar (1e8 + 999×1e-8): 4,9e-4 kuruş.

Toplama sırasına özel bir düzeltme **eklenmedi**; kullanıcıya yansıyan bir sıra
hatası üretilemedi.

## 5. Çıktı sınırı — `float(total)` yeterli DEĞİL

Tüketici taraması: `result["total"]` tek yerde kullanılıyor —
`mixins/account_mixin.py :: _apply_active_assets_result` → `current.balance =
_fmt(total)`, ve `_fmt` `f"₺{value:,.2f}"`. Yani **gösterim sınırı**;
`_asset_data_cache` içinde saklanıp yine yalnız gösteriliyor. Başka parasal
aritmetiğe, net servet toplamına veya bir karşılaştırmaya girmiyor
(`get_net_worth` yalnız hesap bakiyelerinden hesaplanıyor).

Bu yüzden erken quantization riski yok ve sınır `fiat()` ile daraltılabilir.
Gerekli olduğu ölçüldü:

```
Decimal("2.675") -> float()      -> f"{v:,.2f}"  =  2,67
Decimal("2.675") -> float(fiat()) -> f"{v:,.2f}"  =  2,68
```

Yani yalnız `float(total)` demek, Decimal'e geçerek kapattığımız hatayı bir
adım sonra geri getirirdi. Değere de bağlı: `0,675` ve `3,015` düz float
yolunda doğru çıkıyor, `2,675` çıkmıyor — bu yüzden davranışa güvenilemez.

`progress_callback` üretimde hiç kullanılmıyor (tek üretim çağrısı
`fetch_active_non_try_total(on_non_try)`), ama sözleşme yine de kilitlendi:
ara ve nihai toplam **aynı** `_monetary_output()` yardımcısından geçiyor.

## 6. Sonlu olmayan fiyat — teorik değil

`price_providers` ve `_fetch_live_try_prices` fiyatı
`if value is not None and float(value) > 0` ile eliyor. **`float("inf") > 0`
DOĞRU'dur**, yani bozuk bir sağlayıcıdan gelen sonsuz fiyat bu filtreyi geçip
cache'e yazılabilir. `decimal_from()` sonlu olmayan değerde `ValueError`
fırlattığı için, korumasız bir döngü arka plan thread'ini düşürür ve callback
hiç çağrılmaz — arayüz sonsuza kadar bekler. Mutation ile doğrulandı: koruma
kaldırıldığında test 10 saniyelik zaman aşımına düşüyor.

Bozuk varlık, fiyatlanamayan varlıkla aynı şekilde atlanıyor ve geri kalan
toplam doğru geliyor.

## 7. Kapsam dışı bırakılanlar

- `get_active_non_try_assets` içindeki **kullanılmayan `purchase_price`
  çözmesi**: tek üretim çağıranı bu yol ve `purchase_price`'ı hiç okumuyor —
  her yenilemede varlık başına bir AES-GCM çözme yapılıp sonuç atılıyor. Ayrı
  temizlik adayı, bu PR'a karıştırılmadı.
- Miktarın saklama gösterimi, `price_service`'in Decimal'e taşınması, SQLite
  `REAL` şema değişikliği, `format_try` refactor'ü, `math.fsum`, portföy cache
  refactor'ü.

## 8. Karar: **C — Decimal çarpım + Decimal akümülatör**

```
float quantity/price girdi
   → decimal_from(...) × decimal_from(...)
   → Decimal akümülatör          (pozisyon başına erken fiat() YOK)
   → _monetary_output()          (float(fiat(total)))
   → mevcut float callback sözleşmesi
```

A (float kal) reddedildi: politika içinde üretilebilen, ekrana yansıyan bir
kuruş farkı var. B (yalnız akümülatör) reddedildi: fark birikimde değil
çarpımda; akümülatörü tek başına Decimal yapmak 0,67/0,68 vakasını düzeltmez.
D (upstream Decimal) reddedildi: §2'de ölçüldü, kazancı sıfır.
