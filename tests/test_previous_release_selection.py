"""Upgrade smoke GERÇEK önceki sürümü seçmeli, sabit `v0.0.1`'i değil.

`build-windows.yml` sabit `UPGRADE_BASELINE_TAG: "v0.0.1"` kullanıyordu. Bu,
"önceki sürümden yükseltme" iddiasını doğrulamıyordu: v0.0.8 → v0.0.9 yolu hiç
sınanmıyor, bunun yerine sekiz sürüm eskisi test ediliyordu — yani
kullanıcıların gerçekte izlediği yol test edilmemiş kalıyordu.
"""

import unittest

from scripts.previous_release import parse_version, select_previous


class PreviousReleaseSelectionTest(unittest.TestCase):
    ALL = ["v0.0.1", "v0.0.2", "v0.0.3", "v0.0.4",
           "v0.0.5", "v0.0.6", "v0.0.7", "v0.0.8"]

    def test_target_009_selects_008(self):
        self.assertEqual(select_previous("0.0.9", self.ALL), "v0.0.8")

    def test_target_008_selects_007(self):
        self.assertEqual(select_previous("0.0.8", self.ALL), "v0.0.7")

    def test_unordered_tags_are_sorted_correctly(self):
        shuffled = ["v0.0.3", "v0.0.8", "v0.0.1", "v0.0.7", "v0.0.5"]
        self.assertEqual(select_previous("0.0.9", shuffled), "v0.0.8")

    def test_lexical_ordering_does_not_win_over_semver(self):
        """`v0.0.10` metin sıralamasında `v0.0.9`dan ÖNCE gelir."""
        tags = ["v0.0.9", "v0.0.10", "v0.0.2"]
        self.assertEqual(select_previous("0.1.0", tags), "v0.0.10")

    def test_duplicate_tags_are_deduplicated(self):
        tags = ["v0.0.8", "v0.0.8", "0.0.8", "v0.0.7"]
        self.assertEqual(select_previous("0.0.9", tags), "0.0.8")

    def test_malformed_tags_are_skipped_not_fatal(self):
        tags = ["backup/pre-split-2139", "release-candidate",
                "v0.0.8", "vX.Y.Z", ""]
        self.assertEqual(select_previous("0.0.9", tags), "v0.0.8")

    def test_current_target_is_never_selected(self):
        tags = ["v0.0.9", "v0.0.8"]
        self.assertEqual(select_previous("0.0.9", tags), "v0.0.8")

    def test_newer_tags_are_never_selected(self):
        tags = ["v0.1.0", "v0.0.9", "v0.0.7"]
        self.assertEqual(select_previous("0.0.8", tags), "v0.0.7")

    def test_only_current_tag_raises_instead_of_falling_back(self):
        """Aday yoksa AÇIK hata — sabit bir sürüme sessizce düşülmemeli."""
        with self.assertRaises(LookupError):
            select_previous("0.0.9", ["v0.0.9"])

    def test_empty_tag_list_raises(self):
        with self.assertRaises(LookupError):
            select_previous("0.0.9", [])

    def test_prereleases_are_excluded_by_default(self):
        tags = ["v0.0.9-rc1", "v0.0.8"]
        self.assertEqual(select_previous("0.0.9", tags), "v0.0.8")

    def test_prereleases_can_be_opted_in(self):
        tags = ["v0.0.9-rc1", "v0.0.8"]
        self.assertEqual(
            select_previous("0.0.9", tags, allow_prerelease=True),
            "v0.0.9-rc1",
        )

    def test_prerelease_sorts_before_its_stable_release(self):
        tags = ["v0.0.8-rc1", "v0.0.8"]
        self.assertEqual(
            select_previous("0.0.9", tags, allow_prerelease=True), "v0.0.8"
        )

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            select_previous("bozuk", self.ALL)

    def test_parse_version_accepts_both_prefixes(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3, None))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3, None))
        self.assertEqual(parse_version("1.2.3-rc1"), (1, 2, 3, "rc1"))
        self.assertIsNone(parse_version("backup/pre-split"))

    def test_real_repository_history_selects_008_for_009(self):
        """Deponun gerçek etiket geçmişiyle sağlama."""
        import subprocess

        result = subprocess.run(
            ["git", "tag"], capture_output=True, text=True, check=True
        )
        tags = result.stdout.splitlines()
        self.assertIn("v0.0.8", tags, "test varsayımı: v0.0.8 etiketi var")
        self.assertEqual(select_previous("0.0.9", tags), "v0.0.8")


if __name__ == "__main__":
    unittest.main()
