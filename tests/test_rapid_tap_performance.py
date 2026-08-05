"""Takvim ve bütçe ekranlarında hızlı/tekrarlı dokunma dayanıklılığı.

BAĞLAM (kullanıcı raporu, Windows): "Takvim ve aylık bütçe ayarlama
kısmında hızlı hızlı tıklayınca kasıyor ve uygulama çöküyor."

Kök neden iki yerde de aynı sınıftaydı: her dokunuş, dokunuş sayısıyla doğrusal
büyüyen PAHALI işi UI thread'inde senkron çalıştırıyordu.

  * Takvim  — `_select_calendar_day` her dokunuşta 42 hücrelik ızgarayı baştan
    kuruyor (`_render_calendar_month`) VE sınırsız `threading.Thread` açıyordu.
  * Bütçe   — `change_budget_month` her ay butonunda `load_budget_list()` +
    `generate_next_month_projection()` çağırıyordu.

Bu testler DAVRANIŞI ölçer (çağrı sayar), süreyi değil: zamana bakan bir test
CI'da kararsız olurdu. Düzeltme geri alınırsa sayaçlar patlar.
"""
import datetime
import unittest
from unittest import mock


class _FakeClock:
    """`Clock.schedule_once` yerine geçen, elle ilerletilen sahte saat.

    Gerçek Clock'a bağlanmak testi kare hızına bağımlı ve kararsız yapardı.
    Burada önemli olan tek şey debounce SÖZLEŞMESİ: bekleyen iş iptal
    edilebiliyor mu ve art arda çağrılarda kaç kez GERÇEKTEN çalışıyor.
    """

    def __init__(self):
        self.pending = []

    def schedule_once(self, callback, timeout=0):
        event = mock.Mock()
        entry = [callback, True]

        def cancel():
            entry[1] = False

        event.cancel.side_effect = cancel
        self.pending.append(entry)
        return event

    def advance(self):
        """Bekleyen ve iptal EDİLMEMİŞ işleri çalıştırır."""
        due, self.pending = self.pending, []
        for callback, alive in due:
            if alive:
                callback(0)


class CalendarRapidTapTest(unittest.TestCase):
    """Hızlı gün seçiminde ızgara yeniden kurulmamalı, thread yığılmamalı."""

    def _make_app(self):
        from mixins.calendar_mixin import CalendarMixin

        app = CalendarMixin.__new__(CalendarMixin)
        app._calendar_selected_date = None
        app._calendar_generation = 0
        app._calendar_load_event = None
        app._calendar_day_cells = {}
        app._calendar_selected_label = mock.Mock()
        app._calendar_tx_container = mock.Mock()
        app._render_calendar_month = mock.Mock()
        app._style_calendar_day_cell = mock.Mock()
        return app

    def test_rapid_day_taps_never_rebuild_the_whole_grid(self):
        app = self._make_app()
        clock = _FakeClock()
        base = datetime.date(2026, 7, 1)

        with mock.patch("mixins.calendar_mixin.Clock", clock), \
                mock.patch("mixins.calendar_mixin.threading.Thread") as thread:
            for offset in range(12):
                app._select_calendar_day(base + datetime.timedelta(days=offset))

            self.assertEqual(
                app._render_calendar_month.call_count, 0,
                "Gün seçimi ızgarayı yeniden kurmamalı; yalnız etkilenen "
                "hücreler yeniden boyanmalı.",
            )
            # 12 hızlı dokunuş, debounce sayesinde TEK bir DB thread'i açmalı.
            self.assertEqual(thread.call_count, 0, "Debounce öncesi thread açılmamalı.")
            clock.advance()
            self.assertEqual(
                thread.call_count, 1,
                "12 hızlı dokunuş yalnızca SON istek için tek thread açmalı; "
                "eski davranış 12 eşzamanlı SQLite bağlantısı üretiyordu.",
            )

    def test_only_the_two_affected_cells_are_restyled(self):
        app = self._make_app()
        clock = _FakeClock()
        d1, d2 = datetime.date(2026, 7, 10), datetime.date(2026, 7, 11)
        app._calendar_day_cells = {d1: mock.Mock(), d2: mock.Mock()}

        with mock.patch("mixins.calendar_mixin.Clock", clock), \
                mock.patch("mixins.calendar_mixin.threading.Thread"):
            app._select_calendar_day(d1)
            app._style_calendar_day_cell.reset_mock()
            app._select_calendar_day(d2)

        # Eski seçim söndürülür + yeni seçim yakılır = tam 2 boyama.
        self.assertEqual(app._style_calendar_day_cell.call_count, 2)


class BudgetRapidMonthTapTest(unittest.TestCase):
    """Ay butonlarına hızlı basınca liste tek kez yeniden kurulmalı."""

    def test_rapid_month_switches_coalesce_into_one_rebuild(self):
        from mixins.budget_mixin import BudgetMixin

        app = BudgetMixin.__new__(BudgetMixin)
        app.active_budget_year = 2026
        app._budget_month_refresh_event = None
        app.load_budget_list = mock.Mock()
        app.generate_next_month_projection = mock.Mock()

        clock = _FakeClock()
        with mock.patch("mixins.budget_mixin.Clock", clock):
            for month in range(1, 13):
                app.change_budget_month(month)

            # Durum ataması ANINDA olmalı — çağıran hemen okuyabilsin.
            self.assertEqual(app.active_budget_month, 12)
            self.assertEqual(app.load_budget_list.call_count, 0)

            clock.advance()

        self.assertEqual(
            app.load_budget_list.call_count, 1,
            "12 hızlı ay geçişi tek yeniden inşaya indirgenmeli; eski davranış "
            "12 tam liste yeniden kurulumu yapıyordu.",
        )
        self.assertEqual(app.generate_next_month_projection.call_count, 1)


class CategoryToggleRapidTapTest(unittest.TestCase):
    """Kategori anahtarlarını hızlı çevirince grafik bir kez tazelenmeli.

    Kullanıcı raporu: "kategori ayarlarında ayar kapatıp açarken kasmalar".
    Her dokunuş tam bir pasta+trend yeniden hesabı/çizimi tetikliyordu.
    """

    def test_rapid_toggles_coalesce_chart_refresh(self):
        import main as archlence_main

        app = archlence_main.ArchlenceApp.__new__(archlence_main.ArchlenceApp)
        app._category_chart_refresh_event = None
        app.safe_refresh_charts = mock.Mock()

        clock = _FakeClock()
        conn = mock.MagicMock()
        # `update_category_importance` bağlantıyı `managed_connection()` ile
        # alıyor (düz `get_connection()` + `conn.close()` değil), bu yüzden
        # patch'lenen de context manager olmalı.
        managed = mock.MagicMock()
        managed.return_value.__enter__.return_value = conn
        with mock.patch.object(archlence_main, "Clock", clock), \
                mock.patch.object(archlence_main, "managed_connection", managed):
            for index in range(10):
                app.update_category_importance(f"Kategori {index}", index % 2 == 0)

            # Tercih ANINDA yazılmalı — kaybolmamalı.
            self.assertEqual(conn.cursor.return_value.execute.call_count, 10)
            self.assertEqual(app.safe_refresh_charts.call_count, 0)
            clock.advance()

        self.assertEqual(
            app.safe_refresh_charts.call_count, 1,
            "10 hızlı anahtar dokunuşu tek grafik tazelemesine inmeli.",
        )


class TransactionRefreshFrameSpreadTest(unittest.TestCase):
    """İşlem eklendikten sonraki ağır tazelemeler tek kareyi bloklamamalı.

    Kullanıcı raporu: "her yeni işlem eklendiğinde aşırı kasıyor".
    """

    def _app(self):
        from mixins.transaction_mixin import TransactionMixin
        return TransactionMixin.__new__(TransactionMixin)

    def test_each_refresh_runs_in_its_own_frame(self):
        import mixins.transaction_mixin as tx_module

        app = self._app()
        calls = []
        jobs = [lambda: calls.append(n) for n in range(4)]

        clock = _FakeClock()
        with mock.patch.object(tx_module, "Clock", clock):
            app._run_refresh_jobs_across_frames(jobs)
            self.assertEqual(len(calls), 1, "İlk iş hemen, kalanı sonraki karelerde.")
            for expected in (2, 3, 4):
                clock.advance()
                self.assertEqual(len(calls), expected)

    def test_a_failing_refresh_does_not_cancel_the_rest(self):
        import mixins.transaction_mixin as tx_module

        app = self._app()
        done = []

        def boom():
            raise RuntimeError("sunum katmani patladi")

        jobs = [boom, lambda: done.append("sonraki")]
        clock = _FakeClock()
        with mock.patch.object(tx_module, "Clock", clock), \
                mock.patch("utils.logging_config.get_logger"):
            app._run_refresh_jobs_across_frames(jobs)
            clock.advance()

        self.assertEqual(
            done, ["sonraki"],
            "Kayıt zaten commit edildi; bir sunum hatası kalan tazelemeleri "
            "iptal etmemeli.",
        )


if __name__ == "__main__":
    unittest.main()
