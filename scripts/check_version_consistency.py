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
        rf"### {escaped} —",
        "README.md",
        "README changelog sürümü",
    )
    require(
        rf"## \[{escaped}\]",
        "CHANGELOG.md",
        "CHANGELOG sürümü",
    )
    require(
        rf"# Archlence v{escaped}",
        "docs/releases/v1.0.0.md",
        "Release notu başlığı",
    )
    require(
        rf"ArchlenceSetup-{escaped}\.exe",
        "docs/releases/v1.0.0.md",
        "Windows release dosya adı",
    )
    require(
        rf"Archlence-{escaped}-x86_64\.AppImage",
        "docs/releases/v1.0.0.md",
        "Linux release dosya adı",
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
