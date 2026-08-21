"""Veri İçe/Dışa Aktarma (Migration) servisi.

Başka platformdan geçen kullanıcılar için: mevcut veriler şifresi çözülmüş,
okunabilir tek bir CSV'ye yazılır; dışarıdan gelen CSV'deki işlemler ise
TransactionService.add_transaction üzerinden içeri alınır — böylece şifreleme
ve accounts.balance senkronu tek noktadan, atomik olarak işler.

CSV şeması (tek dosya, kayit_turu ayırt edici kolonu):
    kayit_turu ∈ {islem, varlik, borc, tekrarlanan}
    islem       → tarih, tur(gelir/gider), kategori, tutar, aciklama
    varlik      → tarih=alım tarihi, tur=varlık türü, kategori=sembol,
                  tutar=birim alım fiyatı, miktar=adet, aciklama=varlık adı
    borc        → tutar=toplam borç, aciklama=borç adı,
                  detay="aylik_odeme=..;toplam_taksit=..;odenen_taksit=.."
    tekrarlanan → tarih=sonraki vade, tur=sıklık, tutar, aciklama=ad,
                  detay="otomatik=0/1"

İçe aktarım yalnızca işlem satırlarını okur (varlık/borç yapıları platformlar
arası birebir taşınamayacak kadar farklıdır); hem bu dosyanın kendi formatını
hem de jenerik "Tarih,Tür,Kategori,Tutar,Açıklama" başlıklı CSV'leri tanır.
"""

import csv
import math
import os
import tempfile
from pathlib import Path
from datetime import datetime

from database.db import (
    DEFAULT_ACCOUNT_ID,
    SECRET_KEY,
    managed_connection,
)
from utils.crypto import decrypt
from utils.errors import DecryptionError, KeyUnavailableError


CSV_VERSION_COLUMN = "_archlence_csv_version"


CSV_ESCAPE_VERSION = 2


SUPPORTED_CSV_VERSIONS = frozenset({2})

CSV_HEADER = [
    CSV_VERSION_COLUMN,
    "kayit_turu", "tarih", "tur", "kategori", "tutar", "miktar", "aciklama",
    "detay",
]


_RECORD_KINDS = frozenset({"islem", "varlik", "borc", "tekrarlanan"})


_COLUMN_ALIASES = {
    "tarih": "tarih", "date": "tarih",
    "tur": "tur", "tür": "tur", "type": "tur",
    "kategori": "kategori", "category": "kategori",
    "tutar": "tutar", "miktar": "tutar", "amount": "tutar",
    "aciklama": "aciklama", "açıklama": "aciklama", "description": "aciklama",
}

_INCOME_WORDS = {"gelir", "income"}
_EXPENSE_WORDS = {"gider", "expense", "harcama"}

_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y",
]


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


_CSV_ESCAPE_CHAR = "'"


_CSV_TEXT_COLUMNS = ("tur", "kategori", "aciklama", "detay")
_CSV_TEXT_INDEXES = tuple(
    CSV_HEADER.index(column) for column in _CSV_TEXT_COLUMNS
)


def escape_csv_text(value):
    """Kullanıcı metnini elektronik tabloya formül olarak teslim etmeyecek
    hâle getirir. Zararsız metinde KİMLİKTİR — hiçbir hücre boşuna bozulmaz."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES) or text.startswith(_CSV_ESCAPE_CHAR):
        return _CSV_ESCAPE_CHAR + text
    return text


def unescape_csv_text(value):
    """`escape_csv_text`'in tam tersi: baştaki tek apostrofu soyar."""
    text = "" if value is None else str(value)
    if text.startswith(_CSV_ESCAPE_CHAR):
        return text[1:]
    return text


def _escape_row(row):
    """Bir satırı dışa aktarıma hazırlar: sürüm işareti + metin kaçışı.

    `row` sürüm kolonunu İÇERMEDEN gelir (çağıranlar veri kolonlarını üretir);
    işaret burada, tek yerde eklenir ki hiçbir satır işaretsiz çıkmasın.
    """
    escaped = [str(CSV_ESCAPE_VERSION)] + list(row)
    for index in _CSV_TEXT_INDEXES:
        escaped[index] = escape_csv_text(escaped[index])
    return escaped


_AMBIGUOUS = object()


def _row_escape_version(raw):
    """Satırın sürüm işaretini çözer.

    Döner: desteklenen sürüm numarası, `None` (işaret yok) ya da
    `_AMBIGUOUS` (işaret var ama okunamıyor/desteklenmiyor).
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return _AMBIGUOUS
    try:
        version = int(text)
    except ValueError:
        return _AMBIGUOUS
    if version not in SUPPORTED_CSV_VERSIONS:
        return _AMBIGUOUS
    return version


def get_export_path():
    """Dışa aktarım hedefini döndürür: masaüstü varsa oraya, yoksa kullanıcı-veri dizinine."""
    home = os.path.expanduser("~")
    for candidate in ("Masaüstü", "Desktop"):
        desktop = os.path.join(home, candidate)
        if os.path.isdir(desktop):
            return os.path.join(desktop, "archlence_export.csv")


    from utils.app_paths import data_dir
    return os.path.join(data_dir(), "archlence_export.csv")


def _dec(value):
    """Şifreli kolonu çözer; çözülemeyen (eski/bozuk) kayıtta boş döner ki
    tek bir bozuk satır tüm dışa aktarımı düşürmesin."""
    try:
        return decrypt(str(value), SECRET_KEY)
    except KeyUnavailableError:


        raise
    except (DecryptionError, ValueError, TypeError):
        from utils.logging_config import get_logger
        get_logger().exception(
            "[VERİ BÜTÜNLÜĞÜ] CSV dışa aktarımında bir alan çözülemedi")
        return ""


def export_all_to_csv(path=None):
    """transactions + active_assets + active_debts + recurring_payments
    tablolarını çözülmüş halde tek CSV'ye yazar. (yol, satır sayısı) döndürür."""
    path = path or get_export_path()
    rows_out = []


    with managed_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT transaction_date, type, category, amount, description "
            "FROM transactions ORDER BY id"
        )
        for r in cursor.fetchall():
            tur = "gelir" if r["type"] in ("income", "Gelir") else "gider"
            rows_out.append([
                "islem", r["transaction_date"] or "", tur, r["category"] or "",
                _dec(r["amount"]), "", _dec(r["description"]), "",
            ])

        cursor.execute(
            "SELECT asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date "
            "FROM active_assets ORDER BY id"
        )
        for r in cursor.fetchall():
            rows_out.append([
                "varlik", r["purchase_date"] or "", r["asset_type"] or "", r["asset_code"] or "",
                _dec(r["purchase_price"]), _dec(r["quantity"]), _dec(r["asset_name"]), "",
            ])

        cursor.execute(
            "SELECT debt_name, total_amount, monthly_payment, total_installments, "
            "paid_installments FROM active_debts WHERE is_active = 1 ORDER BY id"
        )
        for r in cursor.fetchall():
            detay = (
                f"aylik_odeme={_dec(r['monthly_payment'])};"
                f"toplam_taksit={r['total_installments']};"
                f"odenen_taksit={r['paid_installments']}"
            )
            rows_out.append([
                "borc", "", "", "", _dec(r["total_amount"]), "", _dec(r["debt_name"]), detay,
            ])

        cursor.execute(
            "SELECT name, amount, category, frequency, next_due_date, "
            "recurrence_day, auto_deduct "
            "FROM recurring_payments WHERE is_active = 1 ORDER BY id"
        )
        for r in cursor.fetchall():
            rows_out.append([
                "tekrarlanan", r["next_due_date"] or "", r["frequency"] or "", r["category"] or "",
                _dec(r["amount"]), "", _dec(r["name"]),
                f"otomatik={r['auto_deduct']};gun={r['recurrence_day']}",
            ])


    # Plaintext finance exports are private files, irrespective of umask.
    # Stage beside the target so replace is atomic and never follows an
    # existing symlink target.
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=".archlence-export-", dir=target.parent)
    fd_handed_off = False
    try:


        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:

            fd_handed_off = True
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            writer.writerows(_escape_row(row) for row in rows_out)
            f.flush(); os.fsync(f.fileno())
        os.replace(staged, target)
        if hasattr(os, "fchmod"):
            os.chmod(target, 0o600)


    except Exception:


        if not fd_handed_off:
            try: os.close(fd)
            except OSError: pass
        try: os.unlink(staged)
        except (FileNotFoundError, PermissionError): pass
        raise

    return path, len(rows_out)


def _normalize_date(raw):
    """Desteklenen formatlardaki tarihi DB'nin kullandığı biçime çevirir;
    tanınmazsa None döner (satır atlanır, tarih uydurmayız)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def parse_transactions_csv(path):
    """CSV'den içe aktarılabilir işlem satırlarını çıkarır.

    Dönen her öğe: {date, type('income'/'expense'), category, amount, description}.
    Archlence'nın kendi export formatında yalnızca kayit_turu=islem satırları alınır;
    jenerik dosyalarda tüm satırlar denenir. Bozuk satırlar sessizce atlanır ve
    (kayıtlar, atlanan_sayısı) olarak raporlanır.
    """
    records, skipped = [], 0

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return [], 0


        header_map = {}
        for name in reader.fieldnames:
            key = (name or "").strip().lower()
            if key and key not in header_map:
                header_map[key] = name
        field_map = {}
        for key, raw_name in header_map.items():
            alias = _COLUMN_ALIASES.get(key)
            if alias and alias not in field_map:
                field_map[alias] = raw_name

        type_col = header_map.get("kayit_turu")
        version_col = header_map.get(CSV_VERSION_COLUMN)


        def _text(row, key, unescape):
            raw = row.get(field_map.get(key, ""), "") or ""
            return unescape_csv_text(raw) if unescape else raw

        for row in reader:
            unescape = False
            if version_col is not None:
                version = _row_escape_version(row.get(version_col))
                if version is _AMBIGUOUS:


                    skipped += 1
                    continue
                unescape = version is not None

            if type_col is not None:
                kayit_turu = (row.get(type_col) or "").strip().lower()
                if kayit_turu not in _RECORD_KINDS:


                    skipped += 1
                    continue
                if kayit_turu != "islem":
                    continue

            raw_tur = _text(row, "tur", unescape).strip().lower()
            if raw_tur in _INCOME_WORDS:
                tx_type = "income"
            elif raw_tur in _EXPENSE_WORDS:
                tx_type = "expense"
            else:
                skipped += 1
                continue

            date = _normalize_date(row.get(field_map.get("tarih", ""), ""))
            if not date:
                skipped += 1
                continue

            raw_amount = (row.get(field_map.get("tutar", ""), "") or "").strip()
            try:

                if "," in raw_amount and raw_amount.count(",") == 1:
                    raw_amount = raw_amount.replace(".", "").replace(",", ".")
                amount = float(raw_amount)


                if not math.isfinite(amount) or amount <= 0:
                    raise ValueError
            except ValueError:
                skipped += 1
                continue

            records.append({
                "date": date,
                "type": tx_type,
                "category": _text(row, "kategori", unescape).strip() or "Diğer",
                "amount": amount,
                "description": _text(row, "aciklama", unescape).strip(),
            })

    return records, skipped


def import_transactions_from_csv(path, account_id=DEFAULT_ACCOUNT_ID):
    """CSV'deki işlemleri TransactionService üzerinden içeri alır.

    Şifreleme ve accounts.balance güncellemesi add_transaction içinde atomik
    yapıldığından burada ayrıca bir şey yapılmaz — geçmiş tarihli her kayıt
    bakiyeyi kendi yönünde (gelir +, gider -) etkiler.
    (aktarılan_sayısı, atlanan_sayısı, net_bakiye_etkisi) döndürür.
    """
    from services.transaction_service import TransactionService

    records, skipped = parse_transactions_csv(path)
    net_delta = 0.0
    imported = 0
    for rec in records:
        TransactionService.add_transaction(
            account_id=account_id,
            amount=rec["amount"],
            transaction_type=rec["type"],
            category=rec["category"],
            description=rec["description"] or rec["category"],
            transaction_date=rec["date"],


            enforce_credit_limit=False,
        )
        net_delta += rec["amount"] if rec["type"] == "income" else -rec["amount"]
        imported += 1

    return imported, skipped, net_delta
