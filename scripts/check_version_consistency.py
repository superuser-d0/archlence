"""Fail release builds when packaging metadata or release-facing docs drift."""

import re
import sys
from pathlib import Path

# Konsol kodlaması: bu kapının Türkçe çıktısı süreci ÖLDÜRMESİN.
# Windows'ta stdout yönlendirildiğinde (dosya, pipe, CI log) kod sayfası
# cp1252'ye düşüyor ve 'ı' karakteri KODLANAMIYOR. Ölçüldü: sürüm kontrolü
# TAMAMEN GEÇTİĞİ hâlde, son satırdaki "Sürüm tutarlı: ..." mesajı
# UnicodeEncodeError fırlatıp scripti **exit 1** ile düşürüyordu — yani
# yeşil bir kapı kırmızı raporlanıyordu. CI'da görülmedi çünkü bu adım
# `ubuntu-latest`'ta koşuyor; Windows'tan elle yayın adımı koşturan
# herkesi vururdu. Aynı koruma run_tests.py'ın tepesinde de var (oradaki
# uzun gerekçeye bakın).
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
        raise SystemExit(f"{description} eksik veya geçersiz: {path}")


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
        r"\[!\[Latest release\]\(https://img\.shields\.io/github/v/release/"
        r"superuser-d0/archlence\?include_prereleases\)\]"
        r"\(https://github\.com/superuser-d0/archlence/releases/latest\)",
        "README.md",
        "README dinamik pre-release rozeti",
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
    # Aşağıdakiler kapının DENETLEMEDİĞİ boşluklardı; 16 vakalık mutation
    # matrisi (scripts/audit/version_mutation_matrix.py) bunları kaçırdığını
    # gösterdi.
    require(
        r'Archlence-\$\{v\}-x86_64\.AppImage',
        ".github/workflows/release.yml",
        "AppImage release asset adı",
    )
    require(
        r'SHA256SUMS\.txt',
        ".github/workflows/release.yml",
        "Checksum dosya adı",
    )
    require(
        r'Archlence-\$\{\{ needs\.version\.outputs\.version \}\}-sbom\.cdx\.json',
        ".github/workflows/release.yml",
        "SBOM dosya adı",
    )
    # Tag/uygulama sürümü uyuşmazlığını release.yml'in KENDİSİ yakalamalı.
    # Bu kontrolün varlığını doğruluyoruz: silinirse yanlış etiketle yayın
    # yapılabilir hale gelir.
    require(
        r'Tag/input sürümü .* uygulama sürümüyle .* eşleşmiyor',
        ".github/workflows/release.yml",
        "Tag/uygulama sürüm eşleşme kontrolü",
    )
    # Windows workflow'unda SABİT sürüm fallback'i OLMAMALI. Eskiden
    # `inputs.version || '0.0.1'` her normal derlemeyi 0.0.1 damgalıyordu.
    windows = (ROOT / ".github/workflows/build-windows.yml").read_text(
        encoding="utf-8"
    )
    # Yorum satırları HARİÇ: düzeltmeyi anlatan yorum metni eşleşmemeli.
    windows_code = "\n".join(
        line for line in windows.splitlines()
        if not line.lstrip().startswith("#")
    )
    if re.search(r"inputs\.version\s*\|\|\s*'[0-9]", windows_code):
        raise SystemExit(
            "Windows workflow'unda sabit sürüm fallback'i var: "
            ".github/workflows/build-windows.yml"
        )
    # Upgrade smoke tabanı SABİT bir sürüme bağlı OLMAMALI.
    if re.search(r'UPGRADE_BASELINE_TAG:\s*"v[0-9]', windows_code):
        raise SystemExit(
            "Upgrade smoke tabanı sabit bir sürüme bağlı: "
            ".github/workflows/build-windows.yml"
        )
    print(f"Sürüm tutarlı: {APP_VERSION} / tag v{APP_VERSION}")


if __name__ == "__main__":
    main()
