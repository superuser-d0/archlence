"""Kullanıcının girdiği tutar metinleri için maskeleme ve ayrıştırma.

NEDEN AYRI BİR MODÜL: canlı binlik ayraç maskelemesi girdi metnini
`"250.000"` hâline getiriyor. Bu metni `float()`'a vermek **250.0** üretir —
yani 250 bin lira sessizce 250 liraya döner. Para söz konusu olduğu için bu
sınıf hataların tek bir yerde, testli biçimde çözülmesi gerekiyor.

BELİRSİZLİK VE ÇÖZÜMÜ
---------------------
`"250.000"` tek başına iki şey olabilir: Türkçe gruplama (250 bin) ya da
İngilizce ondalık (250,0). Modül bunu iki katmanla çözer:

1. `attach_amount_mask` ile maskelenen alanlar, görünen metnin yanında
   KANONİK sayısal değeri de widget üzerinde taşır; `read_amount` onu okur ve
   hiç tahmin yapmaz. Maskelenmiş alanlarda belirsizlik kalmaz.
2. Elle yazılmış/eski metinler için `parse_amount` katı bir gruplama kalıbı
   (`1.234.567` gibi ilk gruptan sonra tam üçerli bloklar) arar; kalıp
   tutuyorsa ayraçları gruplama sayar, aksi halde "son geçen ayraç ondalıktır"
   sezgisine döner.

NOT: `mixins/asset_mixin.py::_parse_price_str` KASITLI olarak ayrı bırakıldı.
O, borsa/kur API'lerinden gelen makine metinlerini ("1,500,000.0000") okuyor;
oradaki `"250.000"` gerçekten 250.0 demek olabilir. İki bağlamın kuralları
farklı olduğu için birleştirilmedi.
"""

import re

# Türkçe biçim: ondalık virgül, binlik nokta.
DECIMAL_SEPARATOR = ","
GROUP_SEPARATOR = "."

# En fazla iki ondalık hane tutulur (kuruş).
MAX_DECIMALS = 2

# "1.234", "12.345.678" gibi tam üçerli gruplama; ondalık ayraç YOK.
_GROUPED_PATTERN = re.compile(r"^\d{1,3}(?:\.\d{3})+$")

# Maskelenmiş alanın kanonik değerini taşıdığı attribute.
_CANONICAL_ATTR = "_archlence_amount_value"

# Tutar alanına yazılabilecek en fazla TAM KISIM hanesi (bkz.
# filter_amount_keystroke). float64'ün tam-sayı kesinlik sınırının
# (2**53) güvenli tarafında kalır.
MAX_INTEGER_DIGITS = 12


def _digits_and_decimal(text):
    """Metni (tamsayı_hane_dizisi, ondalık_hane_dizisi | None) hâline getirir."""
    raw = str(text or "")
    # Kullanıcı İngilizce alışkanlıkla '.' yazmış olabilir; maskeleme '.'yi
    # gruplama için kullandığından, ondalık niyeti tek bir ',' ile temsil edilir
    # (dönüşüm filter_amount_keystroke tarafında yapılır).
    if DECIMAL_SEPARATOR in raw:
        integer_part, _, decimal_part = raw.partition(DECIMAL_SEPARATOR)
        return (
            re.sub(r"\D", "", integer_part),
            re.sub(r"\D", "", decimal_part)[:MAX_DECIMALS],
        )
    return re.sub(r"\D", "", raw), None


def parse_amount(text):
    """Kullanıcı tutar metnini float'a çevirir; okunamıyorsa ValueError.

    Kabul edilen biçimler:
      "1.500,50"   -> 1500.5   (Türkçe: nokta gruplama, virgül ondalık)
      "15,000.00"  -> 15000.0  (İngilizce: virgül gruplama, nokta ondalık)
      "250.000"    -> 250000.0 (katı gruplama kalıbı: üçerli bloklar)
      "250.5"      -> 250.5    (gruplama kalıbına uymaz -> ondalık)
      "1500"       -> 1500.0
    """
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Tutar boş olamaz.")

    # İşaret ve para birimi süslemeleri: eksi kabul EDİLMEZ (yön Gelir/Gider
    # seçimiyle belirlenir), bu yüzden '-' varsa doğrudan reddediyoruz.
    if "-" in raw:
        raise ValueError("Tutar negatif olamaz.")
    cleaned = raw.replace("₺", "").replace(" ", "").replace("+", "").strip()
    if not cleaned:
        raise ValueError("Tutar boş olamaz.")
    if not re.fullmatch(r"[\d.,]+", cleaned):
        raise ValueError(f"Geçersiz tutar: {text!r}")

    # 1) Yalnız nokta içeren ve tam üçerli gruplanmış metin -> gruplama.
    if _GROUPED_PATTERN.fullmatch(cleaned):
        return float(cleaned.replace(GROUP_SEPARATOR, ""))

    # 2) Aynı kalıp virgülle (İngilizce gruplama) -> gruplama.
    if _GROUPED_PATTERN.fullmatch(cleaned.replace(",", ".")) and "." not in cleaned:
        return float(cleaned.replace(",", ""))

    # 3) Genel kural: son geçen ayraç ondalıktır (asset_mixin'deki sezgiyle
    #    aynı), diğer tüm ayraçlar gruplama sayılır.
    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    if last_dot > last_comma:
        normalized = cleaned.replace(",", "")
    elif last_comma > last_dot:
        normalized = cleaned.replace(".", "").replace(",", ".")
    else:
        normalized = cleaned

    try:
        return float(normalized)
    except ValueError:
        raise ValueError(f"Geçersiz tutar: {text!r}") from None


def parse_amount_to_float(text, default=0.0):
    """`parse_amount`'ın asla hata fırlatmayan sürümü.

    Kaydetme yolunda kullanılmaz (orada kullanıcıya "Geçersiz tutar" demek
    gerekir); önizleme/canlı hesap gibi bir değerin hep bulunması gereken
    yerler için.
    """
    try:
        return parse_amount(text)
    except (ValueError, TypeError):
        return default


def format_amount_input(text):
    """Girdi metnini canlı maskeler: "250000" -> "250.000".

    Yazma sırasını bozmamak için ondalık kısım OLDUĞU GİBİ korunur: kullanıcı
    "1500," yazdığında virgül silinmez (yoksa kuruş yazmaya başlayamaz),
    "1500,5" de "1.500,50"a tamamlanmaz.
    """
    integer_digits, decimal_digits = _digits_and_decimal(text)

    # Baştaki gereksiz sıfırlar temizlenir ama "0" ve "0,xx" korunur.
    integer_digits = integer_digits.lstrip("0") or ("0" if integer_digits else "")

    grouped = ""
    if integer_digits:
        grouped = f"{int(integer_digits):,}".replace(",", GROUP_SEPARATOR)

    if decimal_digits is None:
        return grouped
    # Ondalık ayraç yazılmış: tamsayı kısmı boşsa "0," ile başlat.
    return f"{grouped or '0'}{DECIMAL_SEPARATOR}{decimal_digits}"


def format_amount_value(value):
    """Sayısal bir değeri maskelenmiş alana yazılabilir metne çevirir.

    1500.5 -> "1.500,50",  250000 -> "250.000,00"

    Programatik atamalarda ZORUNLUDUR: `field.text = f"{1500.0:.2f}"` yazmak
    alana `"1500.00"` koyar; maskeleme orada ondalık ayraç (virgül) görmediği
    için tüm haneleri tamsayı sayar ve `"150.000"` üretir — yani değer 100 katına
    çıkar. Bu fonksiyon ondalığı virgülle verdiği için maskeleme onu korur.
    """
    number = float(value or 0)
    if number < 0:
        raise ValueError("Tutar negatif olamaz.")
    formatted = f"{number:,.{MAX_DECIMALS}f}"
    # "1,500.50" (Python varsayılanı) -> "1.500,50" (Türkçe)
    return formatted.replace(",", "X").replace(".", DECIMAL_SEPARATOR).replace(
        "X", GROUP_SEPARATOR)


def set_amount(field, value):
    """Maskelenmiş alana sayısal bir değeri güvenle yazar."""
    field.text = format_amount_value(value)
    return field


def canonical_amount_text(text):
    """Maskelenmiş metnin ayrıştırmaya hazır kanonik hâli ("1500.5")."""
    integer_digits, decimal_digits = _digits_and_decimal(text)
    if not integer_digits and not decimal_digits:
        return ""
    base = integer_digits.lstrip("0") or "0"
    if decimal_digits:
        return f"{base}.{decimal_digits}"
    return base


def filter_amount_keystroke(substring, existing_text=""):
    """`MDTextField.input_filter` için: yalnız rakam ve TEK ondalık ayraç.

    Harf, işaret ve diğer semboller anında düşer. Kullanıcı İngilizce
    alışkanlıkla '.' yazarsa bu ONDALIK niyeti sayılır ve ','ye çevrilir —
    aksi halde maskelemenin ürettiği gruplama noktalarından ayırt edilemezdi
    ve "1500.5" sessizce 15005 olurdu.
    """
    text = str(substring or "")
    current = str(existing_text or "")
    already_has_decimal = DECIMAL_SEPARATOR in current

    # Tam kısımdaki hane sayısı ÜST SINIRI. Kullanıcı raporu: alana çok uzun
    # sayılar girilince uygulama "sapıtıyor" (ekran görüntüsünde
    # ₺112.955.698.541.615.249.872.910,00 gibi toplamlar). Sebep yalnız görsel
    # değil: float64 yalnızca 2**53 (~9,007e15) değerine kadar TAM SAYIYI
    # birebir taşır; ötesinde toplama/çıkarma sessizce yuvarlanır ve bakiye
    # matematiği anlamını yitirir. MAX_INTEGER_DIGITS bu sınırın güvenli
    # tarafında kalır (999.999.999.999 = 12 hane) ve kişisel finans için
    # fazlasıyla yeterlidir. Sınır girdi ANINDA uygulanır: mevcut kayıtlar
    # etkilenmez, kullanıcı sadece yeni absürt değer yazamaz.
    integer_part = current.split(DECIMAL_SEPARATOR)[0]
    integer_digits = sum(1 for char in integer_part if char.isdigit())

    result = []
    for char in text:
        if char.isdigit():
            if not already_has_decimal and integer_digits >= MAX_INTEGER_DIGITS:
                continue  # tam kısım doldu, yeni hane kabul edilmez
            if not already_has_decimal:
                integer_digits += 1
            result.append(char)
        elif char in (DECIMAL_SEPARATOR, GROUP_SEPARATOR):
            if not already_has_decimal:
                result.append(DECIMAL_SEPARATOR)
                already_has_decimal = True
        # diğer her şey (harf, '-', '+', boşluk, sembol) sessizce düşer
    return "".join(result)


def read_amount(field, default=None):
    """Maskelenmiş bir alandan güvenle float okur.

    Önce widget üzerindeki KANONİK değeri arar (maskeleme onu her değişimde
    günceller), yoksa görünen metni sezgisel ayrıştırıcıya verir. Böylece
    maskelenmiş alanlarda "250.000" hiçbir zaman 250.0 olarak okunamaz.

    `default` verilmezse geçersiz girdi ValueError fırlatır — kaydetme yolu
    kullanıcıya uyarı gösterebilsin diye.
    """
    canonical = getattr(field, _CANONICAL_ATTR, None)
    source = canonical if canonical else getattr(field, "text", "")
    if default is None:
        return parse_amount(source)
    return parse_amount_to_float(source, default)


def attach_amount_mask(field):
    """Bir `MDTextField`e canlı binlik ayraç maskelemesi bağlar.

    - `input_filter` ile geçersiz karakterler hiç girmez.
    - Metin her DÜZENLEMEDE yeniden gruplanır ve imleç, kullanıcının yazdığı
      hanenin hemen ardında bırakılır.
    - Kanonik sayısal değer widget üzerinde saklanır; `read_amount` onu okur.

    İMLEÇ HATASI (v0.0.1'de düzeltildi). Yeniden biçimlendirme eskiden
    `bind(text=...)` ile, yani Kivy'nin `on_text` olayında yapılıyordu. Kivy
    `TextInput.insert_text` içinde ÖNCE `self.text`i değiştirir, imleci ANCAK
    SONRA ilerletir — dolayısıyla `on_text` sırasında okunan `cursor_index()`
    bir karakter GERİDEDİR. Sonuç yalnız "imleç geri kayıyor" değildi: sonraki
    hane yanlış konuma giriyor ve sayı BOZULUYORDU —

        yazılan 1234567  ->  alanda 1.235.674   (olması gereken 1.234.567)

    Yani kullanıcı doğru rakamı yazdığı hâlde hesaba bambaşka bir tutar
    giriyordu. Düzeltme: yeniden biçimlendirme artık `on_text`te değil,
    `insert_text`/`do_backspace` TAMAMLANDIKTAN SONRA çalışıyor; o noktada
    `cursor_index()` gerçek konumu verir. `text` bağlaması yalnızca kanonik
    değeri güncel tutar (programatik `field.text = ""` gibi atamalar için).
    """
    field.input_filter = lambda substring, from_undo: filter_amount_keystroke(
        substring, field.text
    )
    setattr(field, _CANONICAL_ATTR, canonical_amount_text(field.text))

    # Yeniden giriş koruması: aşağıdaki setter kendi on_text'ini tetikliyor.
    state = {"busy": False}

    def _sync_canonical(instance, value):
        """Programatik metin atamalarında kanonik değeri güncel tutar."""
        if state["busy"]:
            return
        setattr(instance, _CANONICAL_ATTR, canonical_amount_text(value))

    def _regroup_and_place_cursor():
        """Metni yeniden grupla, imleci yazılan hanenin ardında bırak.

        YALNIZCA bir düzenleme tamamlandıktan sonra çağrılır; bu yüzden
        `cursor_index()` burada güvenilirdir.
        """
        value = field.text
        formatted = format_amount_input(value)
        setattr(field, _CANONICAL_ATTR, canonical_amount_text(formatted))
        if formatted == value:
            return

        # İmleç, kendisinden ÖNCE kaç ANLAMLI karakter (hane/ondalık ayraç)
        # olduğuna göre yeniden bulunur; gruplama noktaları sayılmaz, çünkü
        # onların sayısı biçimlendirmeyle değişiyor.
        cursor_index = field.cursor_index()
        significant_before = sum(
            1 for char in value[:cursor_index]
            if char.isdigit() or char == DECIMAL_SEPARATOR
        )

        state["busy"] = True
        try:
            field.text = formatted
        finally:
            state["busy"] = False

        seen = 0
        new_index = len(formatted)
        for index, char in enumerate(formatted):
            if seen >= significant_before:
                new_index = index
                break
            if char.isdigit() or char == DECIMAL_SEPARATOR:
                seen += 1
        field.cursor = field.get_cursor_from_index(new_index)

    # Kivy `self.insert_text(...)` çağırdığı için örnek üzerindeki bu isimler
    # sınıf metodunun önüne geçer; sınıf metodunu açıkça çağırıp ARDINDAN
    # biçimlendiriyoruz.
    cls = type(field)

    def insert_text(substring, from_undo=False):
        cls.insert_text(field, substring, from_undo)
        _regroup_and_place_cursor()

    def do_backspace(from_undo=False, mode="bkspc"):
        cls.do_backspace(field, from_undo, mode)
        _regroup_and_place_cursor()

    field.insert_text = insert_text
    field.do_backspace = do_backspace
    field.bind(text=_sync_canonical)
    return field
