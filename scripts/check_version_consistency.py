"""Fail release builds when duplicated packaging metadata drifts."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.version import APP_VERSION


def require(pattern, path, description):
    text = (ROOT / path).read_text(encoding="utf-8")
    if not re.search(pattern, text, re.MULTILINE):
        raise SystemExit(
            f"{description} {APP_VERSION!r} ile eşleşmiyor: {path}"
        )


def main():
    escaped = re.escape(APP_VERSION)
    require(
        rf'#define MyAppVersion "{escaped}"',
        "installer/archlence.iss",
        "Installer sürümü",
    )
    require(
        rf'default: "{escaped}"',
        ".github/workflows/build-windows.yml",
        "Windows workflow sürümü",
    )
    require(
        rf"^pkgver={escaped}$",
        "PKGBUILD",
        "Arch Linux paket sürümü",
    )
    require(
        rf"### {escaped} —",
        "README.md",
        "README changelog sürümü",
    )
    require(
        rf"## \[{escaped}\]",
        "CHANGELOG.md",
        "CHANGELOG sürümü",
    )
    from scripts.release_notes_from_changelog import extract_release_notes

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes = extract_release_notes(changelog, APP_VERSION)
    for expected in (
        f"# Archlence v{APP_VERSION}",
        f"ArchlenceSetup-{APP_VERSION}.exe",
        f"Archlence-{APP_VERSION}-x86_64.AppImage",
    ):
        if expected not in release_notes:
            raise SystemExit(
                f"CHANGELOG-derived release notes missing {expected!r}"
            )
    require(
        r'text: "Archlence v" \+ app\.version',
        "ui/dashboard.kv",
        "About ekranı sürüm binding'i",
    )
    require(
        r'--title "Archlence v\$\{v\}"',
        ".github/workflows/release.yml",
        "Release başlığı",
    )
    print(f"Sürüm tutarlı: {APP_VERSION} / tag v{APP_VERSION}")


if __name__ == "__main__":
    main()
