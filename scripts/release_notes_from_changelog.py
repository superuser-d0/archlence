"""Extract the exact CHANGELOG section for a release tag."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def extract_release_notes(changelog: str, version: str) -> str:
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog)
    if not match:
        raise ValueError(f"CHANGELOG section not found for {version}")
    body = match.group("body").strip()
    required = (
        "Öne çıkan değişiklikler",
        "Finansal doğruluk ve güvenilirlik",
        "Performans",
        "UI ve erişilebilirlik",
        "Test ve paketleme",
        "Çalışma sırasında bulunup düzeltilen ek sorunlar",
        "Bilinen sınırlamalar",
        "Kurulum ve checksum doğrulaması",
    )
    missing = [heading for heading in required if f"### {heading}" not in body]
    if missing:
        raise ValueError(
            "CHANGELOG release section is missing headings: "
            + ", ".join(missing)
        )
    return f"# Archlence v{version}\n\n{body}\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    changelog = Path(args.changelog).read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, args.version)
    Path(args.output).write_text(notes, encoding="utf-8")


if __name__ == "__main__":
    main()
