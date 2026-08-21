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


TRANSLATION_NAMES = {"tr", "translate", "_t"}
TRANSLATION_ATTRS = {"tr", "translate"}


TEMPLATE_HELPERS = {"trf", "_tf", "translate_format"}


ALLOWLIST = {

    "tests/test_i18n_static_gate.py",

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


def controlled_sources_in_expression(node, declared):
    """İfadede OKUNAN (Load bağlamı) beyan edilmiş kontrollü kaynaklar.

    `Store` bağlamı bilerek dışarıda: `_OLU = 1` bir KULLANIM değil, bir
    tanımdır. Eski ölçüm bunu ayırmıyordu ve yalnız atanan bir ad kendini
    canlı gösterebiliyordu.
    """
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            identifier = sub.id
        elif isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load):
            identifier = sub.attr
        else:
            continue
        if identifier in declared:
            found.add(identifier)
    return found


def controlled_sources_in_template_parameters(tree, declared):
    """YALNIZ `trf`/`_tf`/`translate_format` KEYWORD ifadelerinde geçenler.

    Sözleşmenin iddiası "bu ad kod tabanında bir yerde geçiyor" DEĞİL,
    "bu ad şablon parametresine giriyor ve bu yüzden kapı onu koruyor".
    Ölçüm bu yüzden şablon çağrılarıyla sınırlı.

    Bu daraltma iki eski açığı birden kapatır:
      * sözleşmenin KENDİ TANIMI artık kendiliğinden dışarıda — bir
        `frozenset` literali şablon parametresi değildir; ayrıca girdiler
        string sabiti olduğu için `Name`/`Attribute` de üretmezler,
      * yorum, docstring ve string literalleri AST'de tanımlayıcı değildir.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not is_template_helper(node):
            continue
        for keyword in node.keywords:
            found |= controlled_sources_in_expression(keyword.value, declared)
    return found


def unused_label_sources(names):
    """Beyan edilip ŞABLON PARAMETRESİNDE hiç görülmeyen kaynaklar.

    `declared - sources_seen_in_template_parameters`.
    """
    declared = set(names)
    seen = set()
    for path in python_files():
        if relative(path).startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen |= controlled_sources_in_template_parameters(tree, declared)
    return sorted(declared - seen)


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


class ControlledValuesReachTheTranslatorTest(unittest.TestCase):
    """Kontrollü Türkçe etiket, şablona HAM giremez.

    ÖLÇÜLEN KUSUR: `trf()` sözleşmesi doğruydu ama üretim çağrıları enum
    değerini ham veriyordu — "Select Type: Hisse", "Add New Altın",
    "Gold Type: Gram Altın", "Type: Döviz".

    OTOMATİK SINIFLANDIRMA GÜVENİLİR DEĞİL: bir ifadenin kullanıcı verisi mi
    yoksa etiket mi olduğu kaynağa bakmadan bilinemez. O yüzden kapı TAHMİN
    ETMİYOR, AÇIK BİR SÖZLEŞME uyguluyor: bilinen etiket KAYNAKLARI
    (`ui.i18n.CONTROLLED_LABEL_SOURCES`) `trf` parametresine girerken
    `tr()`den geçmek zorunda. Liste dar ve elle bakımlı; yanlış pozitif
    üretmiyor çünkü yalnız gerçekten etiket üreten adları içeriyor.
    """

    def _controlled_source(self, node):
        """İfade bilinen bir ETİKET KAYNAĞINDAN mı okuyor?"""
        from ui.i18n import CONTROLLED_LABEL_SOURCES

        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                names.add(child.id)
            elif isinstance(child, ast.Attribute):
                names.add(child.attr)
        hit = names & set(CONTROLLED_LABEL_SOURCES)
        return sorted(hit)[0] if hit else None

    def _is_translated(self, node):
        """İfade `tr()`/`_t()` çağrısıyla SARILMIŞ mı?"""
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        return name in TRANSLATION_NAMES

    def test_controlled_labels_are_translated_before_substitution(self):
        offenders = []
        for path in python_files():
            name = relative(path)
            if name in ALLOWLIST or name.startswith("tests/"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not is_template_helper(node):
                    continue
                for keyword in node.keywords:
                    if self._is_translated(keyword.value):
                        continue
                    source = self._controlled_source(keyword.value)
                    if source:
                        offenders.append(
                            f"{name}:{node.lineno} — {keyword.arg} "
                            f"({source} etiket kaynağı, tr() ile sarılmalı)"
                        )
        self.assertEqual(
            offenders, [],
            "Kontrollü Türkçe etiket şablona HAM giriyor; İngilizce cümlenin "
            "ortasında Türkçe kalır:\n" + "\n".join(offenders),
        )

    def test_the_controlled_source_check_has_teeth(self):
        """Kapı gerçekten yakalıyor mu — kusurun kendisiyle sınanıyor.

        Örnek CANLI bir kaynakla kuruluyor (`asset_type`): sözleşmede
        olmayan bir adla sınamak, kapının o adı zaten görmeyeceği için
        yanıltıcı bir "diş" iddiası olurdu.
        """
        broken = ast.parse('_tf("Tür Seç: {t}", t=asset_type)')
        call = next(node for node in ast.walk(broken)
                    if isinstance(node, ast.Call) and is_template_helper(node))
        keyword = call.keywords[0]
        self.assertFalse(self._is_translated(keyword.value))
        self.assertEqual(self._controlled_source(keyword.value), "asset_type")

    def test_a_translated_controlled_source_is_accepted(self):
        fixed = ast.parse('_tf("Tür Seç: {t}", t=_t(asset_type))')
        call = next(node for node in ast.walk(fixed)
                    if isinstance(node, ast.Call) and is_template_helper(node))
        self.assertTrue(self._is_translated(call.keywords[0].value))

    def test_user_data_is_not_flagged_as_a_controlled_label(self):
        """Yanlış pozitif olmamalı: kullanıcı adı etiket kaynağı değildir."""
        tree = ast.parse('_tf("{name} eklendi", name=payment["name"])')
        call = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and is_template_helper(node))
        self.assertIsNone(self._controlled_source(call.keywords[0].value))

    def test_every_declared_label_source_is_still_used(self):
        """Sözleşme listesi ÖLÜ girdi biriktirmemeli.

        Kullanılmayan bir ad listede kalırsa kapı, artık var olmayan bir
        riski koruyormuş gibi görünür.

        ÖLÇÜM ŞABLON PARAMETRELERİYLE SINIRLI. İki önceki hâl kaynak
        metinlerde düz metin araması yapıyor ve sözleşmenin KENDİ TANIMINI
        da tarıyordu; bir önceki hâl AST'ye geçti ama `Load`/`Store`
        ayırmıyor ve adın kod tabanında HERHANGİ bir yerde geçmesini
        "canlı" sayıyordu. İkisi de sözleşmenin asıl iddiasını
        kanıtlamıyordu: bu ad ŞABLON PARAMETRESİNE giriyor ve kapı onu
        orada koruyor.
        """
        from ui.i18n import CONTROLLED_LABEL_SOURCES

        self.assertEqual(unused_label_sources(CONTROLLED_LABEL_SOURCES), [])


    def test_a_fake_source_is_reported_as_dead(self):
        from ui.i18n import CONTROLLED_LABEL_SOURCES

        fake = "_TAMAMEN_OLU_SAHTE_KAYNAK"
        self.assertEqual(
            unused_label_sources(set(CONTROLLED_LABEL_SOURCES) | {fake}),
            [fake],
        )

    def test_a_name_that_is_only_assigned_is_not_alive(self):
        """`_OLU = 1` bir KULLANIM değil, tanımdır."""
        tree = ast.parse("_OLU = 1")
        self.assertEqual(
            controlled_sources_in_template_parameters(tree, {"_OLU"}), set()
        )

        assign = tree.body[0]
        self.assertEqual(
            controlled_sources_in_expression(assign.targets[0], {"_OLU"}),
            set(),
        )

    def test_a_read_outside_a_template_parameter_is_not_alive(self):
        """Şablon dışı okuma bu SÖZLEŞME açısından canlı değildir."""
        tree = ast.parse("x = _SOURCE_LABELS")
        self.assertEqual(
            controlled_sources_in_template_parameters(
                tree, {"_SOURCE_LABELS"}),
            set(),
        )

    def test_the_dictionary_definition_itself_is_not_alive(self):
        """`_SOURCE_LABELS = {...}` kendini canlı gösteremez."""
        tree = ast.parse('_SOURCE_LABELS = {"a": "b"}')
        self.assertEqual(
            controlled_sources_in_template_parameters(
                tree, {"_SOURCE_LABELS"}),
            set(),
        )

    def test_a_translated_template_parameter_is_alive(self):
        tree = ast.parse('_tf("{x}", x=_t(_SOURCE_LABELS.get(k, k)))')
        self.assertEqual(
            controlled_sources_in_template_parameters(
                tree, {"_SOURCE_LABELS"}),
            {"_SOURCE_LABELS"},
        )

    def test_a_raw_template_parameter_is_alive_but_fails_the_safety_gate(self):
        """Liveness ile GÜVENLİK ayrı sorular.

        Ham verilen bir kaynak sözleşme açısından CANLIDIR (şablon
        parametresine giriyor), ama ana kapı onu `tr()` ile sarılmadığı için
        REDDEDER. İkisini birbirine karıştırmak, ham kullanımı "zaten
        korunuyor" sanmaya yol açardı.
        """
        tree = ast.parse('_tf("{x}", x=_SOURCE_LABELS.get(k, k))')

        self.assertEqual(
            controlled_sources_in_template_parameters(
                tree, {"_SOURCE_LABELS"}),
            {"_SOURCE_LABELS"},
        )

        call = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and is_template_helper(node))
        keyword = call.keywords[0]
        self.assertFalse(self._is_translated(keyword.value))
        self.assertEqual(self._controlled_source(keyword.value),
                         "_SOURCE_LABELS")

    def test_an_attribute_read_inside_a_template_parameter_is_alive(self):
        tree = ast.parse('_tf("{x}", x=_t(self._asset_selected_type))')
        self.assertEqual(
            controlled_sources_in_template_parameters(
                tree, {"_asset_selected_type"}),
            {"_asset_selected_type"},
        )

    def test_a_name_only_in_a_comment_or_string_is_not_alive(self):
        """Yorum, docstring ve string literali KULLANIM SAYILMAZ."""
        source = "\n".join([
            '"""Docstring içinde _SADECE_YORUMDA gecen bir ad."""',
            "# Yorumda da _SADECE_YORUMDA var.",
            'ETIKET = "_SADECE_YORUMDA"',
            '_tf("{x}", x="_SADECE_YORUMDA")',
        ])
        self.assertEqual(
            controlled_sources_in_template_parameters(
                ast.parse(source), {"_SADECE_YORUMDA"}),
            set(),
        )


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

    def test_every_template_renders_in_english(self):
        """Her şablon gerçekten render edilebiliyor mu (eksik/fazla parametre).

        Bu, `trf`nin `TranslationTemplateError` fırlatmasını üretimde ilk kez
        görmeyi imkânsız kılar: bütün şablonlar burada, kukla değerlerle
        çalıştırılıyor.
        """
        from ui.i18n import placeholders, trf

        for template in sorted(collect_templates()):
            params = {name: "X" for name in placeholders(template)}
            for language in ("en",):
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

    @property
    def USER_FIELDS(self):
        """Sözleşmenin TEK kaynağı `ui.i18n.USER_DATA_FIELDS`.

        Testin kendi kopyasını tutması, iki listenin sessizce ayrışmasına
        açık kapı bırakıyordu; envanter aracı da aynı kaynağı okuyor.
        """
        from ui.i18n import USER_DATA_FIELDS

        return USER_DATA_FIELDS

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
