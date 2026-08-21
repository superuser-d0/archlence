"""Zorunlu CI kontrolleri ile workflow tanımı birbirinden ayrışmamalı.

NEDEN VAR: `main` dalının branch protection ayarı, zorunlu kontrolleri
İSİMLE listeler. Matris job'ları her kombinasyon için AYRI bir isim üretir
(`visual-regression (96, en)` gibi), dolayısıyla o dört isim ayrı ayrı
yazılıdır. Matris değişirse iki şeyden biri olur:

  - yeni bir kombinasyon eklenir ve zorunlu OLMAZ — kapı sessizce eksilir;
  - mevcut bir kombinasyon kalkar ve zorunlu tutulan isim HİÇ raporlanmaz —
    o zaman her PR "waiting for status" durumunda süresiz asılı kalır.

Aynı tuzak `if:` ve `continue-on-error` için de geçerli: zorunlu bir job
atlanırsa ya da hatayı yutarsa kapı ölçmeyi bırakır.

Bu dosya branch protection'ı UZAKTAN okuyamaz (testlerin ağa çıkmaması
gerekir). Bunun yerine beklenen listeyi burada sabitler: ayarı değiştirmek
isteyen bu testi de değiştirmek zorunda kalır, o da uzaktaki ayarı
güncellemesi gerektiğinin hatırlatıcısıdır.

Ayarı okumak için:
    gh api repos/superuser-d0/archlence/branches/main/protection \\
      --jq '.required_status_checks.contexts'

NEDEN `tests/` ALTINDA DEĞİL: bu dosya YAML ayrıştırıyor, yani PyYAML'a
ihtiyacı var. `test` job'ı bilerek yalnız `requirements-runtime.txt`
kuruyor (uygulamayı çalıştırıyor, geliştirme araçlarına ihtiyacı yok), o
yüzden `tests/` altındaki her şey RUNTIME bağımlılıklarıyla koşabilmeli.
Bu kontrol `reliability-gates` içinde koşuyor; orası `requirements.txt`
(runtime + dev) kuruyor ve o job da zorunlu bir status check.
"""

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


REQUIRED_CHECKS = {
    "build-windows": "build-windows.yml",
    "build-linux": "build-linux.yml",
    "test": "tests.yml",
    "test-windows": "tests.yml",
    "reliability-gates": "tests.yml",
    "lint": "tests.yml",
    "visual-regression (96, en)": "tests.yml",
    "visual-regression (192, en)": "tests.yml",
}


VISUAL_MATRIX = {"dpi": ["96", "192"], "language": ["en"]}


def _load(workflow):
    return yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))


def _triggers(document):

    return document.get("on", document.get(True, {}))


class RequiredChecksExistTest(unittest.TestCase):
    def test_every_required_check_maps_to_a_real_job(self):
        for context, workflow in REQUIRED_CHECKS.items():
            with self.subTest(context=context):
                jobs = _load(workflow)["jobs"]
                base = context.split(" (")[0]
                self.assertIn(
                    base, jobs,
                    f"{context!r} zorunlu tutuluyor ama {workflow} içinde "
                    f"{base!r} job'ı yok — bu isim hiç raporlanmaz ve PR'lar "
                    "süresiz beklemede kalır",
                )

    def test_required_jobs_run_on_pull_requests_to_main(self):
        """Zorunlu bir kontrol PR'da koşmuyorsa PR asla birleştirilemez."""
        for context, workflow in REQUIRED_CHECKS.items():
            with self.subTest(context=context):
                triggers = _triggers(_load(workflow))
                self.assertIn("pull_request", triggers, workflow)
                branches = (triggers["pull_request"] or {}).get("branches", [])
                self.assertIn("main", branches, workflow)

    def test_required_jobs_are_not_conditional_or_forgiving(self):
        """`if:` atlanmayı, `continue-on-error` yutmayı mümkün kılar."""
        for context, workflow in REQUIRED_CHECKS.items():
            with self.subTest(context=context):
                job = _load(workflow)["jobs"][context.split(" (")[0]]
                self.assertNotIn(
                    "if", job,
                    f"{context}: job düzeyinde `if` var — atlanan bir zorunlu "
                    "kontrol PR'ı süresiz bekletir",
                )
                self.assertNotIn(
                    "continue-on-error", job,
                    f"{context}: job `continue-on-error` taşıyor — zorunlu "
                    "olmasının anlamı kalmaz",
                )
                forgiving = [
                    step.get("name", "<isimsiz>")
                    for step in job.get("steps", [])
                    if step.get("continue-on-error")
                ]
                self.assertEqual(
                    forgiving, [],
                    f"{context}: şu adımlar hatayı yutuyor: {forgiving}",
                )


class VisualRegressionMatrixIsPinnedTest(unittest.TestCase):
    """Matris değişirse zorunlu kontrol listesi de değişmek ZORUNDA."""

    def test_matrix_matches_the_pinned_combinations(self):
        strategy = _load("tests.yml")["jobs"]["visual-regression"]["strategy"]
        self.assertEqual(
            strategy["matrix"], VISUAL_MATRIX,
            "visual-regression matrisi değişti. Zorunlu kontroller her "
            "kombinasyonu AYRI İSİMLE listeliyor; branch protection ayarını "
            "ve bu dosyadaki REQUIRED_CHECKS listesini birlikte güncelle.",
        )

    def test_pinned_matrix_produces_exactly_the_required_contexts(self):
        """İsimleri elle yazmak yerine matristen TÜRETİP karşılaştır."""
        produced = {
            f"visual-regression ({dpi}, {language})"
            for dpi in VISUAL_MATRIX["dpi"]
            for language in VISUAL_MATRIX["language"]
        }
        required = {
            context for context in REQUIRED_CHECKS
            if context.startswith("visual-regression")
        }
        self.assertEqual(
            produced, required,
            "matristen türeyen isimlerle zorunlu tutulanlar örtüşmüyor",
        )

    def test_matrix_does_not_stop_at_the_first_failure(self):
        """`fail-fast` açıkken bir kombinasyon diğerlerini iptal eder ve
        iptal edilen zorunlu kontrol raporlanmaz."""
        strategy = _load("tests.yml")["jobs"]["visual-regression"]["strategy"]
        self.assertIs(
            strategy.get("fail-fast"), False,
            "visual-regression için `fail-fast: false` şart: iptal edilen bir "
            "matris job'ı zorunlu kontrolü hiç raporlamaz",
        )


if __name__ == "__main__":
    unittest.main()
