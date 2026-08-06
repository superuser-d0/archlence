"""Varlık SATIŞINDA cüzdana giren tutar kuruşa yuvarlanmış olmalı.

Alım tarafının (`asset_purchase_service.create_purchase`) simetriği. Satış
yolu `AssetMixin._execute_sell` içinde bir daemon thread'de koşuyordu ve hiç
test kapsamı yoktu; `total_proceeds = sell_price_per_unit * quantity` ham
çarpımı hem bakiyeye gelir olarak yazılıyor hem de işlem tutarı olarak
saklanıyordu.

Thread ve Clock mock'lanarak `_do_sell` senkron çalıştırılıyor — asıl
ilgilendiğimiz şey aritmetik, zamanlama değil.
"""

import unittest
from decimal import Decimal
from unittest import mock


class AssetSaleCashAmountTest(unittest.TestCase):
    def _sell(self, price, quantity, purchase_price):
        """Satışı senkron koşturur, `insert_asset_transaction`a giden tutarı döner."""
        from mixins.asset_mixin import AssetMixin

        screen = AssetMixin.__new__(AssetMixin)
        for name in (
            "load_active_assets",
            "load_asset_history",
            "load_recent_transactions",
            "safe_refresh_charts",
        ):
            setattr(screen, name, mock.Mock())

        asset = {
            "id": 1,
            "asset_name": "Test",
            "asset_code": "TST",
            "quantity": quantity,
            "purchase_price": purchase_price,
        }

        captured = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            return 1

        # Thread'i senkron çalıştır: hedefi doğrudan çağırıp sahte bir nesne dön.
        def _immediate(target=None, daemon=None):
            target()
            return mock.Mock(start=mock.Mock())

        with mock.patch("database.db.insert_asset_transaction", _capture), \
                mock.patch("database.db.delete_asset", mock.Mock()), \
                mock.patch("mixins.asset_mixin.Clock") as clock, \
                mock.patch("threading.Thread", _immediate):
            clock.schedule_once = mock.Mock()
            screen._execute_sell(asset, price)

        return captured

    def test_proceeds_are_quantised_to_kurus(self):
        # 2.456,78 x 0,12345678 = 303.3061479684 ham float olarak — on
        # ondalıklı bir LİRA tutarı deftere yazılıyordu.
        captured = self._sell(
            price=2456.78, quantity=0.12345678, purchase_price=2000.0
        )
        self.assertEqual(
            Decimal(str(captured["amount"])), Decimal("303.31"),
            "Cüzdana giren tutar kuruşa yuvarlanmış olmalı",
        )
        self.assertEqual(captured["tx_type"], "income")
        self.assertEqual(captured["category"], "Varlık Satışı")

    def test_binary_artefact_never_reaches_the_ledger(self):
        # 142,30 x 17 float'ta 2419.1000000000004 üretir.
        captured = self._sell(
            price=142.30, quantity=17.0, purchase_price=100.0
        )
        self.assertEqual(Decimal(str(captured["amount"])), Decimal("2419.10"))

    def test_pnl_in_the_description_matches_the_cash_actually_credited(self):
        """Açıklamadaki K/Z, yuvarlanmış iki nakit tutarın farkı olmalı.

        Kullanıcıya gösterilen kâr, cüzdanın gerçekten gördüğü değişimle
        tutmazsa rapor kendi içinde çelişir.
        """
        captured = self._sell(
            price=2456.78, quantity=0.12345678, purchase_price=2000.0
        )
        proceeds = Decimal("303.31")          # 2456,78 x 0,12345678
        cost_basis = Decimal("246.91")        # 2000,00 x 0,12345678
        expected_pnl = proceeds - cost_basis  # 56,40

        self.assertEqual(
            Decimal(str(captured["amount"])), proceeds
        )
        self.assertIn(f"{expected_pnl:,.2f}".replace(",", "X")
                      .replace(".", ",").replace("X", "."),
                      captured["description"])


if __name__ == "__main__":
    unittest.main()
