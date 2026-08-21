"""Kaçış YALNIZ sürüm işareti taşıyan satırlarda geri çözülmeli.

ÖLÇÜLEN KUSUR: importer `kayit_turu` kolonunu görünce dosyayı yeni kaçış
sözleşmesine sahip sayıyordu. Ama o kolon v0.0.12 ve daha eski Archlence
export'larında da vardı ve o dosyalarda kaçış YOKTU. Sonuç, eski bir dosyadaki
GERÇEK kullanıcı apostrofunun yenmesiydi — ölçüldü:

    eski export : aciklama = '=gercek-kullanici-metni
    içe aktarım : aciklama =  =gercek-kullanici-metni      <-- apostrof KAYIP
    eski export : aciklama = ''=iki-apostrof
    içe aktarım : aciklama =  '=iki-apostrof               <-- biri KAYIP

İKİNCİ ÖLÇÜLEN KUSUR: `kayit_turu` HAM anahtarla (`row.get("kayit_turu")`)
okunuyordu. `DictReader`'ın anahtarları başlığın kendisidir, yani `KAYIT_TURU`
ya da ` kayit_turu ` yazan bir dosyada bu okuma hep `None` dönüyor ve her satır
"islem değil" sayılıp SESSİZCE düşüyordu — `skipped` bile artmıyordu:

    KAYIT_TURU başlıklı 1 satırlık dosya -> ([], 0)

Çözüm: `_archlence_csv_version` kolonu. Satır başına taşınır, çünkü bir dosya
elle düzenlenmiş ve satırları karıştırılmış olabilir.
"""
import tempfile
import unittest
from pathlib import Path

from services.migration_service import (
    CSV_ESCAPE_VERSION,
    CSV_HEADER,
    CSV_VERSION_COLUMN,
    SUPPORTED_CSV_VERSIONS,
    parse_transactions_csv,
)

LEGACY_HEADER = "kayit_turu,tarih,tur,kategori,tutar,miktar,aciklama,detay"
VERSIONED_HEADER = (
    f"{CSV_VERSION_COLUMN},kayit_turu,tarih,tur,kategori,tutar,"
    "miktar,aciklama,detay"
)


class CsvVersionMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def _parse(self, text):
        path = Path(self.tempdir.name) / "in.csv"
        path.write_text(text, encoding="utf-8-sig", newline="")
        return parse_transactions_csv(str(path))

    def _legacy(self, description, category="Market"):
        """v0.0.12 export'u: `kayit_turu` VAR, sürüm işareti YOK."""
        return (
            LEGACY_HEADER + "\n"
            f"islem,2026-01-15,gider,{category},100.00,,{description},\n"
        )

    def _versioned(self, description, version=str(CSV_ESCAPE_VERSION)):
        return (
            VERSIONED_HEADER + "\n"
            f"{version},islem,2026-01-15,gider,Market,100.00,,{description},\n"
        )

    # ── eski Archlence dosyaları: hiçbir apostrof sökülmez ───────────────
    def test_legacy_export_keeps_a_real_leading_apostrophe(self):
        records, skipped = self._parse(self._legacy("'=literal"))
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "'=literal")

    def test_legacy_export_keeps_a_doubled_apostrophe(self):
        records, skipped = self._parse(self._legacy("''=literal"))
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "''=literal")

    def test_legacy_export_keeps_a_category_apostrophe(self):
        records, _ = self._parse(self._legacy("normal", category="'@kategori"))
        self.assertEqual(records[0]["category"], "'@kategori")

    # ── işaretli (v2) dosyalar: kaçış geri çözülür ───────────────────────
    def test_versioned_rows_are_unescaped(self):
        records, skipped = self._parse(self._versioned("''=literal"))
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "'=literal")

    def test_the_marker_is_the_first_exported_column(self):
        self.assertEqual(CSV_HEADER[0], CSV_VERSION_COLUMN)
        self.assertIn(CSV_ESCAPE_VERSION, SUPPORTED_CSV_VERSIONS)

    # ── belirsiz / bozuk / karışık işaret: tahmin YOK ────────────────────
    def test_an_unreadable_marker_is_skipped_rather_than_guessed(self):
        for marker in ("", "abc", "0", "99", "2.5", "-2", "  "):
            with self.subTest(marker=marker):
                records, skipped = self._parse(
                    self._versioned("'=literal", version=marker)
                )
                self.assertEqual(records, [], f"{marker!r} yorumlandı")
                self.assertEqual(skipped, 1)

    def test_mixed_versions_are_judged_row_by_row(self):
        text = (
            VERSIONED_HEADER + "\n"
            "2,islem,2026-01-15,gider,Market,100.00,,''=escaped,\n"
            "9,islem,2026-01-16,gider,Market,100.00,,'=bilinmeyen,\n"
        )
        records, skipped = self._parse(text)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["description"], "'=escaped")
        self.assertEqual(skipped, 1)

    # ── başlık normalizasyonu: satır sessizce düşmemeli ──────────────────
    def test_uppercase_and_padded_headers_are_read_not_dropped(self):
        for header in ("KAYIT_TURU", " kayit_turu ", "Kayit_Turu"):
            with self.subTest(header=header):
                text = (
                    f"{header},tarih,tur,kategori,tutar,aciklama\n"
                    "islem,2026-01-15,gider,Market,100.00,test\n"
                )
                records, skipped = self._parse(text)
                self.assertEqual(len(records), 1, f"{header!r} satırı düşürdü")
                self.assertEqual(skipped, 0)
                self.assertEqual(records[0]["description"], "test")

    def test_a_padded_version_header_is_also_recognised(self):
        text = (
            f" {CSV_VERSION_COLUMN.upper()} ,kayit_turu,tarih,tur,kategori,"
            "tutar,aciklama\n"
            "2,islem,2026-01-15,gider,Market,100.00,''=escaped\n"
        )
        records, skipped = self._parse(text)
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "'=escaped")

    def test_an_unknown_record_kind_is_counted_not_silently_dropped(self):
        text = (
            "kayit_turu,tarih,tur,kategori,tutar,aciklama\n"
            "bilinmeyen,2026-01-15,gider,Market,100.00,test\n"
        )
        records, skipped = self._parse(text)
        self.assertEqual(records, [])
        self.assertEqual(skipped, 1)

    def test_asset_and_debt_rows_are_still_skipped_without_counting(self):
        text = (
            "kayit_turu,tarih,tur,kategori,tutar,aciklama\n"
            "varlik,2026-01-15,Hisse,ABC,100.00,Varlık\n"
            "borc,,,,500.00,Borç\n"
            "tekrarlanan,2026-02-01,monthly,Abonelik,50.00,Servis\n"
            "islem,2026-01-15,gider,Market,100.00,test\n"
        )
        records, skipped = self._parse(text)
        self.assertEqual(len(records), 1)
        self.assertEqual(skipped, 0)

    # ── üçüncü taraf dosyalar ────────────────────────────────────────────
    def test_third_party_csv_apostrophe_is_untouched(self):
        text = (
            "tarih,tur,kategori,tutar,aciklama\n"
            "2026-01-15,gider,Market,100.00,'=yabanci-veri\n"
        )
        records, skipped = self._parse(text)
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "'=yabanci-veri")

    # ── normal davranış korunuyor ────────────────────────────────────────
    def test_amount_date_and_type_behaviour_is_unchanged(self):
        text = (
            "kayit_turu,tarih,tur,kategori,tutar,aciklama\n"
            'islem,15.01.2026,gelir,Maaş,"1.234,56",Ocak\n'
        )
        records, skipped = self._parse(text)
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["type"], "income")
        self.assertEqual(records[0]["date"], "2026-01-15 00:00:00")
        self.assertAlmostEqual(records[0]["amount"], 1234.56)

    def test_non_finite_amounts_are_still_refused(self):
        for amount in ("inf", "-inf", "nan", "Infinity"):
            with self.subTest(amount=amount):
                text = (
                    "kayit_turu,tarih,tur,kategori,tutar,aciklama\n"
                    f"islem,2026-01-15,gider,Market,{amount},test\n"
                )
                records, skipped = self._parse(text)
                self.assertEqual(records, [])
                self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
