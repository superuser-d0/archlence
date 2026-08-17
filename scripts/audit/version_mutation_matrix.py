#!/usr/bin/env python3
"""Sürüm/paketleme kapısını 16 mutation vakasıyla sınar.

Her vaka, ayrı bir detached `git worktree` içinde tek bir sürüm kaynağını
bozar, kapıyı çalıştırır ve `Detected` / `Escaped` sonucunu kaydeder. Ana
çalışma ağacına HİÇBİR mutation uygulanmaz.

Kullanım:

    python scripts/audit/version_mutation_matrix.py
    python scripts/audit/version_mutation_matrix.py --json /tmp/matrix.json

Çıkış kodu: kaçan vaka varsa 1, yoksa 0.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Türkçe çıktı Windows'ta süreci ÖLDÜRMESİN — stdout yönlendirildiğinde kod
# sayfası cp1252'ye düşüyor ve "yakalandı"nın 'ı'sı kodlanamıyor. Gerekçenin
# tamamı run_tests.py'ın tepesinde; ölçüldü: koruma olmadan 16/16 YAKALAYAN
# matris, yalnızca sonucu yazdırırken exit 1 ile kırmızı raporlanıyordu.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[2]

_APP_VERSION = re.compile(r'^APP_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


def _version_of(tree):
    """Sınanan AĞACIN sürümünü okur — bu betiğin kendi kopyasınınkini DEĞİL.

    NEDEN OKUNUYOR, NEDEN SABİT DEĞİL: altı vaka sürüm dizesinin kendisini
    arıyor (`pkgver=X`, `## [X]`, `ArchlenceSetup-X.exe` ...). Bunlar
    `0.0.8` olarak SABİT yazılmıştı ve v0.0.9 bump'ında matris sessizce
    bozuldu: üç vaka "uygulanamadı"ya düştü, üçü ise CHANGELOG'un TARİHSEL
    `## [0.0.8]` bölümünü mutasyona uğratıp "kaçtı" raporladı — kapı haklı
    olarak umursamadığı için. Yani matris her sürüm bump'ında kendi
    kendini geçersiz kılıyordu.

    `utils/version.py` import EDİLMEZ, ayrıştırılır: worktree'nin sürümü
    ana ağacınkinden farklı olabilir ve import bu süreçteki modülü döndürürdü.
    """
    text = (Path(tree) / "utils" / "version.py").read_text(encoding="utf-8")
    match = _APP_VERSION.search(text)
    if not match:
        raise SystemExit(f"utils/version.py içinde APP_VERSION bulunamadı: {tree}")
    return match.group(1)


# (id, açıklama, dosya, aranan, yerine konan)
# `None` yerine-konan => satırın tamamı silinir (kontrolün kaldırılması).
# `@@VERSION@@` sınanan ağacın sürümüyle değiştirilir (bkz. `_version_of`).
# Yer tutucu bilerek `{v}` DEĞİL: iki vaka workflow'daki gerçek `${v}`
# kabuk değişkenini arıyor ve `str.format` onları bozardı.
CASES = [
    ("01-app-version", "Uygulama sürümü",
     "utils/version.py", 'APP_VERSION = "', 'APP_VERSION = "9.9.9"  #'),
    ("02-installer-version", "Installer sürümü",
     "installer/archlence.iss", '#define MyAppVersion "@@VERSION@@"',
     '#define MyAppVersion "9.9.9"'),
    ("03-workflow-input-default", "Windows workflow input default",
     ".github/workflows/build-windows.yml", 'default: "@@VERSION@@"',
     'default: "9.9.9"'),
    ("04-workflow-fallback", "Sabit sürüm fallback'i geri getirildi",
     ".github/workflows/build-windows.yml",
     '          $version = "${{ inputs.version }}"',
     '          $version = "${{ inputs.version || \'0.0.1\' }}"'),
    ("05-pkgbuild-version", "Arch paket sürümü (Linux paketleme)",
     "PKGBUILD", "pkgver=@@VERSION@@", "pkgver=9.9.9"),
    ("06-appimage-filename", "AppImage release asset adı",
     ".github/workflows/release.yml", "Archlence-${v}-x86_64.AppImage",
     "Archlence-x86_64.AppImage"),
    ("07-changelog-latest", "CHANGELOG en son sürüm başlığı",
     "CHANGELOG.md", "## [@@VERSION@@]", "## [9.9.9]"),
    ("08-readme-marker", "README dinamik release rozeti",
     "README.md",
     "[![Latest release](https://img.shields.io/github/v/release/"
     "superuser-d0/archlence?include_prereleases)]"
     "(https://github.com/superuser-d0/archlence/releases/latest)",
     "[![Latest release](https://example.invalid/badge)](https://example.invalid)"),
    ("09-windows-asset-filename", "Windows release asset adı",
     "CHANGELOG.md", "ArchlenceSetup-@@VERSION@@.exe", "ArchlenceSetup.exe"),
    ("10-appimage-asset-in-notes", "AppImage adı (release notlarında)",
     "CHANGELOG.md", "Archlence-@@VERSION@@-x86_64.AppImage",
     "Archlence-x86_64.AppImage"),
    ("11-checksum-filename", "Checksum dosya adı",
     ".github/workflows/release.yml", "SHA256SUMS.txt", "CHECKSUMS.txt"),
    ("12-sbom-version", "SBOM dosya adı/sürümü",
     ".github/workflows/release.yml",
     "Archlence-${{ needs.version.outputs.version }}-sbom.cdx.json",
     "Archlence-sbom.cdx.json"),
    ("13-release-title", "Release başlığı",
     ".github/workflows/release.yml", '--title "Archlence v${v}"',
     '--title "Archlence"'),
    ("14-tag-mismatch-check", "Tag/uygulama eşleşme kontrolü kaldırıldı",
     ".github/workflows/release.yml",
     'echo "::error::Tag/input sürümü ($version) uygulama sürümüyle '
     '($expected) eşleşmiyor."',
     'echo "surum farkli ama devam"'),
    ("15-fixed-upgrade-baseline", "Upgrade tabanı sabit sürüme bağlandı",
     ".github/workflows/build-windows.yml", 'UPGRADE_BASELINE_TAG: ""',
     'UPGRADE_BASELINE_TAG: "v0.0.1"'),
    ("16-about-screen-binding", "About ekranı sürüm binding'i",
     "ui/dashboard.kv", 'text: "Archlence v" + app.version',
     'text: "Archlence"'),
]


def _run_gate(worktree):
    """Kapıyı çalıştırır; `(exit_code, output)` döner."""
    result = subprocess.run(
        [sys.executable, "scripts/check_version_consistency.py"],
        cwd=worktree, capture_output=True, text=True,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def _apply(worktree, relative, needle, replacement):
    path = Path(worktree) / relative
    text = path.read_text(encoding="utf-8")
    if text.count(needle) < 1:
        return False
    # HEPSİNİ değiştir. Yalnızca ilk eşleşmeyi değiştirmek yanlış "yakalandı"
    # sonucu üretir: dosyada aynı adın başka kopyaları kalırsa kapı onları
    # bulup yeşil kalır, oysa gerçek bir yeniden adlandırma hepsini
    # değiştirirdi.
    path.write_text(text.replace(needle, replacement), encoding="utf-8")
    return True


def run_matrix(verbose=True):
    results = []
    base = tempfile.mkdtemp(prefix="archlence-version-mut-")
    worktree = str(Path(base) / "wt")
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", worktree, "HEAD"],
        cwd=ROOT, check=True, capture_output=True,
    )
    try:
        # Mutation UYGULANMADAN kapı yeşil olmalı; değilse matris anlamsız.
        code, output = _run_gate(worktree)
        if code != 0:
            raise SystemExit(
                f"Temiz worktree'de kapı zaten kırmızı; matris geçersiz:\n{output}"
            )

        version = _version_of(worktree)
        for case_id, label, relative, needle, replacement in CASES:
            needle = needle.replace("@@VERSION@@", version)
            subprocess.run(
                ["git", "checkout", "--quiet", "--", "."],
                cwd=worktree, check=True,
            )
            applied = _apply(worktree, relative, needle, replacement)
            if not applied:
                results.append({
                    "id": case_id, "label": label, "file": relative,
                    "status": "NOT-APPLICABLE", "exit_code": None,
                    "message": f"desen bulunamadı: {needle[:60]!r}",
                })
                if verbose:
                    print(f"  {case_id:<28} UYGULANAMADI ({relative})")
                continue

            code, output = _run_gate(worktree)
            status = "Detected" if code != 0 else "ESCAPED"
            results.append({
                "id": case_id, "label": label, "file": relative,
                "status": status, "exit_code": code,
                "message": output.splitlines()[-1] if output else "",
            })
            if verbose:
                mark = "yakalandı" if status == "Detected" else "*** KAÇTI ***"
                print(f"  {case_id:<28} {mark:<16} exit={code}")
        subprocess.run(
            ["git", "checkout", "--quiet", "--", "."],
            cwd=worktree, check=True,
        )
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", worktree],
            cwd=ROOT, capture_output=True,
        )
        shutil.rmtree(base, ignore_errors=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sürüm kapısını 16 mutation vakasıyla sınar."
    )
    parser.add_argument("--json", help="Sonuçları bu dosyaya JSON olarak yaz.")
    args = parser.parse_args()

    print(f"Sürüm mutation matrisi — {len(CASES)} vaka\n")
    results = run_matrix()
    escaped = [r for r in results if r["status"] == "ESCAPED"]
    skipped = [r for r in results if r["status"] == "NOT-APPLICABLE"]

    print(f"\nyakalanan={len(results) - len(escaped) - len(skipped)} "
          f"kaçan={len(escaped)} uygulanamayan={len(skipped)}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON: {args.json}")
    return 1 if escaped or skipped else 0


if __name__ == "__main__":
    sys.exit(main())
