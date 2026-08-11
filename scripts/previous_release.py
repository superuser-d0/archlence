#!/usr/bin/env python3
"""Bir hedef sürüm için GERÇEK önceki yayını seçer.

NEDEN VAR: `build-windows.yml` upgrade smoke testi sabit `v0.0.1` kullanıyordu.
Bu, "önceki sürümden yükseltme" iddiasını doğrulamıyordu — v0.0.8'den v0.0.9'a
yükseltme yolu hiç sınanmıyor, bunun yerine sekiz sürüm eskisi test ediliyordu.
Kullanıcıların gerçekte izlediği yol test edilmemiş kalıyordu.

Kullanım:

    python scripts/previous_release.py --target 0.0.9 --tags v0.0.8 v0.0.7 ...

`--tags` verilmezse `git tag` çıktısı kullanılır.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# `v` öneki isteğe bağlı; prerelease son eki (`-rc1`) ayrı yakalanır.
_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def parse_version(tag):
    """`(major, minor, patch, prerelease)` döner; tanınmazsa `None`.

    Tanınmayan etiket ATLANIR, hata değildir: depoda `backup/pre-split-2139`
    gibi sürüm olmayan etiketler var ve bunlar seçimi bozmamalı.
    """
    match = _TAG.match(tag.strip())
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return int(major), int(minor), int(patch), pre


def _sort_key(parsed):
    """Semver sırası: prerelease, aynı sayıdaki stable'dan ÖNCE gelir."""
    major, minor, patch, pre = parsed
    # `pre is None` -> stable -> 1 (sonra gelir); prerelease -> 0.
    return (major, minor, patch, 1 if pre is None else 0, pre or "")


def select_previous(target, tags, *, allow_prerelease=False):
    """Hedeften kesin olarak KÜÇÜK en büyük sürümü döner.

    Kurallar:
      * hedefin kendisi asla seçilmez;
      * tanınmayan etiketler atlanır;
      * yinelenen etiketler tekilleştirilir;
      * `allow_prerelease` false ise prerelease'ler aday değildir;
      * uygun aday yoksa `LookupError` — sessiz bir varsayılana DÜŞÜLMEZ.
    """
    target_parsed = parse_version(target)
    if target_parsed is None:
        raise ValueError(f"Geçersiz hedef sürüm: {target!r}")
    target_key = _sort_key(target_parsed)

    candidates = {}
    for tag in tags:
        parsed = parse_version(tag)
        if parsed is None:
            continue
        if parsed[3] is not None and not allow_prerelease:
            continue
        key = _sort_key(parsed)
        if key >= target_key:          # hedefin kendisi ve sonrası eleniyor
            continue
        candidates[key] = tag.strip()

    if not candidates:
        raise LookupError(
            f"{target} için önceki yayın bulunamadı; "
            "upgrade smoke testi sabit bir sürüme düşmemeli."
        )
    return candidates[max(candidates)]


def _git_tags():
    result = subprocess.run(
        ["git", "tag"], capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hedef sürüm için gerçek önceki yayını seçer.",
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--tags", nargs="*", default=None)
    parser.add_argument("--allow-prerelease", action="store_true")
    args = parser.parse_args()

    tags = args.tags if args.tags is not None else _git_tags()
    try:
        print(select_previous(
            args.target, tags, allow_prerelease=args.allow_prerelease
        ))
    except (LookupError, ValueError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
