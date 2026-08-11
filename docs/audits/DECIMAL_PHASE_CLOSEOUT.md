# Decimal fazı — kapanış turu ve fazın sonucu

**Tarih:** 2026-08-11 · **Taban:** `main` = `60c3620`
**Üretim kodu değişmedi.** Bu belge son turun ölçümlerini ve fazın kapanışını kaydeder.

---

## 1. Sayım: baseline ile canlı sayı ayrı şeylerdir

| | Sayı |
|---|---|
| İlk AST baseline (faz başlangıcı) | **101** |
| Güncel canlı `float()` (`60c3620`) | **104** |

**Canlı sayının artmış olması başarısızlık değildir.** Domain aritmetiğindeki
`float()` çağrıları kaldırılırken, mevcut public/output sözleşmesini korumak
için kontrollü `float(fiat(...))` dönüşümleri eklendi: `calculate_pnl` dört,
portföy toplamı bir tane. Yani üç çağrı "kayboldu", beş tanesi sınırda geri
geldi.

Ham `float()` sayısı bir kalite metriği DEĞİLDİR. Bu fazın metriği şuydu:

- aritmetik doğruluğu,
- hassasiyet sınırının nerede olduğu,
- tüketici semantiği,
- iş kararlarının kararlılığı.

### Kategori 1 sayım düzeltmesi

Belge, portföy geçişinden sonra kategori 1 için **18** yazıyordu. Kapanış
turunda üyeler AST ile tek tek sayıldı: gerçek sayı **19**'du. Fark, önceki
turda toplamı elle taşırken yaptığım bir aritmetik hatadan geliyor; düzeltildi
ve burada kayda geçiriliyor.

Kapanış turundan sonra **ölçülmemiş `MIGRATE` adayı: 0.**

---

## 2. Son turun karar tablosu

19 adayın tamamı tüketici semantiğine göre gruplanıp ölçüldü.

| Path | Storage precision | Consumer | Arithmetic | Decision | Final classification |
|---|---|---|---|---|---|
| `asset_service :: get_active_non_try_assets :: quantity` | `str(float(qty))` | portföy toplamı (Decimal'e promote) | yok | değişmiyor | KEEP — persistence boundary |
| `asset_service :: get_active_non_try_assets :: purchase_price` | — | **hiçbir yerde** | — | — | **DEAD / cleanup candidate** |
| `asset_service :: invalidate_asset_data_cache` (4) | girdiler `round(x,2)` | iki UI etiketi | + / − | 0 / 400.000 | KEEP — bounded/display-only |
| `db.py :: get_active_debts` (2) | `str(fiat(x))` | görüntü + insights toplaması | toplama | 0 / 200.000 | KEEP — cent-quantized |
| `db.py :: get_all_assets` (2) | `str(float(x))` | `calculate_pnl` (Decimal) | promote | değişmiyor | KEEP — persistence boundary |
| `db.py :: get_asset_by_id` (2) | `str(float(x))` | `:g` / `:,.4g` etiketi | yok | değişmiyor | KEEP — display |
| `db.py :: get_asset_transaction_history` (1) | `str(fiat(x))` | geçmiş listesi | yok | değişmiyor | KEEP — display |
| `db.py :: get_active_recurring_payments` (1) | `str(fiat(x))` | `budget_service` (`decimal_from`) | promote | değişmiyor | KEEP — persistence boundary |
| `history_service :: get_balance_at` (1) | snapshot `round(x,2)` | geçmiş bakiye | **toplama** | değişmiyor | KEEP — cent-quantized |
| `calendar_service :: get_day_transactions` (1) | `str(fiat(x))` | ay ızgarası | yok | değişmiyor | KEEP — display |
| `recurring_service :: _plain_amount` (1) | `str(fiat(x))` | iade adayı | yok | değişmiyor | KEEP — persistence boundary |
| `recurring_service :: refund_current_period_charge` (1) | `str(fiat(x))` | yazma + bakiye mutasyonu | yok — aynı tutar | değişmiyor | KEEP — persistence boundary |
| `insights_service :: _safe_decrypt_float` (1) | `str(fiat(x))` | `fmean`, `pstdev`, skor, anomali | **evet** | 0 flip | KEEP — numerical/statistical |

`INVESTIGATE` kalemi kalmadı.

## 3. Ölçüm sonuçları

### insights — eşik kararları

İki gerçek karar noktası ölçüldü:

```
sağlık skoru ETİKETİ değişen (score_label 80/60/40/20) : 0 / 200.000
anomali eşiği kararı değişen (z >= 2.0)                : 0 / 20.000 seri
```

`_safe_decrypt_float`'ın dönüş tipini `Decimal` yapmak varsayılan çözüm olarak
kabul edilmedi; `statistics.fmean` / `pstdev` zaten float bekliyor ve fan-out
yüksek. Ölçüm hiçbir kararın değişmediğini gösterdiği için bilinçli
statistical float olarak kapatıldı.

### history_service — toplama

1, 10 ve 100 hedefte, kuruşlu tutarlarla ve `0,1 / 0,2 / 0,3` dizisiyle:
**gösterilen kuruş farkı yok.**

### `db.py` getter'larının ortak gerekçesi

Hepsi `encrypt(str(fiat(x)))` ile yazılmış değerleri okuyor, yani saklanan
metin kuruşun tam katı. Kuruşun tam katı iki sayının toplamı/farkı da kuruşun
tam katıdır — yarım kuruş sınırına hiç ulaşılmaz, dolayısıyla float hatası
yuvarlamayı çeviremez. Getter'ın `float` döndürmesi tek başına gerekçe
sayılmadı; aritmetiğe girdiği iki yer ayrıca ölçüldü.

### `invalidate_asset_data_cache` — risk notu

Ardışık cache mutasyonlarında (12 kart silme ölçüldü) ham `card_debt` değerinde
yaklaşık **6,8e-13** artık kalabiliyor. Bugün bir correctness sorunu değil:
hiçbir predicate bu ham snapshot değerini kullanmıyor, iki UI etiketi dışında
tüketicisi yok ve bir sonraki warm-up değeri veritabanından yeniden hesaplıyor.

**İleride bu cache alanı `> 0` ya da `== 0` gibi bir iş kuralında
kullanılacaksa, önce monetary normalization uygulanmalıdır.**

---

## 4. Decimal fazının sonucu

### Migrate edilenler

| Dilim | Kanıt |
|---|---|
| `calculate_pnl` | 0,045 × 15 = 0,675 → 0,67 yerine 0,68 (PR #84) |
| Portföy piyasa değeri — çarpım ve birikim | Aynı sınıf, ekrana yansıyan bir kuruş (PR #88) |

### Ölçülüp bilinçli olarak float bırakılanlar

- Projeksiyon sayısal çekirdeği (RK4) — 22 vakanın 21'inde kuruş aynı, Decimal
  çekirdek 4,1× maliyetli
- Cache/gösterim sınırındaki bounded aritmetik
- İstatistiksel/insights aritmetiği
- Persistence ve display sınırları
- Kalan cent-quantized yollar

### Faz sırasında ortaya çıkan yan correctness bulguları

Bunlar Decimal hatası DEĞİLDİR; denetim sırasında ortaya çıkan ayrı correctness
bulgularıdır:

- Eşzamanlı varlık alımında kredi kartı limit invariant'ı (PR #83)
- Birikim hedefi durumunun hassasiyet tutarsızlığı (PR #86)
- Sonlu olmayan portföy fiyatının worker'ı düşürmesi (PR #88)

---

## 5. Kapanış

**Baseline sınıflandırmasından geriye denetlenmemiş Decimal migration adayı
kalmamıştır.**

Bu noktadan sonra yalnızca `float()` var diye yeni migration yapılmaz. Decimal
sınıflandırması ancak yeni kod ya da yeni kanıt ortaya çıktığında yeniden
açılır; repo çapında yeni bir float taraması başlatılmaz.
