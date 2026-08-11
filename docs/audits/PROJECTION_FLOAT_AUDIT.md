# `projection_service` hassasiyet denetimi — karar: **Keep float**

**Tarih:** 2026-08-11 · **Taban:** `main` = `12e28bf`
**Ölçüm aracı:** `scripts/audit/measure_projection_precision.py`
**Üretim kodu değişmedi.**

Denetlenen fonksiyonlar: `project_wealth_series`, `project_final_wealth`,
`simulate_scenario`.

---

## 1. Yöntem — üç ayrı sonuç, iki ayrı hata

`dW/dt = rW + c` (c = günlük gelir − günlük gider) üç şekilde çözüldü:

| | Ne | Ne ölçer |
|---|---|---|
| **A** | Mevcut float RK4 (üretim kodu, olduğu gibi çağrıldı) | — |
| **B** | AYNI RK4 algoritması, aritmetik `Decimal` (80 hane) | — |
| **C** | Analitik çözüm, yüksek hassasiyetle | — |

Ayrıştırma bilerek üç sayı:

```
|A − B|   float temsil / birikim hatası   (aynı algoritma, farklı aritmetik)
|B − C|   RK4 kesme hatası                 (aynı aritmetik, farklı yöntem)
|A − C|   mevcut toplam hata
```

Bu ayrım olmadan "Decimal daha doğru mu?" sorusu dürüstçe cevaplanamaz:
`|A−B|` Decimal'in kazandırabileceğini, `|B−C|` ise yöntemin zaten
kaybettiğini ölçer. `A ≈ B` iken ikisi de `C`'den uzaksa Decimal'a geçmek
anlamsızdır.

**Referansın kendisi doğrulandı.** Analitik çözüm `(W0 + c/r)·e^{rt} − c/r`
biçiminde DEĞİL, `W0·e^{rt} + c·(e^{rt}−1)/r` biçiminde hesaplandı: küçük
`r`'de `c/r` devasa olur ve çıkarma iptali sonucu bozardı. Ayrıca her vaka 60
ve 120 hane ile ayrı ayrı hesaplanıp aynı çıktığı doğrulandı
(`_reference_is_stable`); tutmayan vaka ölçüme alınmaz.

---

## 2. `r = 0` bulgusu — kesme hatası yapısal olarak sıfır

Türev sabit olduğunda (`r = 0` → `dW/dt = c`) RK4'ün dört eğimi de eşittir ve
adım tam olarak `W += c` verir. Yani bu vakada **yöntem hiçbir yaklaşım
yapmıyor**; ölçülen her sapma doğrudan temsil/birikim kaynaklıdır.

Ölçüm bunu doğruladı — `|B − C| = 0` (80 hane altında sıfır):

| Vaka | \|A−B\| | Kuruş sonucu |
|---|---|---|
| 150,75 / 100,25 · 3650 gün | **0** — `c = 50,50` ikilide tam gösterilebilir | aynı |
| 0,30 / 0,10 · 3650 gün | 2,90e-11 | aynı |
| kuruş altı (0,005 / 0,001) · 365 gün | 1,78e-12 | aynı |
| gelir = gider · 365 gün | 0 | aynı |

---

## 3. Varsayılan `r = 0.0001` bulgusu — float hatası kesme hatasını **geçiyor**

Denetime girerken "RK4 kesme hatası muhtemelen ikili float hatasından kat kat
büyüktür" diye bir beklenti vardı. **Ölçüm bunu çürüttü.**

| Vaka | \|A−B\| float | \|B−C\| RK4 | Baskın |
|---|---|---|---|
| r=0.0001 · 30 gün | 1,61e-12 | 1,29e-15 | float, ~1.200× |
| r=0.0001 · 365 gün | 8,45e-13 | 1,63e-14 | float, ~52× |
| r=0.0001 · 3650 gün | 6,47e-11 | 2,26e-13 | float, ~287× |
| r=1e-9 · 3650 gün | 5,13e-11 | 1,54e-33 | float, ~10²²× |
| r=0.0001 · 9,5M TL servet | 5,35e-8 | 5,48e-12 | float, ~9.700× |

15 vakanın 9'unda float temsil hatası baskın. Kesme hatası ancak
`r ≳ 0.0005` bölgesinde öne geçiyor.

**Bu, Decimal lehine bir bulgudur** — tek başına okunursa. Kararı belirleyen
şey bir sonraki bölüm.

---

## 4. Kullanıcıya yansıyan sonuç: kuruş değişmiyor

22 vakanın **21'inde** A ve C aynı kuruşa yuvarlanıyor. Gerçekçi oranların
hepsinde (yıllık %5 / %20 / %50), 1–36.500 gün ufkunda, 9,5M TL'ye kadar
servette kuruş **birebir** aynı. Float-baskın vakalarda bağıl hata ~1e-16,
yani çift hassasiyetin tabanı.

Tek ayrışan vaka:

| Vaka | A | C | Baskın hata |
|---|---|---|---|
| r=0.005/gün · 3650 gün | 9.273.997.604.561,34 | 9.273.997.605.439,16 | **RK4 kesme** |

Günlük %0,5 ≈ yıllık %517 bileşik getiri ve 9,27 trilyon TL servet. Bağıl hata
9,5e-11. Burada bile sorun Decimal'in çözebileceği bir şey değil — baskın olan
kesme hatası.

---

## 5. `difference` — iptal (cancellation) riski ölçüldü

`difference = scenario_final − base_final`, yani iki büyük ve birbirine yakın
sayının farkı. Senaryo farkı bilerek küçültülerek zorlandı:

| Senaryo | float `difference` | Decimal | Kuruş farkı | Kuruş aynı? |
|---|---|---|---|---|
| gelir %0,001 · 3650 gün | 20.811180078657344 | 20,811180 | 2,24e-7 | evet |
| gelir %0,01 · 3650 gün | 208.11180076678284 | 208,111801 | 2,59e-7 | evet |
| gelir %1 · 3650 gün | 20811.18007641961 | 20811,180076 | 1,73e-8 | evet |
| gelir %0 · 3650 gün | 0.0 | 0 | 0 | evet |
| gelir %0,001 · 9,5M servet | 66.07710126787424 | 66,077101 | 4,55e-6 | evet |

Senaryo yüzde aritmetiği ayrıca ölçüldü (`base_income * (1 + pct/100)`): en
büyük sapma `103.25750000000001` vs `103,2575` → 1e-12 kuruş.

---

## 6. `goes_negative` — karar değişmiyor

Karar `any(value < 0)` ile **tüm seri** üzerinde veriliyor, yani yalnız nihai
servet değil yoldaki sıfır geçişi de önemli. Sınır vakaları:

| Vaka | A kararı | C kararı | A minimum |
|---|---|---|---|
| tam sıfıra inen | False | False | 0,0000000000 |
| sıfırın bir kuruş üstü | False | False | 0,0100000000 |
| sıfırın bir kuruş altı | True | True | −0,0100000000 |
| `r` ile toparlanan | False | False | 50,0000000000 |

Tam sıfır vakasında minimum tam olarak `0.0` ve `any(v < 0)` doğru şekilde
`False`. Dördünde de A ve C aynı kararı veriyor.

---

## 7. Performans

3650 gün, 200 tekrar:

```
float RK4             0,227 s   1,0×
Decimal RK4 prec=28   0,933 s   4,1×
Decimal RK4 prec=80   1,274 s   5,6×
```

---

## 8. Karar tablosu

| Alt alan | Mevcut hata | User-visible? | Karar değişiyor mu? | Decimal iyileştirir mi? | Maliyet | Karar |
|---|---|---|---|---|---|---|
| Input normalization | ≤1e-12 kuruş | hayır | hayır | görünür şekilde hayır | ~0 | değiştirme |
| Senaryo yüzde aritmetiği | max 1e-12 kuruş | hayır | hayır | marjinal | ~0 | değiştirme |
| RK4 çekirdeği | ~1e-16 bağıl | hayır | hayır | **hayır** | **4,1×** | değiştirme |
| `difference` | max 4,55e-6 kuruş | hayır | hayır | hayır | — | değiştirme |
| `goes_negative` | 0 | hayır | hayır | — | — | değiştirme |

## 9. Karar: **C — Keep float**

Gerekçe "hata yok" DEĞİL. Hata var, ölçüldü ve bazı gerçekçi parametrelerde
kesme hatasından da büyük. Gerekçe şu: hatanın tamamı kuruşun ~10 mertebe
altında kalıyor, hiçbir gösterilen değeri, `difference`'ı veya `goes_negative`
kararını değiştirmiyor, ve float-baskın vakalarda bağıl hata zaten çift
hassasiyetin tabanında.

**Neden A (Full Decimal) değil:** Decimal çekirdek `|A−B|`'yi düşürür ama
düşürdüğü şey görünmez; karşılığı 4,1× maliyet ve `float` bekleyen bir sayısal
çekirdeğe tip sınırı.

**Neden B (Hybrid) değil:** finansal aritmetiğin (yüzde, `difference`, girdi
normalizasyonu) ölçülen sapması 1e-12 kuruş. `calculate_pnl`'de Decimal bir
kuruş kazandırıyordu çünkü orada sorun **yuvarlama sınırındaki** bir çarpımdı
(0,045 × 15 = 0,675); burada öyle bir sınır yok.

**Neden D (Algorithmic change) değil:** yalnız `r ≳ 0.005` bölgesinde gündeme
gelirdi ve orada asıl mesele hassasiyet değil — model 10 yılda 9 trilyon TL
üretiyor. Bu bir çözücü sorunu değil, girdi aralığı sorunu; ayrı ve ürün
tarafında bir karar.

## 10. Sınıflandırmaya etkisi

`projection_service`'teki 11 `float()` çağrısı
`domain / business calculation` (migrate) kategorisinden çıkarılıp
**`numerical algorithm / intentional float`** kategorisine alındı. Ayrıntı:
`DECIMAL_MIGRATION_CLASSIFICATION.md`.
