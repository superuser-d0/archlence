import io
import re
import tokenize
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTACT_EMAIL = "Superkullaniciyapiyor@proton.me"


def _tracked_source_files():
    excluded = {".git", ".venv", "venv", "build", "dist", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or excluded.intersection(path.parts):
            continue
        if path.suffix.lower() in {
            ".py", ".md", ".kv", ".yml", ".yaml", ".iss", ".spec",
            ".toml", ".txt", ".json",
        } or path.name in {".gitignore", "PKGBUILD", "LICENSE"}:
            yield path


class RepositoryPrivacyTest(unittest.TestCase):
    def test_personal_identity_and_developer_home_paths_are_absent(self):
        forbidden = (
            re.compile("mehmet\\s+cem\\s+" + "çakırgöz", re.IGNORECASE),
            re.compile("mehmet\\s+cem\\s+" + "cakirg[oö]z", re.IGNORECASE),
            re.compile("ck" + "rgz", re.IGNORECASE),
            re.compile(r"/home/c" + r"em(?:/|\\)", re.IGNORECASE),
        )
        findings = []
        for path in _tracked_source_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in forbidden:
                if pattern.search(text):
                    findings.append(str(path.relative_to(ROOT)))
                    break
        self.assertEqual(findings, [])

    def test_local_agent_configuration_is_not_part_of_the_repository(self):
        self.assertFalse((ROOT / ".claude" / "settings.local.json").exists())
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".claude/", ignore)

    def test_contact_address_is_consistent_on_public_surfaces(self):
        for relative in ("README.md", "SECURITY.md", "CODE_OF_CONDUCT.md"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(CONTACT_EMAIL, text)

        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        installer = (ROOT / "installer" / "archlence.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'ARCHLENCE_CONTACT_EMAIL = "{CONTACT_EMAIL}"', main_source)
        self.assertIn('#define MyAppPublisher "Archlence"', installer)

    def test_public_ui_is_english_only(self):
        from ui.i18n import SUPPORTED_LANGUAGES, set_language, tr

        self.assertEqual(SUPPORTED_LANGUAGES, {"en": "English"})
        self.assertEqual(set_language("tr"), "en")
        self.assertEqual(tr("Ayarlar", "tr"), "Settings")

        kv = (ROOT / "ui" / "dashboard.kv").read_text(encoding="utf-8")
        self.assertNotIn("open_language_dialog", kv)
        self.assertNotIn('text: "English" if', kv)

    def test_source_comments_do_not_contain_turkish_characters(self):
        turkish_characters = frozenset("çÇğĞıİöÖşŞüÜ")
        findings = []
        for path in _tracked_source_files():
            if path.suffix.lower() not in {
                ".py", ".kv", ".yml", ".yaml", ".spec", ".iss"
            } and path.name not in {".gitignore", "PKGBUILD"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix.lower() == ".py" or path.name.endswith(".spec"):
                try:
                    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
                    for token in tokens:
                        if token.type == tokenize.COMMENT and (
                            turkish_characters.intersection(token.string)
                        ):
                            findings.append(
                                f"{path.relative_to(ROOT)}:{token.start[0]}"
                            )
                except (tokenize.TokenError, IndentationError):
                    findings.append(f"{path.relative_to(ROOT)}:tokenize")

            marker = ";" if path.suffix.lower() == ".iss" else "#"
            for number, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith(marker) and (
                    turkish_characters.intersection(line)
                ):
                    finding = f"{path.relative_to(ROOT)}:{number}"
                    if finding not in findings:
                        findings.append(finding)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
