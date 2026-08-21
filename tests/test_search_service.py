"""Hesap/kategori aramasının sözleşmesi — özellikle Türkçe katlama.

NEDEN VAR: ana sayfadaki arama çubuğu uzun süre hiçbir işleyiciye bağlı
değildi ve tek kapısı yalnızca NASIL GÖRÜNDÜĞÜNÜ ölçüyordu. Bu paket, arama
kutusunun bir ŞEY YAPTIĞINI ölçer.

Buradaki testlerin çoğu Türkçe büyük/küçük harf katlamasına ayrılmış, çünkü
kırılan yer orası: `"I".casefold()` → `"i"` ama `"ı".casefold()` → `"ı"`.
Yani düz `casefold` ile "ISI" yazan kullanıcı "ısı" kaydını BULAMAZ. Depodaki
diğer iki arama kutusu (budget_mixin, asset_mixin) hâlâ düz `casefold`
kullanıyor; bu paket yeni servisin o tuzağa düşmediğini sabitliyor.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")

from services.search_service import (
    ACCOUNT, CATEGORY, match_names, matches, normalize,
)


class MatchesTest(unittest.TestCase):
    """Liste filtreleyen çağıranların ortak yardımcısı.

    `search()`in tersine BOŞ SORGU her şeyi geçirir: bu fonksiyon "filtrele"
    için, "ara" için değil.
    """

    def test_empty_query_lets_everything_through(self):
        for query in ("", "   ", None):
            with self.subTest(query=query):
                self.assertTrue(matches(query, "herhangi bir sey"))

    def test_matches_any_of_the_given_fields(self):
        self.assertTrue(matches("btc", "BTC", "Bitcoin"))
        self.assertTrue(matches("bitcoin", "BTC", "Bitcoin"))
        self.assertFalse(matches("ethereum", "BTC", "Bitcoin"))

    def test_turkish_bist_name_is_found_without_special_characters(self):
        """Asıl kusur buydu: `.lower()` ile bu arama BOŞ dönüyordu."""
        self.assertTrue(matches("is bankasi", "ISCTR", "İŞ BANKASI"))
        self.assertTrue(matches("İŞ", "ISCTR", "İŞ BANKASI"))
        self.assertTrue(matches("tupras", "TUPRS", "TÜPRAŞ"))

    def test_dotless_and_dotted_i_are_interchangeable_in_filters(self):
        self.assertTrue(matches("ISI", "Isıtma"))
        self.assertTrue(matches("ısı", "ISITMA"))

    def test_no_candidates_means_no_match_unless_query_is_empty(self):
        self.assertFalse(matches("btc"))
        self.assertTrue(matches(""))

    def test_none_fields_do_not_raise(self):
        self.assertFalse(matches("btc", None, ""))


class NormalizeTest(unittest.TestCase):
    def test_dotted_and_dotless_i_all_fold_together(self):
        """Türkçe aramanın en sık kırıldığı yer.

        Dört yazım da aynı kelimedir; kullanıcı hangisini yazarsa yazsın
        diğerlerini bulmalı.
        """
        forms = ["ISI", "ısı", "İSİ", "Isı", "isi"]
        normalized = {normalize(form) for form in forms}
        self.assertEqual(
            normalized, {"isi"},
            f"ı/İ/I/i aynı yere inmedi: {normalized}",
        )

    def test_capital_dotted_i_does_not_leave_a_combining_mark(self):
        """`"İ".casefold()` "i" + U+0307 üretir — görsel olarak "i", eşit değil."""
        self.assertEqual(normalize("İstanbul"), "istanbul")
        self.assertNotIn("̇", normalize("İ"))

    def test_diacritics_are_folded_so_plain_typing_finds_them(self):
        self.assertEqual(normalize("Şirket"), "sirket")
        self.assertEqual(normalize("Günlük"), "gunluk")
        self.assertEqual(normalize("Öğrenci"), "ogrenci")
        self.assertEqual(normalize("Çanta"), "canta")

    def test_whitespace_is_collapsed_and_trimmed(self):
        self.assertEqual(normalize("  Kredi   Kartı  "), "kredi karti")

    def test_none_and_empty_are_safe(self):
        self.assertEqual(normalize(None), "")
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize("   "), "")


class MatchNamesTest(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"name": "Nakit"},
            {"name": "Nakit Olmayan"},
            {"name": "Banka Hesabı"},
            {"name": "Şirket Kartı"},
            {"name": "Ísı Gideri"},
        ]

    def test_empty_query_matches_nothing(self):
        """Odaklanınca tüm profili dökmemeli."""
        for query in ("", "   ", None):
            with self.subTest(query=query):
                self.assertEqual(match_names(query, self.items), [])

    def test_exact_match_outranks_prefix_and_substring(self):
        names = [item["name"] for item in match_names("Nakit", self.items)]
        self.assertEqual(names[0], "Nakit")
        self.assertIn("Nakit Olmayan", names)

    def test_prefix_outranks_substring(self):
        items = [{"name": "Olmayan Nakit"}, {"name": "Nakit Akışı"}]
        names = [item["name"] for item in match_names("nakit", items)]
        self.assertEqual(names, ["Nakit Akışı", "Olmayan Nakit"])

    def test_turkish_query_finds_differently_cased_record(self):
        """Kullanıcı noktasız yazdı, kayıt noktalı — yine bulmalı."""
        names = [item["name"] for item in match_names("isi", self.items)]
        self.assertIn("Ísı Gideri", names)

    def test_accentless_query_finds_accented_record(self):
        names = [item["name"] for item in match_names("sirket", self.items)]
        self.assertEqual(names, ["Şirket Kartı"])

    def test_no_match_returns_empty(self):
        self.assertEqual(match_names("kripto", self.items), [])

    def test_ties_keep_caller_ordering(self):
        """Eşit puanlılar çağıranın sırasını korumalı — sonuç deterministik."""
        items = [{"name": "A Kart"}, {"name": "B Kart"}, {"name": "C Kart"}]
        names = [item["name"] for item in match_names("kart", items)]
        self.assertEqual(names, ["A Kart", "B Kart", "C Kart"])

    def test_input_dicts_are_not_mutated(self):
        original = [{"name": "Nakit", "id": 7}]
        match_names("nakit", original)
        self.assertEqual(original, [{"name": "Nakit", "id": 7}])

    def test_extra_fields_survive_into_results(self):
        results = match_names("nakit", [{"name": "Nakit", "id": 7, "kind": ACCOUNT}])
        self.assertEqual(results[0]["id"], 7)
        self.assertEqual(results[0]["kind"], ACCOUNT)


class SearchAgainstDatabaseTest(unittest.TestCase):
    """`search()`in gerçek SQL'i ve birleştirme sırası."""

    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, "
            "account_type TEXT)"
        )
        conn.execute("CREATE TABLE categories (name TEXT, type TEXT)")


        conn.execute(
            "CREATE TABLE transactions (id INTEGER PRIMARY KEY, "
            "account_id INTEGER, description TEXT, category TEXT, "
            "transaction_date TEXT)"
        )
        conn.executemany(
            "INSERT INTO accounts (id, name, account_type) VALUES (?, ?, ?)",
            [(1, "Ziraat Vadesiz", "checking"),
             (2, "Şirket Kartı", "credit_card"),
             (3, "Isıtma Fonu", "checking")],
        )
        conn.executemany(
            "INSERT INTO categories (name, type) VALUES (?, ?)",
            [("Market", "expense"), ("Isınma", "expense"), ("Maaş", "income")],
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def _search(self, query, **kwargs):
        from services import search_service

        conn = sqlite3.connect(self.db_path)

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *_exc):
                return False

        with mock.patch.object(
            search_service, "managed_connection", lambda: _Ctx()
        ):
            try:
                return search_service.search(query, **kwargs)
            finally:
                conn.close()

    def test_empty_query_never_touches_the_database(self):
        from services import search_service

        def _boom():
            raise AssertionError("boş sorgu için DB açılmamalı")

        with mock.patch.object(
            search_service, "managed_connection", _boom
        ):
            self.assertEqual(search_service.search("  "), [])

    def test_finds_account_and_category_in_one_list(self):
        results = self._search("isi")
        kinds = {item["kind"] for item in results}
        names = [item["name"] for item in results]
        self.assertEqual(kinds, {ACCOUNT, CATEGORY})
        self.assertIn("Isıtma Fonu", names)
        self.assertIn("Isınma", names)

    def test_accounts_come_before_categories(self):
        """Kullanıcının kendi hesabı, alfabetik olarak öne düşen bir
        kategorinin altında kalmamalı."""
        results = self._search("isi")
        first_category = next(
            index for index, item in enumerate(results)
            if item["kind"] == CATEGORY
        )
        last_account = max(
            index for index, item in enumerate(results)
            if item["kind"] == ACCOUNT
        )
        self.assertLess(last_account, first_category)

    def test_account_results_carry_id_and_type(self):
        results = self._search("ziraat")
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[0]["detail"], "checking")

    def test_category_results_carry_type_and_no_id(self):
        results = self._search("maas")
        self.assertEqual(results[0]["kind"], CATEGORY)
        self.assertEqual(results[0]["detail"], "income")
        self.assertIsNone(results[0]["id"])

    def test_limit_is_honoured(self):
        self.assertEqual(len(self._search("a", limit=2)), 2)

    def test_unmatched_query_returns_empty(self):
        self.assertEqual(self._search("kripto"), [])


class TransactionDescriptionSearchTest(unittest.TestCase):
    """Şifreli açıklamalarda arama — pencere sınırı dahil.

    Bu paketin asıl işi sınırın GERÇEKTEN uygulandığını sabitlemek. Pencere,
    yazma-zamanı indeks yerine seçilen güvenlik takasının ta kendisi: sessizce
    büyürse her tuş vuruşunda tüm veriyi çözer hâle geliriz (50.000 işlemde
    1,1 sn), sessizce küçülürse kullanıcı bulabildiği şeyleri bulamaz olur.
    """

    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE transactions (id INTEGER PRIMARY KEY, "
            "account_id INTEGER, description TEXT, category TEXT, "
            "transaction_date TEXT)"
        )
        self.conn = conn

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def _insert(self, rows):
        """`rows`: (id, düz_açıklama, kategori, tarih)."""
        from utils.crypto import encrypt
        from database.db import SECRET_KEY

        self.conn.executemany(
            "INSERT INTO transactions (id, account_id, description, category,"
            " transaction_date) VALUES (?, 1, ?, ?, ?)",
            [(i, encrypt(text, SECRET_KEY), cat, date)
             for i, text, cat, date in rows],
        )
        self.conn.commit()

    def _search(self, query, **kwargs):
        from services import search_service

        conn = sqlite3.connect(self.db_path)

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *_exc):
                return False

        with mock.patch.object(
            search_service, "managed_connection", lambda: _Ctx()
        ):
            try:
                return search_service.search_transactions(query, **kwargs)
            finally:
                conn.close()

    def test_finds_a_description_and_decrypts_it_for_display(self):
        self._insert([(1, "Market alışverişi", "Market", "2026-08-01")])
        results = self._search("market")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Market alışverişi")
        self.assertEqual(results[0]["kind"], "transaction")
        self.assertEqual(results[0]["detail"], "Market")

    def test_turkish_folding_applies_to_descriptions_too(self):
        self._insert([(1, "ISITMA faturası", "Fatura", "2026-08-01")])
        self.assertEqual(len(self._search("ısıtma")), 1)
        self.assertEqual(len(self._search("isitma")), 1)

    def test_empty_query_never_decrypts_anything(self):
        from services import search_service

        def _boom():
            raise AssertionError("boş sorgu için DB açılmamalı")

        with mock.patch.object(search_service, "managed_connection", _boom):
            self.assertEqual(search_service.search_transactions("  "), [])

    def test_window_bounds_how_far_back_the_search_reaches(self):
        """Pencerenin DIŞINDAKİ satır bulunmamalı — takasın görünür bedeli."""
        self._insert([
            (1, "eski kayit hedef", "X", "2020-01-01"),
            (2, "yeni kayit", "X", "2026-08-01"),
            (3, "yeni kayit", "X", "2026-08-02"),
        ])
        self.assertEqual(self._search("hedef", window=2), [])
        found = self._search("hedef", window=3)
        self.assertEqual(len(found), 1)

    def test_newest_rows_are_the_ones_inside_the_window(self):
        self._insert([
            (1, "alfa", "X", "2020-01-01"),
            (2, "beta", "X", "2026-08-02"),
        ])
        self.assertEqual(len(self._search("beta", window=1)), 1)
        self.assertEqual(self._search("alfa", window=1), [])

    def test_undecryptable_row_is_skipped_not_fatal(self):
        """Bozuk tek satır kutuyu tamamen çalışmaz hâle getirmemeli."""
        self._insert([(1, "market", "X", "2026-08-01")])
        self.conn.execute(
            "INSERT INTO transactions (id, account_id, description, category,"
            " transaction_date) VALUES (2, 1, 'AEADv1:bozuk', 'X', '2026-08-02')"
        )
        self.conn.commit()
        self.assertEqual(len(self._search("market")), 1)

    def test_limit_stops_the_decrypt_loop(self):
        self._insert([
            (i, f"market {i}", "X", f"2026-08-{i:02d}") for i in range(1, 6)
        ])
        self.assertEqual(len(self._search("market", limit=2)), 2)

    def test_missing_key_is_not_swallowed(self):
        """Anahtar yoksa bu bir satır sorunu değil; sessizce boş dönmemeli."""
        from services import search_service
        from utils.errors import KeyUnavailableError

        self._insert([(1, "market", "X", "2026-08-01")])
        conn = sqlite3.connect(self.db_path)

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *_exc):
                return False

        def _no_key(*_a, **_k):
            raise KeyUnavailableError("anahtar yok")

        with mock.patch.object(
            search_service, "managed_connection", lambda: _Ctx()
        ), mock.patch("utils.crypto.decrypt", _no_key):
            with self.assertRaises(KeyUnavailableError):
                search_service.search_transactions("market")
        conn.close()


if __name__ == "__main__":
    unittest.main()
