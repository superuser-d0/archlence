"""Çeviri fonksiyonlarına DİNAMİK metin verilmesini yasaklayan kalıcı kapı.

NEDEN VAR: kusur tek bir hatalı satır değil, bir ALIŞKANLIKTI — çağıran
f-string'i önce kuruyor, sonra çeviriye veriyordu. `tr()` alt dize
değiştirmeyi bıraktığı için artık kullanıcı verisi bozulmuyor; ama dinamik
metin çeviriye verilmeye devam ederse cümle SESSİZCE çevrilmemiş kalır
(sözlükte tam karşılığı olmayan bir metin kaynağa döner). İki kusur da aynı
kökten geliyor: parametrelerin çeviriden ÖNCE metne gömülmesi.

Bu paket üç şeyi birden sabitler:

  1. `_t(f"...")`, `translate(f"...")`, `app.tr(f"...")`, `"a" + b` ve
     `"%s" % x` sonuçları çeviri fonksiyonlarına VERİLEMEZ,
  2. kod tabanındaki HER `trf` şablonu EN sözlüğünde vardır ve iki dilin
     yer tutucu KÜMESİ aynıdır,
  3. her şablon gerçekten render edilebilir (eksik/fazla parametre yok).

Muafiyet listesi DAR ve GEREKÇELİDİR; "şimdilik" muafiyeti yoktur —
dinamik bir çağrının doğru çözümü parametreli yardımcıya geçmektir.
"""

import ast
import os
import re
import sys
import unittest
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "venv", "build", "dist", ".git", "AppDir", "__pycache__",
             ".mypy_cache", ".hypothesis", "node_modules"}

#: Çeviri yapan adlar. `_t`/`translate` `ui.i18n.tr`nin takma adları;
#: `app.tr`/`self.tr` da aynı fonksiyona iner.
TRANSLATION_NAMES = {"tr", "translate", "_t"}
TRANSLATION_ATTRS = {"tr", "translate"}

#: Şablon yardımcıları — dinamik ARGÜMAN almazlar, şablon SABİT olmalıdır.
TEMPLATE_HELPERS = {"trf", "_tf", "translate_format"}

#: DAR ve gerekçeli muafiyetler: (dosya, satırdaki fonksiyon/anahtar).
#:
#: Yalnız "çeviri fonksiyonunun KENDİSİNİ sınayan" test altyapısı muaf;
#: üretim kodunda muafiyet YOKTUR.
ALLOWLIST = {
    # Kapının kendisi: yasak deseni ÜRETİP yakalandığını doğruluyor.
    "tests/test_i18n_static_gate.py",
    # Çeviri motorunun birim testleri bilerek dinamik girdi üretir.
    "tests/test_i18n.py",
    "tests/test_i18n_user_data.py",
    "tests/test_chart_localization.py",
}


def python_files():
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def relative(path):
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def is_translation_call(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in TRANSLATION_NAMES
    if isinstance(func, ast.Attribute):
        return func.attr in TRANSLATION_ATTRS
    return False


def is_template_helper(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in TEMPLATE_HELPERS
    if isinstance(func, ast.Attribute):
        return func.attr in TEMPLATE_HELPERS
    return False


def dynamic_kind(argument):
    """Argüman "derleme zamanında sabit metin" DEĞİLSE nedenini döndürür."""
    if isinstance(argument, ast.JoinedStr):
        return "f-string"
    if isinstance(argument, ast.BinOp):
        if isinstance(argument.op, ast.Add):
            return "string birleştirme"
        if isinstance(argument.op, ast.Mod):
            return "%-formatlama"
        return "aritmetik ifade"
    if isinstance(argument, ast.Call):
        func = argument.func
        if isinstance(func, ast.Attribute) and func.attr in ("format", "join"):
            return f"str.{func.attr}()"
    return None


class NoDynamicTextReachesTheTranslatorTest(unittest.TestCase):
    def test_no_dynamic_expression_is_passed_to_a_translation_function(self):
        offenders = []
        for path in python_files():
            name = relative(path)
            if name in ALLOWLIST:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                if not is_translation_call(node):
                    continue
                kind = dynamic_kind(node.args[0])
                if kind:
                    offenders.append(f"{name}:{node.lineno} — {kind}")

        self.assertEqual(
            offenders, [],
            "Çeviri fonksiyonuna dinamik metin veriliyor. Doğru çözüm "
            "muafiyet değil, parametreli yardımcıdır:\n"
            "    _tf(\"{name} aboneliği durduruldu.\", name=payment['name'])\n"
            + "\n".join(offenders),
        )

    def test_template_helpers_only_receive_constant_templates(self):
        """`trf`nin ŞABLONU da sabit olmalı — yoksa sözlükte aranamaz."""
        offenders = []
        for path in python_files():
            name = relative(path)
            if name in ALLOWLIST:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                if not is_template_helper(node):
                    continue
                template = node.args[0]
                if not (isinstance(template, ast.Constant)
                        and isinstance(template.value, str)):
                    offenders.append(f"{name}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_the_gate_actually_catches_the_forbidden_shapes(self):
        """Kapının DİŞLERİ var mı — yasak desenler gerçekten yakalanıyor mu."""
        samples = {
            'f-string': 'toast(_t(f"{name} eklendi"))',
            'string birleştirme': 'toast(_t("Hata: " + detail))',
            '%-formatlama': 'toast(_t("Hata: %s" % detail))',
            'str.format()': 'toast(_t("Hata: {}".format(detail)))',
        }
        for expected, source in samples.items():
            with self.subTest(shape=expected):
                tree = ast.parse(source)
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and is_translation_call(node)
                ]
                self.assertEqual(len(calls), 1, source)
                self.assertEqual(dynamic_kind(calls[0].args[0]), expected)

    def test_a_static_call_is_not_flagged(self):
        tree = ast.parse('toast(_t("Hesap eklendi."))')
        call = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and is_translation_call(node)
        )
        self.assertIsNone(dynamic_kind(call.args[0]))


class KvFilesOnlyTranslateLiteralsTest(unittest.TestCase):
    """KV tarafı da aynı sözleşmeye tabi.

    `ui/dashboard.kv` içinde 139 `app.tr(...)` çağrısı var. Hepsi düz metin
    literaliyle çağrılıyor ve öyle KALMALI: KV'de bir f-string ya da
    birleştirme kurulup çeviriye verilirse, Python tarafında kapattığımız
    kapı KV'den yeniden açılır.
    """

    #: `app.tr("...")` — çift ya da tek tırnakla başlayan literal.
    LITERAL_CALL = re.compile(r"""app\.tr\(\s*["']""")
    ANY_CALL = re.compile(r"app\.tr\(")

    def test_every_kv_translation_call_starts_with_a_string_literal(self):
        offenders = []
        for path in sorted(PROJECT_ROOT.rglob("*.kv")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for match in self.ANY_CALL.finditer(line):
                    tail = line[match.start():]
                    if not self.LITERAL_CALL.match(tail):
                        offenders.append(
                            f"{relative(path)}:{number} — {line.strip()[:70]}"
                        )
        self.assertEqual(
            offenders, [],
            "KV'de çeviriye literal olmayan bir ifade veriliyor:\n"
            + "\n".join(offenders),
        )

    def test_the_kv_check_has_teeth(self):
        self.assertIsNone(self.LITERAL_CALL.match('app.tr(root.name)'))
        self.assertIsNotNone(self.LITERAL_CALL.match('app.tr("Hesaplar")'))


def collect_templates():
    """Kod tabanındaki her `trf` şablonu ve kullanıldığı yerler."""
    templates = {}
    for path in python_files():
        name = relative(path)
        if name in ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if not is_template_helper(node):
                continue
            template = node.args[0]
            if isinstance(template, ast.Constant) and isinstance(template.value, str):
                templates.setdefault(template.value, []).append(
                    f"{name}:{node.lineno}"
                )
    return templates


class TemplateCatalogueTest(unittest.TestCase):
    def test_every_template_has_an_english_entry(self):
        from ui.i18n import EN

        missing = sorted(set(collect_templates()) - set(EN))
        self.assertEqual(
            missing, [],
            "Bu şablonların İngilizce karşılığı yok; kullanıcı İngilizce "
            "arayüzde Türkçe cümle görür:\n" + "\n".join(map(repr, missing)),
        )

    def test_placeholder_sets_match_between_turkish_and_english(self):
        """Yer tutucu KÜMESİ aynı olmalı; SIRA serbesttir.

        Eksik yer tutucu değeri sessizce yutar, fazlası ise render sırasında
        `TranslationTemplateError` fırlatır. İkisi de kullanıcıya bozuk cümle
        gösterir; kapı ikisini de burada yakalar.
        """
        from ui.i18n import EN, placeholders

        mismatched = []
        for source, english in EN.items():
            if placeholders(source) != placeholders(english):
                mismatched.append(
                    f"{source!r}: TR={sorted(placeholders(source))} "
                    f"EN={sorted(placeholders(english))}"
                )
        self.assertEqual(mismatched, [], "\n".join(mismatched))

    def test_every_template_renders_in_both_languages(self):
        """Her şablon gerçekten render edilebiliyor mu (eksik/fazla parametre).

        Bu, `trf`nin `TranslationTemplateError` fırlatmasını üretimde ilk kez
        görmeyi imkânsız kılar: bütün şablonlar burada, kukla değerlerle
        çalıştırılıyor.
        """
        from ui.i18n import placeholders, trf

        for template in sorted(collect_templates()):
            params = {name: "X" for name in placeholders(template)}
            for language in ("tr", "en"):
                with self.subTest(template=template, language=language):
                    rendered = trf(template, language=language, **params)
                    self.assertNotIn("{", rendered.replace("{X}", ""))

    def test_a_template_placeholder_never_leaks_into_the_output(self):
        from ui.i18n import EN, placeholders, trf

        for source in EN:
            names = placeholders(source)
            if not names:
                continue
            rendered = trf(source, language="en",
                           **{name: f"<{name}>" for name in names})
            for name in names:
                self.assertIn(f"<{name}>", rendered)


class UserDataNeverReachesTheTranslatorTest(unittest.TestCase):
    """Kullanıcının VERDİĞİ ad çeviriye giremez — kaynak seviyesinde.

    Davranış testi bunu tek başına yakalayamaz: `tr()` artık tam eşleşme
    yaptığı için çoğu ad zaten değişmeden döner. Ama sözlükte AYNI anahtar
    varsa ("Nakit", "Ayarlar", "Gelir") ad YİNE çevrilir. O yüzden çağrının
    kendisi yasak.

    Kontrol METİN ARAMA değil AST: docstring'de geçen `_t(acc["name"])`
    örneği (kusurun anlatıldığı yer) yanlış pozitif üretiyordu.
    """

    #: Kullanıcının kendi yazdığı alanlar. `type_label`, `category`,
    #: `asset_type` BİLEREK yok: onlar uygulamanın kendi etiket sözlüğü.
    USER_FIELDS = {
        "name", "goal_name", "debt_name", "account_name", "description",
        "card_name", "asset_name",
    }

    def _user_field(self, argument):
        """İfade bir kullanıcı alanını okuyor mu?"""
        if isinstance(argument, ast.Subscript):
            key = argument.slice
            if isinstance(key, ast.Constant) and key.value in self.USER_FIELDS:
                return str(key.value)
        if isinstance(argument, ast.Call):
            func = argument.func
            if (isinstance(func, ast.Attribute) and func.attr == "get"
                    and argument.args):
                first = argument.args[0]
                if (isinstance(first, ast.Constant)
                        and first.value in self.USER_FIELDS):
                    return str(first.value)
        if isinstance(argument, ast.Attribute):
            if argument.attr in self.USER_FIELDS:
                return argument.attr
        return None

    def test_no_module_translates_a_user_supplied_name(self):
        offenders = []
        for path in python_files():
            name = relative(path)
            if name.startswith("tests/"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                if not is_translation_call(node):
                    continue
                field = self._user_field(node.args[0])
                if field:
                    offenders.append(f"{name}:{node.lineno} — {field}")
        self.assertEqual(
            offenders, [],
            "Kullanıcının verdiği ad çeviri fonksiyonuna giriyor:\n"
            + "\n".join(offenders),
        )

    def test_the_user_field_check_has_teeth(self):
        tree = ast.parse('label = _t(acc["name"])')
        call = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and is_translation_call(node))
        self.assertEqual(self._user_field(call.args[0]), "name")

    def test_enum_labels_are_still_allowed(self):
        """Tür etiketi bir ENUM: çevrilmesi doğru, kapı onu engellememeli."""
        tree = ast.parse('label = _t(acc["type_label"])')
        call = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and is_translation_call(node))
        self.assertIsNone(self._user_field(call.args[0]))


if __name__ == "__main__":
    unittest.main()
