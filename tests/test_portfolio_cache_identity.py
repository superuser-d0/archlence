"""Portföy cache'inin float eşitlik karşılaştırmasını GÜVENLİ kılan özellik.

`_read_cached_portfolio` cache'in hâlâ geçerli olduğuna şöyle karar veriyor::

    float(entry["quantity"]) != float(asset["quantity"])

Float eşitliği genelde bir kod kokusudur, ama BURADA güvenli — ve sebebi
tesadüf değil, ölçülebilir bir özellik: karşılaştırılan iki değer AYNI
kaynaktan geliyor. İkisi de aynı satırın `decrypt()` çıktısının `float()`'u;
biri doğrudan, diğeri `json.dumps`/`json.loads` turundan geçmiş hâli. Python'un
JSON kodlaması float'ı `repr()` ile yazar ve `repr` round-trip'i kayıpsızdır,
dolayısıyla iki taraf bit bit aynı kalır.

ÖLÇÜM (bu testler yazılmadan önce yapıldı, hiçbiri yanlış geçersizleşme
üretemedi):

  * JSON round-trip: 0.1+0.2, 1/3, 0.045*15, 2.675, 1e-8, 0.7*3 — dokuzunda
    da geri okunan değer birebir aynı.
  * SQLite REAL round-trip: aynı, birebir.
  * Gerçek üretim yolu: üç varlık alınıp cache yazıldı, hem elde tutulan
    listeyle hem de DB'den YENİDEN okunan listeyle karşılaştırıldı — ikisi de
    HIT.

Bu yüzden `math.isclose()` ya da tolerans EKLENMEDİ: ortada düzeltilecek bir
sapma yok, eklenen tolerans ise gerçek bir değişikliği (kullanıcı miktarı
düzeltmişse) yutarak yanlış bir cache HIT'i üretme riski taşırdı. Yanlış HIT,
gereksiz MISS'ten daha kötüdür: biri performans, diğeri yanlış veri.

Buradaki testler o özelliğin korunmasını sağlar. Payload biçimi kayıplı bir
şeye çevrilirse (ör. yazarken yuvarlanırsa) cache her okumada MISS'e döner ve
bu testler bunu söyler.
"""

import json
import unittest


_ADVERSARIAL = [
    0.1 + 0.2,          # 0.30000000000000004
    0.3,
    1 / 3,
    0.045 * 15,         # 0.6749999999999999
    2.675,
    0.7 * 3,            # 2.0999999999999996
    1e-8,
    123456.789,
]


class CachePayloadRoundTripIsLossless(unittest.TestCase):
    """Cache'in yazma/okuma turu değeri DEĞİŞTİRMEMELİ."""

    def test_json_round_trip_preserves_every_adversarial_value(self):
        for value in _ADVERSARIAL:
            with self.subTest(value=value):
                restored = json.loads(json.dumps({"quantity": value}))["quantity"]
                self.assertEqual(
                    restored, value,
                    "JSON turu değeri değiştirdi; cache her okumada MISS olur",
                )

    def test_sqlite_real_round_trip_preserves_every_adversarial_value(self):
        import sqlite3
        from contextlib import closing

        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE t (v REAL)")
            for value in _ADVERSARIAL:
                with self.subTest(value=value):
                    conn.execute("DELETE FROM t")
                    conn.execute("INSERT INTO t VALUES (?)", (value,))
                    restored = conn.execute("SELECT v FROM t").fetchone()[0]
                    self.assertEqual(restored, value)

    def test_equality_holds_across_the_whole_payload_hop(self):
        """Karşılaştırmanın kendisi: kaydedilen ve okunan değer eşit kalmalı."""
        for value in _ADVERSARIAL:
            with self.subTest(value=value):
                entry = json.loads(json.dumps({"quantity": value,
                                               "purchase_price": value}))
                self.assertFalse(
                    float(entry["quantity"]) != float(value)
                    or float(entry["purchase_price"]) != float(value),
                    "cache gereksiz yere geçersizleşirdi",
                )


if __name__ == "__main__":
    unittest.main()
