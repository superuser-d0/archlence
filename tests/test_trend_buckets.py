"""CurvedTrendChart zaman kovaları — açılış bakiyesi serisi.

BAĞLAM: Varlıklarım sekmesindeki SAĞ (zaman/trend) grafiği yalnızca
`transactions` tablosundan besleniyordu. Hesap açılış bakiyesi oraya hiç
yazılmadığı için (bkz. TransactionService.get_opening_events_by_period),
yeni açılmış tek hesaplı bir kullanıcı — bakiyesi dolu olsa bile — sağ
grafikte kalıcı olarak "Veri Yok" görüyordu.

Bu paket açılış olaylarının doğru zaman kovasına düştüğünü ve `income`
alanına SIZMADIĞINI (gerçek gelir sayılmadığını) kilitler.
"""
import datetime
import os
import unittest

os.environ.setdefault("KIVY_NO_ARGS", "1")


def _buckets(raw_data, period, opening_events=None, now=None):
    """`_build_time_buckets`'ı Kivy widget ağacı kurmadan çağırır.

    Metot yalnızca `self._parse_tx_datetime` (bir staticmethod) kullanıyor,
    bu yüzden `self` yerine sınıfın kendisi geçilebiliyor — bir MDBoxLayout
    örneklemek (ve pencere sağlayıcısı gerektirmek) gereksiz olurdu.
    """
    from ui.charts import DashboardChartManager
    return DashboardChartManager._build_time_buckets(
        DashboardChartManager, raw_data, period, opening_events, now
    )


class TrendBucketOpeningSeriesTest(unittest.TestCase):
    def setUp(self):
        # Gerçek sistem saati sabah 06:00'dan önceyse bu regresyon testi
        # eskiden skip ediliyordu. Sabit akşam saatiyle 24/7 deterministik.
        self.now = datetime.datetime(2026, 7, 30, 20, 0, 0)
        self.today_ts = self.now.strftime("%Y-%m-%d %H:%M:%S")

    def test_opening_only_still_produces_rows(self):
        """Asıl hata: hiç işlem yokken grafik tamamen boş dönüyordu."""
        rows = _buckets(
            [], "Bugün",
            [{"amount": 22500.0, "transaction_date": self.today_ts}],
            now=self.now,
        )
        self.assertTrue(rows, "açılış bakiyesi tek başına grafiği doldurmalı")
        self.assertEqual(sum(r["opening"] for r in rows), 22500.0)

    def test_opening_does_not_leak_into_income(self):
        """Açılış bakiyesi gelir serisine SAYILMAMALI (pasta ile aynı ilke)."""
        rows = _buckets(
            [], "Bugün",
            [{"amount": 22500.0, "transaction_date": self.today_ts}],
            now=self.now,
        )
        self.assertEqual(sum(r["income"] for r in rows), 0.0)
        self.assertEqual(sum(r["expense"] for r in rows), 0.0)

    def test_no_data_at_all_returns_empty(self):
        """Ne işlem ne açılış varsa boş liste (eksen iskeleti + 'Veri Yok')."""
        self.assertEqual(_buckets([], "Bugün", [], now=self.now), [])
        self.assertEqual(_buckets([], "Bugün", None, now=self.now), [])

    def test_transactions_still_bucket_normally(self):
        """Regresyon: açılış serisi eklenirken gelir/gider bozulmamalı."""
        rows = _buckets(
            [
                {"type": "income", "amount": 100.0,
                 "transaction_date": self.today_ts},
                {"type": "expense", "amount": 40.0,
                 "transaction_date": self.today_ts},
            ],
            "Bugün",
            now=self.now,
        )
        self.assertEqual(sum(r["income"] for r in rows), 100.0)
        self.assertEqual(sum(r["expense"] for r in rows), 40.0)
        self.assertEqual(sum(r["opening"] for r in rows), 0.0)

    def test_early_opening_hour_is_not_clipped_off_today_axis(self):
        """'Bugün' ekseninin alt sınırı işlemlerden türetiliyordu; sabah
        açılan bir hesap (şu an akşamsa) aralığın dışında kalıp sessizce
        kayboluyordu."""
        early = self.now.replace(hour=1, minute=0, second=0)
        rows = _buckets(
            [], "Bugün",
            [{"amount": 5000.0,
              "transaction_date": early.strftime("%Y-%m-%d %H:%M:%S")}],
            now=self.now,
        )
        self.assertEqual(sum(r["opening"] for r in rows), 5000.0)
        self.assertEqual(rows[0]["label"], "01:00")

    def test_lifetime_axis_starts_at_opening_year(self):
        """'Hayat Boyu' ekseninin başlangıç yılı da yalnız işlemlerden
        türetiliyordu; sadece açılış olayı varsa hiç satır üretilmezdi."""
        old = self.now.replace(year=self.now.year - 2)
        rows = _buckets(
            [], "Hayat Boyu",
            [{"amount": 900.0,
              "transaction_date": old.strftime("%Y-%m-%d %H:%M:%S")}],
            now=self.now,
        )
        self.assertTrue(rows)
        self.assertEqual(rows[0]["label"], str(old.year))
        self.assertEqual(sum(r["opening"] for r in rows), 900.0)

    def test_rows_always_carry_the_opening_key(self):
        """Çizim tarafı d.get('opening') okuyor; anahtarın her satırda
        bulunması sözleşmenin parçası."""
        rows = _buckets(
            [{"type": "income", "amount": 10.0,
              "transaction_date": self.today_ts}],
            "1 Hafta",
            now=self.now,
        )
        self.assertTrue(all("opening" in r for r in rows))


if __name__ == "__main__":
    unittest.main()
