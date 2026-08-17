"""Fail Windows packaging when a lazily imported companion module is absent.

PyInstaller resolves imports statically.  A module imported *inside a function
body, at call time* is therefore invisible to it, and the package looks complete
right up to the moment a user reaches that code path.

This happened.  Kivy's file chooser calls ``win32file.GetFileAttributesExW`` to
read the hidden-file flag, and pywin32 imports ``win32timezone`` from inside
that call.  ``win32file`` was packaged, ``win32timezone`` was not, and opening
the restore dialog terminated the whole application on a real Windows 11
machine ("No module named 'win32timezone'").

The invariant is deliberately CONDITIONAL: the companion is required only when
its parent was actually packaged.  A build environment without pywin32 packages
neither, and that is correct rather than broken — Kivy skips the hidden-file
check when ``win32file`` cannot be imported.

HOW "PACKAGED" IS DECIDED, and why it is not a single byte search.  A PyInstaller
onedir bundle stores the two kinds of module in two different places, verified
against the real broken build (run 31629218009):

    win32file      -> _internal/win32/win32file.pyd     (extension: a FILE)
    win32timezone  -> inside the PYZ, embedded in the exe (pure Python: BYTES)

An earlier version of this script scanned only the executable.  It reported
"win32file: absent" for a bundle that plainly contained it, so its conditional
never fired and it would have passed the very build that crashed.  Both
locations are searched now, and the script is tested against that broken bundle.

What this does NOT prove: that the dialog opens.  It proves the module was
collected.  Real confirmation belongs on a real machine.
"""

import argparse
import sys
from pathlib import Path

# Türkçe çıktı Windows konsolunu ÖLDÜRMESİN. `run_tests.py` bu dersi uzun uzun
# anlatıyor: cp1252 konsol 'ğ'/'ş' kodlayamaz ve `print` UnicodeEncodeError
# fırlatır — bu script tam olarak öyle çökmüştü, kontrolü tamamladıktan SONRA.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

#: (parent module, module it imports lazily at call time).
LAZY_IMPORT_PAIRS = (
    ("win32file", "win32timezone"),
)

#: Uzantı modüllerinin dosya olarak göründüğü son ekler.
_EXTENSION_SUFFIXES = (".pyd", ".so", ".dll")


def _packaged_names(bundle_dir: Path):
    """Pakette bulunabilen modül adları: dosya adları + exe'nin ham baytları.

    Dönen ikili: (dosya adlarından gelen küme, exe baytları).
    """
    names = set()
    archives = []
    for path in bundle_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in _EXTENSION_SUFFIXES:
            # "win32file.pyd" ve "timezones.cp312-win_amd64.pyd" — ikisi de
            # ilk noktaya kadar olan kısımla adlandırılır.
            names.add(path.name.split(".")[0])
        elif suffix == ".exe":
            archives.append(path)
    return names, archives


def is_packaged(module: str, names, archives) -> bool:
    if module in names:
        return True
    needle = module.encode("ascii")
    return any(needle in archive.read_bytes() for archive in archives)


def missing_lazy_imports(bundle_dir, pairs=LAZY_IMPORT_PAIRS, report=None):
    """Return "parent -> companion" for each packaged parent missing its companion."""
    bundle_dir = Path(bundle_dir)
    names, archives = _packaged_names(bundle_dir)
    findings = []
    for parent, companion in pairs:
        parent_here = is_packaged(parent, names, archives)
        companion_here = is_packaged(companion, names, archives)
        if report is not None:
            report.append((parent, parent_here, companion, companion_here))
        if parent_here and not companion_here:
            findings.append(f"{parent} -> {companion}")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Frozen bundle lazy-import check")
    parser.add_argument("bundle", help="PyInstaller onedir bundle directory")
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"::error::Paket dizini bulunamadi: {bundle}")
        return 1

    report = []
    findings = missing_lazy_imports(bundle, report=report)
    for parent, parent_here, companion, companion_here in report:
        print(f"{parent}: {'var' if parent_here else 'yok'} | "
              f"{companion}: {'var' if companion_here else 'yok'}")

    for finding in findings:
        parent, companion = finding.split(" -> ")
        print(f"::error::{parent} paketlenmis ama cagri aninda import ettigi "
              f"{companion} eksik. O yol calistirildiginda uygulama "
              f"ModuleNotFoundError ile coker. archlence.spec icindeki "
              f"hiddenimports listesine {companion} eklenmeli.")
    if findings:
        return 1
    print("Tembel import butunlugu dogrulandi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
