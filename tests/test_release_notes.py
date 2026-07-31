import unittest

from scripts.release_notes_from_changelog import extract_release_notes


class ReleaseNotesFromChangelogTest(unittest.TestCase):
    def test_exact_version_section_is_extracted(self):
        headings = (
            "Highlights",
            "Financial correctness and reliability",
            "Performance",
            "UI and accessibility",
            "Testing and packaging",
            "Additional issues found and fixed",
            "Known limitations",
            "Installation and checksum verification",
        )
        body = "\n".join(f"### {heading}\n\n- x" for heading in headings)
        changelog = f"# Changelog\n\n## [0.0.2] — 2026-07-30\n\n{body}\n\n## [0.0.1]\n"
        notes = extract_release_notes(changelog, "0.0.2")
        self.assertTrue(notes.startswith("# Archlence v0.0.2"))
        self.assertNotIn("## [0.0.1]", notes)

    def test_missing_required_heading_fails_release(self):
        with self.assertRaises(ValueError):
            extract_release_notes(
                "# Changelog\n\n## [0.0.2] — 2026-07-30\n\n- incomplete",
                "0.0.2",
            )


if __name__ == "__main__":
    unittest.main()
