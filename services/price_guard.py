"""Harici fiyatlar için tek normalizasyon sınırı.

NEDEN AYRI BİR MODÜL: fiyat üç ayrı yerden içeri giriyordu
(`price_providers`, `asset_service._fetch_live_try_prices`,
`price_service._store_cache`) ve üçü de aynı kalıbı kullanıyordu:

    if value is not None and float(value) > 0:

Bu kalıp SONSUZU KABUL EDER — `float("inf") > 0` True'dur. `json.loads`
varsayılan olarak `Infinity` ve `NaN` sabitlerini ayrıştırdığı için bozuk ya
da düşmanca bir sağlayıcı yanıtı bunu doğrudan üretebiliyordu. Sonsuz bir
fiyat cache'e yazıldığında kalıcı hâle geliyor ve `inf * miktar` üzerinden
portföy toplamının TAMAMINI `inf` yapıyordu.

Kontrol her çağrı yerine ayrı ayrı yazılmak yerine buraya toplandı: üç
kopyanın zamanla birbirinden ayrılması, bu kusurun ilk hâlinin nasıl
oluştuğuyla aynı mekanizma.
"""

import math

__all__ = ["finite_positive_price"]


def finite_positive_price(value) -> float | None:
    """Kabul edilebilir bir fiyatsa `float`, değilse `None` döndürür.

    Reddedilenler ve nedenleri:
      * `NaN` / `Inf` / `-Inf` — `> 0` karşılaştırmasının yakalayamadığı sınıf.
        Taşma sonucu oluşan `inf` (`1e400`) de buraya düşer.
      * `bool` — Python'da `int`'in alt sınıfı, yani `True` sayısal bir
        kontrolü sessizce geçer. Bir fiyat asla bool değildir.
      * sıfır ve negatif — bir varlığın piyasa fiyatı olamaz.
      * `None`, boş metin, sayıya çevrilemeyen her şey.

    ASLA İSTİSNA FIRLATMAZ. Çağıranların hepsi bir toplu sonucu döngüyle
    işliyor; tek bozuk sembol yüzünden tüm batch'in düşmesi, bu fonksiyonun
    engellemek istediği "tek kötü değer her şeyi bozar" davranışının aynısı
    olurdu. Bozuk sembol atlanır, sağlamlar geçer.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0:
        return None
    return price
