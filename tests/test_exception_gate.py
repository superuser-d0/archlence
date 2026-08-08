"""İstisna kalite kapısının kendi testleri.

Denetim bulguları A-1 ve A-2. Kapı, projenin geniş-handler borcunu
büyütmeme sözünün TEK mekanizmasıydı ve kendisi hiç test edilmiyordu.

A-1: tespit yalnızca `ast.Name` tanıyordu. `except (Exception,)`,
`except (Exception, OSError)`, `except builtins.Exception` ve takma adlar
tamamen görünmezdi — üçü de işlevsel olarak `except Exception:` ile aynı.

A-2: kapı yalnızca `current - baseline` (fazlalık) bakıyordu. Bir handler
DARALTILDIĞINDA baseline sessizce slack açıyor, sonra aynı fonksiyona eklenen
yeni geniş handler o boşluğa sessizce yerleşiyordu.
"""

import ast
import importlib.util
import json
import unittest
from pathlib import Path

_GATE = Path(__file__).resolve().parents[1] / "scripts" / "audit_exception_handlers.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("_gate", _GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def _broad(source):
    """Kaynaktaki `except` ifadesi kapı tarafından geniş sayılıyor mu."""
    tree = ast.parse(source)
    aliases = gate._broad_aliases(tree)
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert handlers, "test kaynağında except handler yok"
    return [gate._is_broad(h.type, aliases) for h in handlers]


class BroadHandlerDetectionTest(unittest.TestCase):
    """A-1: bütün eşdeğer biçimler tanınmalı."""

    def test_plain_exception(self):
        self.assertEqual(_broad("try:\n pass\nexcept Exception:\n pass"), [True])

    def test_base_exception(self):
        self.assertEqual(
            _broad("try:\n pass\nexcept BaseException:\n pass"), [True]
        )

    def test_bare_except(self):
        self.assertEqual(_broad("try:\n pass\nexcept:\n pass"), [True])

    def test_single_element_tuple(self):
        self.assertEqual(
            _broad("try:\n pass\nexcept (Exception,):\n pass"), [True]
        )

    def test_mixed_tuple_containing_exception(self):
        self.assertEqual(
            _broad("try:\n pass\nexcept (OSError, Exception):\n pass"), [True]
        )

    def test_attribute_form(self):
        self.assertEqual(
            _broad("import builtins\ntry:\n pass\n"
                   "except builtins.Exception:\n pass"), [True]
        )

    def test_module_level_alias(self):
        self.assertEqual(
            _broad("Ex = Exception\ntry:\n pass\nexcept Ex:\n pass"), [True]
        )

    def test_chained_alias(self):
        self.assertEqual(
            _broad("A = Exception\nB = A\ntry:\n pass\nexcept B:\n pass"),
            [True],
        )

    def test_import_alias(self):
        self.assertEqual(
            _broad("from builtins import Exception as Boom\n"
                   "try:\n pass\nexcept Boom:\n pass"), [True]
        )

    def test_multiline_tuple(self):
        self.assertEqual(
            _broad("try:\n pass\nexcept (\n    OSError,\n"
                   "    Exception,\n):\n pass"), [True]
        )

    # ── Dar handler'lar geniş SAYILMAMALI (yanlış pozitif olmasın) ────────

    def test_narrow_handlers_are_not_broad(self):
        self.assertEqual(
            _broad("try:\n pass\nexcept ValueError:\n pass"), [False]
        )
        self.assertEqual(
            _broad("try:\n pass\nexcept (ValueError, TypeError):\n pass"),
            [False],
        )
        self.assertEqual(
            _broad("import sqlite3\ntry:\n pass\n"
                   "except sqlite3.Error:\n pass"), [False]
        )


class BaselineComparisonTest(unittest.TestCase):
    """A-2: fazlalık DA eksiklik DE kırmızı olmalı."""

    def _check(self, current_counts, baseline_counts):
        """`main()` karşılaştırma mantığını taklit eder."""
        import collections

        current = collections.Counter(current_counts)
        baseline = collections.Counter(baseline_counts)
        additions = current - baseline
        removals = baseline - current
        return bool(additions), bool(removals)

    def test_identical_inventories_pass(self):
        self.assertEqual(self._check({"a": 1}, {"a": 1}), (False, False))

    def test_new_handler_is_caught(self):
        added, removed = self._check({"a": 1, "b": 1}, {"a": 1})
        self.assertTrue(added)

    def test_second_handler_in_same_scope_is_caught(self):
        added, _ = self._check({"a": 2}, {"a": 1})
        self.assertTrue(added, "aynı fonksiyona ikinci handler yakalanmadı")

    def test_narrowed_handler_is_caught_as_slack(self):
        """Daraltma iyi bir değişiklik ama baseline güncellenmeli."""
        _, removed = self._check({"a": 1}, {"a": 2})
        self.assertTrue(removed, "baseline slack'i yakalanmadı")

    def test_removed_handler_is_caught_as_slack(self):
        _, removed = self._check({}, {"a": 1})
        self.assertTrue(removed)

    def test_moved_handler_is_caught_both_ways(self):
        """Taşıma: eski parmak izi kaybolur, yenisi belirir."""
        added, removed = self._check({"b": 1}, {"a": 1})
        self.assertTrue(added)
        self.assertTrue(removed)


class GateIntegrationTest(unittest.TestCase):
    """Gerçek envanter üretimi çalışıyor ve baseline'la eşleşiyor mu."""

    def test_repository_inventory_matches_the_reviewed_baseline(self):
        import collections

        findings = gate.inventory()
        current = collections.Counter(f["fingerprint"] for f in findings)
        baseline_path = (
            Path(__file__).resolve().parents[1]
            / ".github" / "exception-baseline.json"
        )
        baseline = collections.Counter(
            json.loads(baseline_path.read_text(encoding="utf-8"))
        )
        self.assertEqual(
            current, baseline,
            "envanter baseline ile birebir eşleşmiyor",
        )

    def test_no_bare_except_in_the_repository(self):
        findings = gate.inventory()
        bare = [f for f in findings if f["kind"] == "bare"]
        self.assertEqual(bare, [], f"bare except bulundu: {bare}")


if __name__ == "__main__":
    unittest.main()
