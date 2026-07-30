"""Inventory broad handlers and prevent new silent handlers in CI."""

import argparse
import ast
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "venv", "build", "dist"}


def classify(handler):
    dumped = ast.dump(ast.Module(body=handler.body, type_ignores=[]))
    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
        return "Kaldırılması veya loglanması gerekli"
    if any(isinstance(node, ast.Raise) for node in ast.walk(handler)):
        return "Yeniden fırlatılan sınır"
    if "get_logger" in dumped or "logging" in dumped:
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
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        parents = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                parents.append(node.name)
                self.generic_visit(node)
                parents.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ExceptHandler(self, node):
                broad = node.type is None or (
                    isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                )
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
                            "bare" if node.type is None else node.type.id,
                        ]
                    )
                    findings.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line": node.lineno,
                            "function": ".".join(parents) or "<module>",
                            "kind": (
                                "bare"
                                if node.type is None
                                else node.type.id
                            ),
                            "classification": classify(node),
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
        additions = current - baseline
        bare = [item for item in findings if item["kind"] == "bare"]
        if additions or bare:
            print(
                f"Yeni geniş handler={sum(additions.values())}, "
                f"bare except={len(bare)}"
            )
            raise SystemExit(1)
        print(f"Exception baseline korundu: {len(findings)} handler")


if __name__ == "__main__":
    main()
