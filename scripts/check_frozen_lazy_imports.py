"""Fail Windows packaging when a lazily imported companion module is absent.

PyInstaller resolves imports statically.  A module that is imported *inside a
function body at call time* is therefore invisible to it, and the resulting
package looks complete right up to the moment the user reaches that code path.

This happened: Kivy's file chooser calls ``win32file.GetFileAttributesExW`` to
read the hidden-file flag, and pywin32 imports ``win32timezone`` from inside
that call.  ``win32file`` was packaged, ``win32timezone`` was not, and opening
the restore dialog terminated the whole application on a real Windows 11
machine ("No module named 'win32timezone'").

The invariant checked here is deliberately CONDITIONAL: the companion is only
required when its parent is actually present.  A build environment without
pywin32 packages neither, and that is correct rather than broken — Kivy falls
back to skipping the hidden-file check when ``win32file`` cannot be imported.

What this does NOT prove: that the dialog opens.  It proves the module name is
present in the frozen archive.  Real confirmation belongs on a real machine.
"""

import argparse
import sys
from pathlib import Path

#: (parent module, module it imports lazily at call time).
LAZY_IMPORT_PAIRS = (
    ("win32file", "win32timezone"),
)


def missing_lazy_imports(data: bytes, pairs=LAZY_IMPORT_PAIRS):
    """Return "parent -> companion" for every packaged parent missing its companion.

    Module names appear as plain bytes in PyInstaller's archive table of
    contents, so a substring search over the frozen executable is enough to
    tell whether a module was collected.
    """
    findings = []
    for parent, companion in pairs:
        if parent.encode("ascii") in data and companion.encode("ascii") not in data:
            findings.append(f"{parent} -> {companion}")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", help="Frozen executable to inspect")
    args = parser.parse_args(argv)

    path = Path(args.executable)
    if not path.is_file():
        print(f"::error::Paketlenmiş dosya bulunamadı: {path}")
        return 1

    data = path.read_bytes()
    for parent, companion in LAZY_IMPORT_PAIRS:
        print(f"{parent}: {'var' if parent.encode() in data else 'yok'} · "
              f"{companion}: {'var' if companion.encode() in data else 'yok'}")

    findings = missing_lazy_imports(data)
    for finding in findings:
        parent, companion = finding.split(" -> ")
        print(f"::error::{parent} paketlenmiş ama çağrı anında import ettiği "
              f"{companion} eksik. Bu yol çalıştırıldığında uygulama "
              f"ModuleNotFoundError ile çöker. archlence.spec içindeki "
              f"hiddenimports listesine {companion} eklenmeli.")
    if findings:
        return 1
    print("Tembel import bütünlüğü doğrulandı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
