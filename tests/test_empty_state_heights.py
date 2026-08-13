"""Boş kartlar yer kaplamamalı; boş durum metni yine de görünmeli.

NEDEN VAR: "Aktif Borçlarım", "Yaklaşan Ödemeler", "Varlık Geçmişi", "Aktif
Varlıklarım" ve "Son İşlemler" alanları sabit yükseklikliydi (220/190/320/280/
400dp). İçerik yokken bu kartlar ekranın yarısını boş boş kaplıyordu. Artık
yükseklik içerikten geliyor (bkz. ui/dashboard.kv).

Bu değişikliğin ince tarafı şu: içeriğe uyan bir kapsayıcıda `size_hint_y`
varsayılanı (1) olan bir çocuk `minimum_height`'a SIFIR katkı verir. Yani boş
durum etiketleri açık yükseklikle eklenmezse kart tamamen kapanır ve
"Henüz aktif bir borcunuz bulunmuyor." gibi metinler görünmez olur. Testler o
sözleşmeyi tutuyor: etiketler ölçülebilir yükseklikle kuruluyor mu, ve "Son
İşlemler" listesinin boş durum etiketi doğru zamanlarda açılıp kapanıyor mu.

Kivy widget ağacı kurulmaz: MDLabel taklit edilir, `root.ids` sözlük stub'ıdır
(tests/test_pending_panel.py'deki desen).
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Ids(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _Container:
    def __init__(self):
        self.children = []

    def clear_widgets(self):
        self.children = []

    def add_widget(self, widget):
        self.children.append(widget)


class EmptyStateLabelsHaveHeight(unittest.TestCase):
    """Boş durum etiketi kapsayıcının minimum_height'ına katkı vermeli."""

    def test_debt_card_empty_label_is_measurable(self):
        from mixins.debt_mixin import DebtMixin

        app = SimpleNamespace(
            root=SimpleNamespace(ids=_Ids(active_debts_container=_Container()))
        )
        with mock.patch("mixins.debt_mixin.MDLabel") as label:
            DebtMixin.render_active_debts(app, [])

        kwargs = label.call_args.kwargs
        self.assertIsNone(kwargs["size_hint_y"])
        self.assertGreater(kwargs["height"], 0)

    def test_upcoming_payments_empty_label_is_measurable(self):
        from mixins.recurring_mixin import RecurringMixin

        app = SimpleNamespace(
            root=SimpleNamespace(ids=_Ids(upcoming_payments_container=_Container()))
        )
        with mock.patch("mixins.recurring_mixin.MDLabel") as label:
            RecurringMixin.render_upcoming_payments(app, [])

        kwargs = label.call_args.kwargs
        self.assertIsNone(kwargs["size_hint_y"])
        self.assertGreater(kwargs["height"], 0)


class RecentTransactionsEmptyLabel(unittest.TestCase):
    """Liste yüksekliği içerikten geldiği için boş dönemde metin gösterilmeli."""

    def _make_app(self):
        rv = SimpleNamespace(data=None)
        label = SimpleNamespace(height=0, opacity=0)
        app = SimpleNamespace(
            root=SimpleNamespace(ids=_Ids(
                recent_transactions_list=rv,
                recent_tx_empty_label=label,
            )),
        )
        app._prefetch_recent_brand_icons = lambda *a, **k: None
        return app, rv, label

    def test_empty_period_shows_the_label(self):
        import main as app_module

        app, rv, label = self._make_app()
        app_module.ArchlenceApp._render_recent_transactions(app, [])

        self.assertEqual(rv.data, [])
        self.assertEqual(label.opacity, 1)
        self.assertGreater(label.height, 0)

    def test_populated_period_hides_the_label(self):
        import main as app_module

        app, rv, label = self._make_app()
        label.height, label.opacity = 40, 1
        rows = [("expense", "Market", 25.0, "Ekmek", "2026-08-13", False)]
        app_module.ArchlenceApp._render_recent_transactions(app, rows)

        self.assertEqual(len(rv.data), 1)
        self.assertEqual(label.opacity, 0)
        self.assertEqual(label.height, 0)


if __name__ == "__main__":
    unittest.main()
