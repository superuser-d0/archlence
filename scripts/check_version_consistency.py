"""Fail release builds when packaging metadata or release-facing docs drift."""

import re
import sys
from pathlib import Path


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.version import APP_VERSION


def require(pattern, path, description):
    text = (ROOT / path).read_text(encoding="utf-8")
    if not re.search(pattern, text, re.MULTILINE):
        raise SystemExit(f"{description} is missing or invalid: {path}")


def main():
    escaped = re.escape(APP_VERSION)
    require(
        rf'#define MyAppVersion "{escaped}"',
        "installer/archlence.iss",
        "Installer version",
    )
    require(
        rf'default: "{escaped}"',
        ".github/workflows/build-windows.yml",
        "Windows workflow version",
    )
    require(
        rf"^pkgver={escaped}$",
        "PKGBUILD",
        "Arch Linux package version",
    )
    require(
        r"\[!\[Latest release\]\(https://img\.shields\.io/github/v/release/"
        r"superuser-d0/archlence\)\]"
        r"\(https://github\.com/superuser-d0/archlence/releases/latest\)",
        "README.md",
        "README stable-release badge",
    )
    require(
        rf"## \[{escaped}\]",
        "CHANGELOG.md",
        "CHANGELOG version",
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
        "About-screen version binding",
    )
    require(
        r'--title "Archlence v\$\{v\}"',
        ".github/workflows/release.yml",
        "Release title",
    )


    require(
        r'Archlence-\$\{v\}-x86_64\.AppImage',
        ".github/workflows/release.yml",
        "AppImage release asset name",
    )
    require(
        r'SHA256SUMS\.txt',
        ".github/workflows/release.yml",
        "Checksum filename",
    )
    require(
        r'Archlence-\$\{\{ needs\.version\.outputs\.version \}\}-sbom\.cdx\.json',
        ".github/workflows/release.yml",
        "SBOM filename",
    )


    require(
        r'Tag/input version .* does not match application version',
        ".github/workflows/release.yml",
        "Tag/application version match check",
    )


    windows = (ROOT / ".github/workflows/build-windows.yml").read_text(
        encoding="utf-8"
    )

    windows_code = "\n".join(
        line for line in windows.splitlines()
        if not line.lstrip().startswith("#")
    )
    if re.search(r"inputs\.version\s*\|\|\s*'[0-9]", windows_code):
        raise SystemExit(
            "Windows workflow contains a fixed version fallback: "
            ".github/workflows/build-windows.yml"
        )

    if re.search(r'UPGRADE_BASELINE_TAG:\s*"v[0-9]', windows_code):
        raise SystemExit(
            "Upgrade smoke baseline is pinned to a fixed version: "
            ".github/workflows/build-windows.yml"
        )
    print(f"Version metadata is consistent: {APP_VERSION} / tag v{APP_VERSION}")


if __name__ == "__main__":
    main()
