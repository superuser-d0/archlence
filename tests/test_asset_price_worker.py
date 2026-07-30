"""Canlı fiyat subprocess'i ve yfinance MultiIndex ayrıştırması.

Bu turda teşhis edilen üç kök neden burada kilitlenir:
  1. Alt süreç yanlış cwd'den çağrılınca `ModuleNotFoundError: services` ile
     ölüyordu; artık cwd=proje kökü veriliyor ve hata YUTULMUYOR (loglanıyor).
  2. yfinance 1.4.x TEK sembolde de MultiIndex sütun döndürüyor; hem
     asset_service hem price_service tek-sembol dalı `float(DataFrame)` ile
     TypeError alıp fiyatı sessizce düşürüyordu.

Ağ gerektiren testler yok — yfinance yanıtı sahte bir DataFrame ile taklit
edilir; subprocess çağrısı mock'lanır.
"""
import os
import subprocess
import unittest
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SubprocessInvocationTest(unittest.TestCase):
    """fetch_portfolio_with_prices'ın alt süreç çağrısının sözleşmesi."""

    def _run_isolated(self, fake_proc):
        """İzole worker dalını, subprocess.run mock'lanmış hâlde çalıştırır."""
        import services.asset_service as asset_service

        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return fake_proc

        import time
        results = []
        # İzole worker daemon thread'de koşar; mock'lar thread bitene kadar AKTİF
        # kalmalı, yoksa thread patch kalkınca GERÇEK subprocess'i çalıştırır.
        with mock.patch.object(asset_service, "_read_cached_portfolio",
                               return_value=None), \
             mock.patch.object(asset_service, "_store_cached_portfolio"), \
             mock.patch("subprocess.run", side_effect=fake_run):
            asset_service.fetch_portfolio_with_prices(
                [{"id": 1, "asset_code": "THYAO.IS", "asset_type": "Hisse",
                  "quantity": 1, "purchase_price": 1.0, "asset_name": "x"}],
                callback=results.append, force_refresh=True,
            )
            deadline = time.monotonic() + 3
            while not results and time.monotonic() < deadline:
                time.sleep(0.02)
        return captured, results

    def test_subprocess_runs_with_project_root_cwd(self):
        """cwd proje köküne sabitlenmeli (ModuleNotFoundError kök nedeni)."""
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        captured, _ = self._run_isolated(fake_proc)
        self.assertEqual(captured["kwargs"].get("cwd"), PROJECT_ROOT)

    def test_subprocess_captures_streams_not_devnull(self):
        """stderr görünür olmalı: PIPE, DEVNULL değil."""
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        captured, _ = self._run_isolated(fake_proc)
        self.assertEqual(captured["kwargs"].get("stderr"), subprocess.PIPE)
        self.assertEqual(captured["kwargs"].get("stdout"), subprocess.PIPE)

    def test_nonzero_exit_is_logged_not_swallowed(self):
        """Alt süreç çökerse stderr KALICI log'a yazılmalı.

        Bu test eskiden `builtins.print`i gözlüyordu. Ama paketlenmiş Windows
        uygulaması `console=False` ile derleniyor (archlence.spec:180), yani
        print çıktısı hiçbir yere gitmiyor — "loglandı" demek orada pratikte
        "kayboldu" demekti. Artık gerçek rotating logger'a yazıldığını
        doğruluyoruz; kullanıcının gönderebileceği tek kanıt o dosya.
        """
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="",
            stderr="ModuleNotFoundError: No module named 'services'")
        fake_logger = mock.Mock()
        with mock.patch("utils.logging_config.get_logger",
                        return_value=fake_logger):
            self._run_isolated(fake_proc)

        logged = " ".join(
            str(part)
            for call in fake_logger.error.call_args_list
            for part in call.args
        )
        self.assertIn("ModuleNotFoundError", logged)


class MultiIndexCloseTest(unittest.TestCase):
    """Tek sembol MultiIndex'i her iki fiyat yolunda da doğru okunmalı."""

    def _single_ticker_frame(self):
        """yfinance 1.4.x'in TEK sembolde döndürdüğü MultiIndex'i taklit eder."""
        import pandas as pd
        columns = pd.MultiIndex.from_tuples(
            [("Close", "THYAO.IS"), ("Open", "THYAO.IS")])
        return pd.DataFrame([[310.0, 300.0], [312.0, 311.0]], columns=columns)

    def test_price_service_reads_single_ticker_multiindex(self):
        from services.price_service import _extract_last_close
        frame = self._single_ticker_frame()
        # single=True olsa bile MultiIndex'ten doğru skaler çıkmalı.
        self.assertEqual(
            _extract_last_close(frame, "THYAO.IS", True), 312.0)

    def test_price_service_download_single_ticker(self):
        import services.price_service as price_service
        frame = self._single_ticker_frame()
        with mock.patch("yfinance.download", return_value=frame):
            self.assertEqual(
                price_service._download_batch(["THYAO.IS"]), {"THYAO.IS": 312.0})

    def test_flat_series_still_works(self):
        """Eski yfinance'in düz Close'u da (regresyon) okunabilmeli."""
        import pandas as pd
        from services.price_service import _extract_last_close
        flat = pd.DataFrame({"Close": [310.0, 312.0]})
        self.assertEqual(_extract_last_close(flat, "THYAO.IS", True), 312.0)


if __name__ == "__main__":
    unittest.main()
