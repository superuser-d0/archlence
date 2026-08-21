"""Fail packaging when user data, secrets or developer paths are bundled."""

import argparse
import re
import zipfile
from pathlib import Path

FORBIDDEN_NAMES = {
    "finance.db",
    "encryption.key",
    ".env",
    "archlence.log",
    "crash.log",
}
FORBIDDEN_PARTS = {
    ".git",
    "__pycache__",
    "tests",
    "test",
    "fixtures",
    "db_backups",
}
TEXT_PATTERNS = {
    "developer-home": re.compile(
        rb"/home/[^/\x00]{1,64}/|\\\\Users\\\\[^\\\x00]{1,64}\\\\|"
        rb"Documents[/\\\\]archlence",
        re.IGNORECASE,
    ),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
}


def inspect_files(files):
    findings = []
    for name, content in files:
        path = Path(name)
        lowered = {part.lower() for part in path.parts}
        if path.name.lower() in FORBIDDEN_NAMES:
            findings.append(f"forbidden-name:{name}")
        if lowered & FORBIDDEN_PARTS:
            findings.append(f"development-content:{name}")
        # PyInstaller stores Python sources in PYZ/bytecode. Scan every file as
        # bytes so developer paths and tokens cannot hide inside binaries.
        if len(content) <= 100_000_000:
            for label, pattern in TEXT_PATTERNS.items():
                if pattern.search(content):
                    findings.append(f"{label}:{name}")
    return findings


def directory_files(root):
    for path in root.rglob("*"):
        if path.is_file():
            yield str(path.relative_to(root)), path.read_bytes()


def archive_files(path):
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                yield info.filename, archive.read(info)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    args = parser.parse_args()
    target = Path(args.target)
    if target.is_dir():
        files = list(directory_files(target))
    elif zipfile.is_zipfile(target):
        files = list(archive_files(target))
    else:
        files = [(target.name, target.read_bytes())]
    findings = inspect_files(files)
    # Some Windows runners use cp1252 stdout. Keep gate output ASCII-safe.
    print(f"Inspected files: {len(files)}")
    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print("Package content/secret scan passed.")


if __name__ == "__main__":
    main()
