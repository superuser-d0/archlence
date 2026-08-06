"""Inventory broad handlers and prevent new silent handlers in CI."""

import argparse
import ast
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# `AppDir` derleme çıktısıdır (.gitignore'da; build-linux.yml üretir) ve içinde
# KivyMD'nin KENDİ kaynağının kopyası bulunur. Taranırsa üçüncü parti
# handler'lar "yeni geniş handler" sayılıp kapıyı KIRAR — CI'da görünmez
# (temiz checkout), ama yerelde bir kez AppImage üreten geliştiricide kapı
# kapanır. Aynı gerekçe tests/test_icon_names.py::SKIP_DIRS için de geçerli.
SKIP = {".git", ".venv", "venv", "build", "dist", "AppDir"}


# Bir handler'ın ÜSTÜNDE ya da İÇİNDE bu işaret geçiyorsa, geniş bırakılması
# incelenmiş ve bilinçli olarak kabul edilmiş demektir. Gerekçe her zaman
# aynı satırdaki serbest metinde durur. İşaret CI kapısını GEVŞETMEZ:
# `--check` yalnızca parmak izi sayımına ve bare `except`'e bakar, sınıfa
# değil. Amacı, incelenmiş kararların "incelenmemiş borç" listesinde
# görünmeye devam etmesini önlemek.
AUDIT_MARKER = "EXCEPTION-AUDIT: bilinçli geniş"

_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def _logs(handler):
    """Handler gövdesinde bir logger çağrısı var mı.

    Eskiden `ast.dump` metninde "get_logger"/"logging" aranıyordu; bu, kod
    tabanının KENDİ yardımcılarını (`_log().error(...)`, modül düzeyindeki
    `logger.warning(...)`) göremiyor ve loglayan sınırları "daraltılması
    gerekli" kutusuna düşürüyordu. Artık çağrı biçimine bakılıyor.
    """
    for node in ast.walk(handler):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOG_METHODS
        ):
            return True
    return False


_BROAD_NAMES = {"Exception", "BaseException"}


def _broad_aliases(tree):
    """Modül içinde `Exception`/`BaseException`e verilmiş takma adları toplar.

    Kapı eskiden yalnızca `ast.Name` tanıyordu, dolayısıyla
    `Ex = Exception; except Ex:` gibi bir yeniden adlandırma tamamen
    görünmezdi (denetim bulgusu A-1).
    """
    aliases = set()
    for node in ast.walk(tree):
        # X = Exception
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            if node.value.id in _BROAD_NAMES | aliases:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases.add(target.id)
        # from builtins import Exception as X
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _BROAD_NAMES and alias.asname:
                    aliases.add(alias.asname)
    return aliases


def _is_broad(expr, aliases):
    """`except <expr>:` her şeyi yakalıyor mu.

    Tanınan biçimler: bare except, Name, Attribute (`builtins.Exception`),
    Tuple (`(Exception,)` ve `(Exception, OSError)` gibi karışık demetler —
    içinde geniş bir tip varsa demetin tamamı geniştir) ve takma adlar.
    """
    if expr is None:                       # bare except:
        return True
    if isinstance(expr, ast.Name):
        return expr.id in _BROAD_NAMES or expr.id in aliases
    if isinstance(expr, ast.Attribute):    # builtins.Exception
        return expr.attr in _BROAD_NAMES
    if isinstance(expr, ast.Tuple):
        return any(_is_broad(el, aliases) for el in expr.elts)
    return False


def _normalized_expression(expr):
    """Parmak izi için kararlı metin gösterimi."""
    if expr is None:
        return "bare"
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return f"{_normalized_expression(expr.value)}.{expr.attr}"
    if isinstance(expr, ast.Tuple):
        return "(" + ", ".join(
            _normalized_expression(el) for el in expr.elts
        ) + ")"
    return ast.dump(expr)


def classify(handler, source_lines=()):
    dumped = ast.dump(ast.Module(body=handler.body, type_ignores=[]))
    start = max(handler.lineno - 6, 1)
    end = handler.end_lineno or handler.lineno
    span = "\n".join(source_lines[start - 1:end])
    if AUDIT_MARKER in span:
        return "Bilinçli geniş; incelendi ve kabul edildi"
    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
        return "Kaldırılması veya loglanması gerekli"
    if any(isinstance(node, ast.Raise) for node in ast.walk(handler)):
        return "Yeniden fırlatılan sınır"
    if _logs(handler):
        return "Loglanan sınır"
    if "toast" in dumped or "schedule_once" in dumped:
        return "Kullanıcıya gösterilen; daraltılması incelenmeli"
    if "print" in dumped:
        return "Log sistemine taşınması gerekli"
    if any(
        isinstance(node, ast.Return)
        and isinstance(node.value, (ast.Constant, ast.List, ast.Dict))
        for node in ast.walk(handler)
    ):
        return "Fallback sonucu; veri bütünlüğü açısından incelenmeli"
    return "Daraltılması gerekli"


def inventory():
    findings = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP for part in path.parts):
            continue
        if "tests" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeError, SyntaxError):
            continue
        source_lines = source.splitlines()
        broad_aliases = _broad_aliases(tree)
        parents = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                parents.append(node.name)
                self.generic_visit(node)
                parents.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ExceptHandler(self, node):
                broad = _is_broad(node.type, broad_aliases)
                if broad:
                    # AST dumps are not a stable interchange format across
                    # Python minors (local 3.14 vs production CI 3.12 yielded
                    # different hashes for every existing handler). Identity
                    # therefore uses source location semantics, while Counter
                    # cardinality still detects a second broad handler in the
                    # same function.
                    identity = "|".join(
                        [
                            str(path.relative_to(ROOT)),
                            ".".join(parents) or "<module>",
                            _normalized_expression(node.type),
                        ]
                    )
                    findings.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line": node.lineno,
                            "function": ".".join(parents) or "<module>",
                            "kind": _normalized_expression(node.type),
                            "classification": classify(node, source_lines),
                            "fingerprint": hashlib.sha256(
                                identity.encode("utf-8")
                            ).hexdigest(),
                        }
                    )
                self.generic_visit(node)

        Visitor().visit(tree)
    return findings


def write_report(path, findings):
    grouped = collections.defaultdict(list)
    for finding in findings:
        grouped[finding["classification"]].append(finding)
    lines = [
        "# Exception handler denetimi",
        "",
        f"Toplam geniş/bare handler: {len(findings)}.",
        "",
        "Bu envanter mevcut teknik borcu görünür kılar. CI baseline’a göre "
        "yeni geniş handler eklenmesini engeller; mevcut kayıtlar aşamalı "
        "olarak daraltılacaktır.",
        "",
    ]
    for classification, items in sorted(grouped.items()):
        lines.extend([f"## {classification} ({len(items)})", ""])
        lines.extend(
            f"- `{item['path']}:{item['line']}` — `{item['function']}` "
            f"({item['kind']})"
            for item in items
        )
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline")
    parser.add_argument("--write-report")
    parser.add_argument("--check")
    args = parser.parse_args()
    findings = inventory()
    if args.write_baseline:
        Path(args.write_baseline).write_text(
            json.dumps(
                collections.Counter(
                    item["fingerprint"] for item in findings
                ),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    if args.write_report:
        write_report(args.write_report, findings)
    if args.check:
        baseline = collections.Counter(
            json.loads(Path(args.check).read_text(encoding="utf-8"))
        )
        current = collections.Counter(
            item["fingerprint"] for item in findings
        )
        # TAM EŞİTLİK. Eskiden yalnızca `current - baseline` (fazlalık)
        # kontrol ediliyordu, yani baseline'ın gerçekten FAZLA kayıt taşıması
        # hiçbir zaman hata üretmiyordu. Bu, v0.0.6'da bulunan 44 boş slotun
        # mekanizmasıydı ve kendiliğinden tekrar oluşabiliyordu: bir handler
        # DARALTILDIĞINDA (iyi bir değişiklik) baseline sessizce slack açıyor,
        # sonra aynı fonksiyona eklenen yeni bir geniş handler o boşluğa
        # sessizce yerleşiyordu (denetim bulgusu A-2).
        #
        # Artık azalma da hata. Handler daraltmak hâlâ doğru bir değişiklik;
        # yalnızca baseline'ın BİLİNÇLİ olarak yeniden üretilmesini istiyoruz.
        additions = current - baseline
        removals = baseline - current
        bare = [item for item in findings if item["kind"] == "bare"]
        if additions or removals or bare:
            print(
                f"Yeni geniş handler={sum(additions.values())}, "
                f"kaybolan (baseline slack)={sum(removals.values())}, "
                f"bare except={len(bare)}"
            )
            if removals:
                print(
                    "Baseline gerçekle uyuşmuyor. Handler daraltıldıysa veya "
                    "silindiyse baseline'ı bilinçli olarak yeniden üretin:\n"
                    "  python scripts/audit_exception_handlers.py "
                    "--write-baseline .github/exception-baseline.json"
                )
            raise SystemExit(1)
        print(f"Exception baseline korundu: {len(findings)} handler")


if __name__ == "__main__":
    main()
