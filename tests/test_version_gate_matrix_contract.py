"""Sürüm mutation matrisinin kendisi sürüme bağlı OLMAMALI.

NEDEN VAR: matris altı vakada aranan dizeyi `0.0.8` olarak SABİT yazmıştı.
v0.0.9 bump'ında sessizce bozuldu — üç vaka "uygulanamadı"ya düştü, üçü de
CHANGELOG'un TARİHSEL `## [0.0.8]` bölümünü mutasyona uğratıp "kaçtı"
raporladı (kapı haklı olarak eski bölümü umursamıyor). Yani sürüm kapısını
sınayan araç, her sürüm bump'ında kendi kendini geçersiz kılıyordu.

Bu, denetimin tekrar eden temasının aynısı: yeşil raporlayan ama aslında
bir şey ölçmeyen bir kapı. Buradaki testler o kalıbın geri gelmesini
engeller.
"""

import re
import unittest

from scripts.audit import version_mutation_matrix as matrix
from utils.version import APP_VERSION

_SEMVER = re.compile(r"\b\d+\.\d+\.\d+\b")


class MatrixIsVersionAgnosticTest(unittest.TestCase):
    def test_no_needle_hardcodes_a_version(self):
        """Aranan dizeler sürüm içeremez — yer tutucu kullanılmalı.

        `replacement` tarafı serbest: oraya bilerek `9.9.9` veya `v0.0.1`
        gibi YANLIŞ değerler yazılıyor, mutation'ın kendisi bu.
        """
        offenders = []
        for case_id, _label, relative, needle, _replacement in matrix.CASES:
            for found in _SEMVER.findall(needle):
                offenders.append(f"{case_id} ({relative}): {found!r} in {needle[:50]!r}")
        self.assertEqual(
            offenders, [],
            "Aranan dizede sabit sürüm var; bir sonraki bump'ta bu vaka "
            "sessizce ölçmeyi bırakır. `@@VERSION@@` kullan. Bulunanlar: "
            + "; ".join(offenders),
        )

    def test_placeholder_is_substituted_for_the_tested_tree(self):
        """Yer tutucu gerçekten değiştiriliyor mu — kuralın işe yaradığı."""
        templated = [
            case for case in matrix.CASES if "@@VERSION@@" in case[3]
        ]
        self.assertGreaterEqual(
            len(templated), 6,
            "sürüme bağlı vakalar yer tutucu kullanmalı",
        )
        for _id, _label, _rel, needle, _repl in templated:
            resolved = needle.replace("@@VERSION@@", APP_VERSION)
            self.assertIn(APP_VERSION, resolved)
            self.assertNotIn("@@VERSION@@", resolved)

    def test_placeholder_does_not_collide_with_shell_variables(self):
        """`{v}` yer tutucusu KULLANILAMAZ.

        İki vaka workflow'daki gerçek `${v}` kabuk değişkenini arıyor;
        `str.format` onları `$<sürüm>`'e çevirip vakayı uygulanamaz kılardı.
        Bu test o çözümün geri gelmemesini sağlıyor.
        """
        shell_cases = [c for c in matrix.CASES if "${v}" in c[3]]
        self.assertTrue(shell_cases, "beklenen `${v}` vakaları kayboldu")
        for case in shell_cases:
            resolved = case[3].replace("@@VERSION@@", APP_VERSION)
            self.assertIn("${v}", resolved,
                          "kabuk değişkeni bozulmuş — yer tutucu çakışıyor")
            # `str.format` kullanılsaydı `${v}` -> `$<sürüm>` olurdu.
            self.assertNotIn(f"${APP_VERSION}", resolved)

    def test_version_is_read_from_the_tree_under_test(self):
        """Sürüm, sınanan ağaçtan okunmalı — bu sürecin modülünden değil."""
        import pathlib

        root = pathlib.Path(matrix.ROOT)
        self.assertEqual(matrix._version_of(root), APP_VERSION)


if __name__ == "__main__":
    unittest.main()
