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
    get_connection,
    managed_connection,
)
from utils.crypto import decrypt
from utils.errors import DecryptionError, KeyUnavailableError

CSV_HEADER = ["kayit_turu", "tarih", "tur", "kategori", "tutar", "miktar", "aciklama", "detay"]

# Jenerik CSV başlıklarını alan adlarına eşleme (küçük harfe indirilmiş halleriyle)
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


def get_export_path():
    """Dışa aktarım hedefini döndürür: masaüstü varsa oraya, yoksa kullanıcı-veri dizinine."""
    home = os.path.expanduser("~")
    for candidate in ("Masaüstü", "Desktop"):
        desktop = os.path.join(home, candidate)
        if os.path.isdir(desktop):
            return os.path.join(desktop, "archlence_export.csv")
    # docs/ROADMAP.md Faz 1 madde 4. Eskiden BASE_DIR'a (uygulamanın kendi
    # kurulum dizini) düşerdi — paketlenmiş bir Windows kurulumunda bu
    # genelde salt-okunur, Masaüstü bulunamazsa dışa aktarım burada
    # sessizce başarısız olurdu.
    from utils.app_paths import data_dir
    return os.path.join(data_dir(), "archlence_export.csv")


def _dec(value):
    """Şifreli kolonu çözer; çözülemeyen (eski/bozuk) kayıtta boş döner ki
    tek bir bozuk satır tüm dışa aktarımı düşürmesin."""
    try:
        return decrypt(str(value), SECRET_KEY)
    except KeyUnavailableError:
        # Anahtar yoksa HİÇBİR alan çözülemez ve kullanıcı BAŞTAN SONA BOŞ
        # bir CSV indirir — verisini kaybettiğini sanır. Tek bozuk satırı
        # tolere etmek başka, tüm dışa aktarımın sessizce boşalması başka.
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

    # `managed_connection` ŞART, çıplak `get_connection()` DEĞİL: aşağıdaki
    # `_dec()` çağrıları anahtar erişilemediğinde KeyUnavailableError
    # fırlatıyor ve eski kodda `conn.close()` fonksiyonun sonunda tek başına
    # duruyordu — araya giren her istisnada bağlantı sızıyordu. Windows'ta
    # sızan bağlantı dosyayı kilitli tutuyor (CI bunu WinError 32 ile
    # yakaladı); Linux'ta sessizce sızıyordu. Bu, database/db.py'deki
    # `managed_connection` docstring'inin anlattığı hatanın aynısı.
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
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            writer.writerows(rows_out)
            f.flush(); os.fsync(f.fileno())
        os.replace(staged, target)
        os.chmod(target, 0o600)
    # EXCEPTION-AUDIT: bilinçli geniş — staged dosyanın silinmesi HER hata
    # türünde çalışmalı (şifresi çözülmüş finansal veri diskte kalmasın).
    # Handler yutmuyor, yeniden fırlatıyor.
    except Exception:
        try: os.unlink(staged)
        except FileNotFoundError: pass
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
        field_map = {}
        for name in reader.fieldnames:
            key = _COLUMN_ALIASES.get((name or "").strip().lower())
            if key and key not in field_map:
                field_map[key] = name
        has_type_col = "kayit_turu" in [(n or "").strip().lower() for n in reader.fieldnames]

        for row in reader:
            if has_type_col:
                kayit_turu = (row.get("kayit_turu") or "").strip().lower()
                if kayit_turu != "islem":
                    continue  # varlık/borç/tekrarlanan satırları işlem değildir

            raw_tur = (row.get(field_map.get("tur", ""), "") or "").strip().lower()
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
                # "1.234,56" Türk biçimini de kabul et
                if "," in raw_amount and raw_amount.count(",") == 1:
                    raw_amount = raw_amount.replace(".", "").replace(",", ".")
                amount = float(raw_amount)
                # math.isfinite ŞART: float("inf") ve float("nan") ikisi de
                # Python'da SORUNSUZ ayrıştırılır ve İKİSİ DE `<= 0`
                # koşulunu geçmez (IEEE 754: nan ile yapılan her
                # karşılaştırma False'tur, inf zaten <= 0 değildir). Yani bu
                # guard tek başına ikisini de KABUL ediyordu. Böyle tek bir
                # satır içeri alınınca adjust_account_balance'ın
                # `balance = balance + ?` işlemi hesabı kalıcı olarak
                # zehirliyor: inf/nan sonraki HER SUM(balance) üzerinden
                # yayılıyor, yani uygulamadaki her Net Servet rakamı bozuluyor
                # ve kullanıcı ilgili satırı elle bulup silene kadar düzelmiyor.
                # Elle giriş yolu bu sınıfa karşı zaten korunuyordu
                # (utils/formatters.py::read_amount + input_filter); aynı
                # disiplin CSV yoluna hiç uygulanmamıştı.
                if not math.isfinite(amount) or amount <= 0:
                    raise ValueError
            except ValueError:
                skipped += 1
                continue

            records.append({
                "date": date,
                "type": tx_type,
                "category": (row.get(field_map.get("kategori", ""), "") or "").strip() or "Diğer",
                "amount": amount,
                "description": (row.get(field_map.get("aciklama", ""), "") or "").strip(),
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
            # Geçmişi olduğu gibi yeniden kuruyoruz: gerçekte limiti zorlamış bir
            # kart harcaması da içeri alınabilmeli, içe aktarım reddedilmemeli.
            enforce_credit_limit=False,
        )
        net_delta += rec["amount"] if rec["type"] == "income" else -rec["amount"]
        imported += 1

    return imported, skipped, net_delta
