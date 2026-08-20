"""Eski `savings_goals.json` kayıtlarını SQLite'a taşıyan göç motoru.

NEDEN VAR (sözleşme: docs/ARCHITECTURE.md): birikim hedefleri iki yerde
yaşıyordu — para SQLite'ta, ekrandaki kart `savings_goals.json`'da. JSON hedefi
yalnız SAYISAL id ile işaretliyordu ve `sqlite_sequence` `finance.db`'nin
içinde olduğu için restore o sayacı geri sarıyordu: restore'dan sonra açılan
hedef, bayat JSON'un hâlâ işaret ettiği id'yi yeniden alıyor ve kullanıcının
parası yanlış hedefe yazılıyordu.

Bu modül UI'dan TAMAMEN bağımsızdır (Kivy import etmez), böylece doğrudan
test edilebilir.

SÖZLEŞME — hepsi aynı anda geçerli:

  * İdempotent. Kaç kez koşarsa koşsun ikinci kez satır üretmez; bunu
    kayıt-başına işaretle (`savings_migration_state`) sağlar ve o işaretler
    INSERT'lerle AYNI transaction'da yazılır.
  * Tek transaction. `BEGIN IMMEDIATE` ... `COMMIT`. Commit olmadıysa hiçbir
    şey değişmemiştir.
  * Mevcut SQL satırını EZMEZ. Eşleşen kayıtta yalnız BOŞ olan
    color/created_at/auto_deposit alanları doldurulur; tutarlara dokunulmaz.
  * Finansal değer ÜRETMEZ. Hiçbir hesap bakiyesi, hiçbir `balance_events`
    satırı değişmez. Karşılığı olmayan ve ÜZERİNDE PARA OLAN bir JSON kaydı
    INSERT EDİLMEZ — karantinaya alınır (aşağıdaki nota bakın).
  * Belirsizlikte otomatik karar vermez; karantinaya alır ve kullanıcıya
    gösterilmek üzere kaydeder.
  * Başarılı doğrulama öncesinde JSON'a DOKUNMAZ; başarıdan sonra da silmez,
    `savings_goals.json.migrated-<ISO>` olarak korur.
  * Nihai işaret ancak her şey bittikten SONRA yazılır.

"KARŞILIĞI OLMAYAN VE PARA TAŞIYAN KAYIT NEDEN INSERT EDİLMİYOR": eski
uygulamada bir hedefe para yatırmak `deposit_to_goal` üzerinden geçiyordu,
yani parası olan her hedefin SQL'de bir satırı VARDI. Karşılığı olmayan ama
`current > 0` diyen bir JSON kaydı bu yüzden anomalidir: satır silinmiş ya da
başka bir generation'dan kalmıştır ve paranın hesaba iade edilip edilmediğini
bilmenin yolu yoktur. Onu INSERT etmek, hiçbir hesaptan çıkmamış parayı
defterde yoktan var etmek olurdu (`_backfill_ledger_baseline` ona bir açılış
olayı yazardı). Kayıt karantinaya alınır: veri KAYBOLMAZ, kullanıcıya
gösterilir, ama otomatik olarak paraya çevrilmez.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from database import db as _db
from database.db import SECRET_KEY
from utils.app_paths import data_dir
from utils.crypto import decrypt, encrypt
from utils.errors import DecryptionError, KeyUnavailableError
from utils.financial_decimal import fiat

SAVINGS_JSON_NAME = "savings_goals.json"


def _default_db_path():
    """Veritabanı yolunu ÇAĞRI ANINDA çözer.

    `from database.db import DB_NAME` bağı import anında sabitleniyor ve
    `database.db.DB_NAME`'i yamalayan çağıranlar (testler, sıfırlama akışı)
    sessizce GERÇEK profile yazardı. Kod tabanının geri kalanı da (bkz.
    `database/db.py::get_connection`) değeri her çağrıda okuyor.
    """
    return _db.DB_NAME

#: `savings_migration_state` içindeki nihai işaret. Bu satır varsa göç
#: tamamlanmıştır ve sonradan ortaya çıkan her JSON dosyası BAYATTIR.
MIGRATION_MARKER = "savings_json_to_sql"

_JOURNAL_DIRNAME = ".archlence-savings-migration"
_JOURNAL_NAME = "journal.json"

STATE_READ = "OKUNDU"
STATE_PLANNED = "PLANLANDI"
STATE_APPLIED = "UYGULANDI"
STATE_VERIFIED = "DOĞRULANDI"
STATE_RETIRED = "EMEKLİ"

# Karar etiketleri (karantina `reason` sütununa da bu değerler yazılır).
DECISION_MATCH = "match"
DECISION_INSERT = "insert"
DECISION_QUARANTINE = "quarantine"

REASON_ID_COLLISION = "ayni-id-farkli-hedef"
REASON_AMBIGUOUS = "ayni-ad-tutar-farkli-id"
REASON_DUPLICATE_ID = "json-icinde-yinelenen-id"
REASON_UNMATCHED_WITH_BALANCE = "karsiligi-yok-uzerinde-para-var"
REASON_INVALID = "okunamayan-kayit"
REASON_STALE_JSON = "restore-sonrasi-bayat-json"
REASON_UNREADABLE_FILE = "bozuk-json-dosyasi"

# Kullanıcıya gösterilen metinler. Dosya yolu, exception ayrıntısı ya da
# traceback İÇERMEZ — `startup_recovery.USER_MESSAGE` ile aynı gerekçe.
QUARANTINE_USER_MESSAGES = {
    REASON_ID_COLLISION:
        "Bu hedefin numarası başka bir hedefe ait görünüyor; otomatik "
        "taşımak yanlış hedefe para yazma riski taşıyordu.",
    REASON_AMBIGUOUS:
        "Aynı ad ve tutarda başka bir hedef var; hangisinin kastedildiği "
        "kesin olmadığı için birleştirilmedi.",
    REASON_DUPLICATE_ID:
        "Eski dosyada aynı numarayı taşıyan birden çok hedef var.",
    REASON_UNMATCHED_WITH_BALANCE:
        "Bu hedefin veritabanında karşılığı yok ama üzerinde birikim "
        "görünüyor; para yoktan var edilmesin diye taşınmadı.",
    REASON_INVALID:
        "Eski dosyadaki bu kayıt okunamadı.",
    REASON_STALE_JSON:
        "Bu kayıt, geri yükleme öncesinden kalmış eski bir dosyadan geliyor "
        "ve güncel verinizle çelişebilir.",
    REASON_UNREADABLE_FILE:
        "Eski hedef dosyası okunamadı; hiçbir kayıt taşınmadı ve dosya "
        "olduğu gibi saklandı.",
}


class SavingsMigrationError(Exception):
    """Göç güvenle tamamlanamadı; hiçbir kalıcı karar verilmedi."""


# ── Yollar ────────────────────────────────────────────────────────────────
def savings_json_path(directory=None) -> Path:
    return Path(directory or data_dir()) / SAVINGS_JSON_NAME


def _journal_dir(db_path) -> Path:
    return Path(db_path).parent / _JOURNAL_DIRNAME


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _retire_path(json_path: Path, suffix: str) -> Path:
    """`savings_goals.json` -> `savings_goals.json.<suffix>-<zaman>`.

    Aynı saniye içinde ikinci bir dosya üretilirse (testler ve hızlı ardışık
    restore'lar) sayaç eklenir; `os.replace` sessizce üzerine yazardı.
    """
    base = json_path.with_name(f"{json_path.name}.{suffix}-{_timestamp()}")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{counter}")
        counter += 1
    return candidate


# ── Journal (restore journal'ıyla aynı desen) ─────────────────────────────
def _write_journal(db_path, state, detail=None):
    directory = _journal_dir(db_path)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "state": state,
        "db_path": str(db_path),
        "detail": detail or {},
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    target = directory / _JOURNAL_NAME
    handle_fd, staged = tempfile.mkstemp(dir=str(directory), prefix=".journal-")
    with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, target)
    return target


def read_journal(db_path=None):
    path = _journal_dir(db_path or _default_db_path()) / _JOURNAL_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clear_journal(db_path):
    shutil.rmtree(_journal_dir(db_path), ignore_errors=True)


# ── Veritabanı yardımcıları ───────────────────────────────────────────────
def _connect(db_path):
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def migration_completed(db_path=None) -> bool:
    """Nihai işaret var mı? (Bayat JSON kuralının tek dayanağı.)"""
    db_path = Path(db_path or _default_db_path())
    if not db_path.exists():
        return False
    with closing(_connect(db_path)) as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM savings_migration_state WHERE marker = ?",
                (MIGRATION_MARKER,),
            ).fetchone()
        except sqlite3.Error:
            # Tablo yoksa profil bu kuşaktan önce; göç henüz yapılmamıştır.
            return False
    return row is not None


def pending_quarantine(db_path=None):
    """Kullanıcıya HENÜZ gösterilmemiş karantina kayıtları."""
    db_path = Path(db_path or _default_db_path())
    if not db_path.exists():
        return []
    with closing(_connect(db_path)) as conn:
        try:
            rows = conn.execute(
                "SELECT id, reason, source, legacy_id, goal_name,"
                " target_amount, current_amount, quarantined_at"
                " FROM savings_migration_quarantine"
                " WHERE acknowledged = 0 ORDER BY id"
            ).fetchall()
        except sqlite3.Error:
            return []
    return [_readable_quarantine_row(row) for row in rows]


def _readable_quarantine_row(row):
    name = row["goal_name"]
    if name:
        try:
            name = decrypt(name, SECRET_KEY)
        except (DecryptionError, KeyUnavailableError, ValueError, TypeError):
            name = "Bilinmeyen Hedef"
    return {
        "id": row["id"],
        "reason": row["reason"],
        "message": QUARANTINE_USER_MESSAGES.get(row["reason"], ""),
        "source": row["source"],
        "legacy_id": row["legacy_id"],
        "goal_name": name,
        "target_amount": row["target_amount"],
        "current_amount": row["current_amount"],
        "quarantined_at": row["quarantined_at"],
    }


def acknowledge_quarantine(db_path=None):
    """Karantina bildirimini "gösterildi" diye işaretler.

    Bildirim TEK SEFERLİKTİR ama kayıt SİLİNMEZ: kullanıcı daha sonra da
    hangi hedeflerin taşınamadığını görebilmeli.
    """
    db_path = Path(db_path or _default_db_path())
    if not db_path.exists():
        return 0
    with closing(_connect(db_path)) as conn:
        try:
            cursor = conn.execute(
                "UPDATE savings_migration_quarantine SET acknowledged = 1"
                " WHERE acknowledged = 0"
            )
        except sqlite3.Error:
            return 0
        conn.commit()
        return cursor.rowcount


# ── JSON okuma ────────────────────────────────────────────────────────────
def _parse_json_records(json_path: Path):
    """Kivy `JsonStore` dosyasından hedef listesini çıkarır.

    `JsonStore` biçimi: {"goals": {"data": [ ... ]}}. Kivy'ye BAĞIMLILIK YOK —
    bu modül UI'sız koşabilmeli.
    """
    raw = json_path.read_text(encoding="utf-8")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("beklenmeyen JSON kökü")
    goals = document.get("goals")
    if goals is None:
        return []
    if not isinstance(goals, dict):
        raise ValueError("beklenmeyen 'goals' bölümü")
    data = goals.get("data", [])
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("beklenmeyen 'data' bölümü")
    return data


def _record_fingerprint(index, record):
    """Kayıt-başına işaret anahtarı.

    İçeriğe VE sıraya bağlı: birbirinin tıpatıp aynısı iki kayıt varsa ikisi
    de ayrı ayrı işaretlenmeli, yoksa ikincisi "zaten uygulanmış" sanılıp
    sessizce düşerdi.
    """
    payload = json.dumps(
        [index, record], sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"record:{digest[:32]}"


def _coerce_record(record):
    """Ham JSON kaydını doğrular ve normalleştirir; olmuyorsa None döner."""
    if not isinstance(record, dict):
        return None
    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        target = float(fiat(record.get("target", 0) or 0))
        current = float(fiat(record.get("current", 0) or 0))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if target <= 0 or current < 0:
        return None
    legacy_id = record.get("id")
    if legacy_id is not None:
        try:
            legacy_id = int(legacy_id)
        except (TypeError, ValueError):
            return None
    color = record.get("color")
    if color is not None and not isinstance(color, str):
        color = None
    created_at = record.get("created_at")
    if created_at is not None and not isinstance(created_at, str):
        created_at = None
    return {
        "legacy_id": legacy_id,
        "name": name.strip(),
        "target": target,
        "current": current,
        "color": color,
        "auto_deposit": bool(record.get("auto_deposit", False)),
        "created_at": created_at,
    }


# ── Sınıflandırma ─────────────────────────────────────────────────────────
def _existing_goals(conn):
    rows = conn.execute(
        "SELECT id, goal_uid, goal_name, target_amount, current_amount,"
        " color, auto_deposit, created_at FROM savings_goals"
    ).fetchall()
    goals = []
    for row in rows:
        goals.append({
            "id": row["id"],
            "goal_uid": row["goal_uid"],
            "name": decrypt(row["goal_name"], SECRET_KEY),
            "target": float(row["target_amount"] or 0.0),
            "current": float(row["current_amount"] or 0.0),
            "color": row["color"],
            "auto_deposit": row["auto_deposit"],
            "created_at": row["created_at"],
        })
    return goals


def classify(records, existing):
    """Her JSON kaydını bir karara bağlar. SAF fonksiyon — I/O yok.

    Ayrı ve saf tutulması bilinçli: karar tablosu (plan §6) bu kod tabanındaki
    en riskli mantık ve yanlış bir karar kullanıcının parasını yanlış hedefe
    yazıyor. Saf olduğu için doğrudan, veritabanısız test edilebiliyor.
    """
    by_id = {goal["id"]: goal for goal in existing if goal["id"] is not None}
    name_amount_index: dict[tuple[str, float], list[dict]] = {}
    for goal in existing:
        name_amount_index.setdefault((goal["name"], round(goal["target"], 2)), []).append(goal)

    duplicated_ids = set()
    seen_ids = set()
    for record in records:
        legacy_id = record["legacy_id"]
        if legacy_id is None:
            continue
        if legacy_id in seen_ids:
            duplicated_ids.add(legacy_id)
        seen_ids.add(legacy_id)

    # (karar, kayıt, ek bilgi): ek bilgi MATCH'te eşleşen SQL satırı,
    # QUARANTINE'de gerekçe kodu, INSERT'te yok.
    decisions: list[tuple[str, dict, object]] = []
    for record in records:
        legacy_id = record["legacy_id"]
        key = (record["name"], round(record["target"], 2))

        if legacy_id is not None and legacy_id in duplicated_ids:
            decisions.append((DECISION_QUARANTINE, record, REASON_DUPLICATE_ID))
            continue

        candidate = by_id.get(legacy_id) if legacy_id is not None else None
        if candidate is not None:
            if candidate["name"] == record["name"]:
                # Kesin eşleşme: id VE ad birlikte tutuyor.
                decisions.append((DECISION_MATCH, record, candidate))
            else:
                # §1(b)'nin ürettiği tam durum: id yeniden kullanılmış.
                decisions.append(
                    (DECISION_QUARANTINE, record, REASON_ID_COLLISION))
            continue

        if name_amount_index.get(key):
            # Ad+tutar KANIT DEĞİLDİR: bu, id'si değişmiş AYNI hedef de
            # olabilir, aynı adla açılmış BAŞKA bir hedef de. Birleştirmek
            # birini yok eder, INSERT etmek diğerini ikiye böler. İkisi de
            # otomatik yapılamayacak kadar tehlikeli.
            decisions.append((DECISION_QUARANTINE, record, REASON_AMBIGUOUS))
            continue

        if record["current"] > 0:
            # Modül docstring'indeki gerekçe: karşılıksız para yoktan var
            # edilemez.
            decisions.append(
                (DECISION_QUARANTINE, record, REASON_UNMATCHED_WITH_BALANCE))
            continue

        decisions.append((DECISION_INSERT, record, None))
    return decisions


# ── Uygulama ──────────────────────────────────────────────────────────────
def _applied_markers(conn):
    rows = conn.execute(
        "SELECT marker FROM savings_migration_state WHERE marker LIKE 'record:%'"
    ).fetchall()
    return {row["marker"] for row in rows}


def _quarantine(conn, reason, source, record, raw):
    conn.execute(
        "INSERT INTO savings_migration_quarantine"
        " (quarantined_at, reason, source, legacy_id, goal_name,"
        "  target_amount, current_amount, payload, acknowledged)"
        " VALUES (?,?,?,?,?,?,?,?,0)",
        (
            datetime.now().isoformat(timespec="seconds"),
            reason,
            source,
            record.get("legacy_id") if record else None,
            encrypt(str(record["name"]), SECRET_KEY) if record else None,
            record.get("target") if record else None,
            record.get("current") if record else None,
            encrypt(
                json.dumps(raw, ensure_ascii=False, default=str), SECRET_KEY
            ),
        ),
    )


def _insert_goal(conn, record, taken_ids):
    """Yeni hedefi yazar. Mümkünse eski sayısal id KORUNUR.

    Eski id'yi korumak iki iş görüyor: (1) kullanıcının kendi dosyasındaki
    kimlik eşlemesi bozulmuyor, (2) `AUTOINCREMENT` sayacı o değerin ÜSTÜNE
    çıkıyor, yani aynı id bir daha dağıtılmıyor.
    """
    goal_uid = str(uuid.uuid4())
    columns = (
        "goal_name, target_amount, current_amount, target_date, status,"
        " goal_uid, color, auto_deposit, created_at"
    )
    values = (
        encrypt(record["name"], SECRET_KEY),
        record["target"],
        record["current"],
        None,
        "tamamlandi" if fiat(record["current"]) >= fiat(record["target"])
        else "aktif",
        goal_uid,
        record["color"],
        1 if record["auto_deposit"] else 0,
        record["created_at"],
    )
    legacy_id = record["legacy_id"]
    if legacy_id is not None and legacy_id not in taken_ids:
        conn.execute(
            f"INSERT INTO savings_goals (id, {columns})"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",  # nosec B608 - sabit sütun listesi
            (legacy_id, *values),
        )
        taken_ids.add(legacy_id)
    else:
        conn.execute(
            f"INSERT INTO savings_goals ({columns})"
            " VALUES (?,?,?,?,?,?,?,?,?)",  # nosec B608 - sabit sütun listesi
            values,
        )
    return goal_uid


def _complete_fields(conn, record, existing_goal):
    """Eşleşen satırın YALNIZ boş alanlarını doldurur.

    Tutarlara ve ada DOKUNMAZ. `auto_deposit` yalnız 0 -> 1 yönünde
    değişebilir: kullanıcının açtığı bir tercih, eski bir dosya yüzünden
    kapatılmamalı.
    """
    updates = []
    params = []
    if not existing_goal["color"] and record["color"]:
        updates.append("color = ?")
        params.append(record["color"])
    if not existing_goal["created_at"] and record["created_at"]:
        updates.append("created_at = ?")
        params.append(record["created_at"])
    if record["auto_deposit"] and not existing_goal["auto_deposit"]:
        updates.append("auto_deposit = 1")
    if not updates:
        return False
    params.append(existing_goal["id"])
    conn.execute(
        f"UPDATE savings_goals SET {', '.join(updates)} WHERE id = ?",  # nosec B608
        params,
    )
    return True


def _financial_fingerprint(conn):
    """Göçün DEĞİŞTİRMEMESİ gereken her şeyin özeti."""
    accounts = conn.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM accounts"
    ).fetchone()[0]
    events = conn.execute("SELECT COUNT(*) FROM balance_events").fetchone()[0]
    event_sum = conn.execute(
        "SELECT COALESCE(SUM(delta), 0) FROM balance_events"
    ).fetchone()[0]
    existing_total = conn.execute(
        "SELECT COALESCE(SUM(current_amount), 0) FROM savings_goals"
    ).fetchone()[0]
    return {
        "accounts_total": round(float(accounts or 0.0), 2),
        "balance_events": int(events),
        "balance_events_delta": round(float(event_sum or 0.0), 2),
        "savings_total": round(float(existing_total or 0.0), 2),
    }


def _safety_snapshot(db_path: Path) -> Path:
    """Göç ÖNCESİ veritabanının birebir kopyası.

    Parolalı `create_backup` KULLANILMIYOR — o kurtarma parolası ister ve bu
    göç açılışta, kullanıcıya hiçbir şey sormadan koşuyor. Kopya SQLite'ın
    kendi online-backup API'siyle alınıyor (dosyayı kopyalamak, açık bir WAL
    varken tutarsız bir kopya üretebilirdi) ve şifreleme anahtarını İÇERMEZ:
    içeriği canlı veritabanının aynısı, aynı dizinde ve aynı korumada.
    """
    target = db_path.with_name(
        f"{db_path.name}.pre-savings-migration-{_timestamp()}"
    )
    counter = 1
    while target.exists():
        target = db_path.with_name(f"{target.name}-{counter}")
        counter += 1
    with closing(sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(str(target))) as destination:
            source.backup(destination)
    try:
        os.chmod(target, 0o600)
    except OSError:
        # Windows'ta chmod'un karşılığı sınırlı; kopya zaten kullanıcı veri
        # dizininde ve canlı veritabanıyla aynı korumada.
        pass
    return target


def _outcome(status, **extra):
    result = {
        "status": status,
        "inserted": 0,
        "completed": 0,
        "quarantined": 0,
        "skipped": 0,
    }
    result.update(extra)
    return result


def run_savings_migration(*, json_path=None, db_path=None, _failure_hook=None):
    """JSON hedeflerini SQLite'a taşır. Modül docstring'indeki sözleşmeyle.

    `_failure_hook` testlerin her kritik aşamada kesinti enjekte etmesi için;
    üretimde `None` (restore'daki `_failure_hook` ile aynı desen).
    """
    db_path = Path(db_path or _default_db_path())
    json_path = Path(json_path) if json_path else savings_json_path(db_path.parent)

    if not db_path.exists():
        # Şema hiç kurulmamış: göç kendi başına veritabanı yaratmaz.
        return _outcome("no-database")

    # YARIM KALMIŞ BİR KOŞUMU TAMAMLA. Kayıtlar commit edilmiş ve JSON
    # emekliye ayrılmış ama nihai işaret yazılamadan süreç ölmüşse, dosya
    # ortada olmadığı için normal akış "yapacak bir şey yok" derdi ve işaret
    # SONSUZA KADAR eksik kalırdı. O profil, ileride ortaya çıkan bayat bir
    # JSON'u legacy sanıp göç ettirirdi — tam da engellemeye çalıştığımız şey.
    journal = read_journal(db_path)
    if (
        journal
        and journal.get("state") in (STATE_APPLIED, STATE_VERIFIED, STATE_RETIRED)
        and not json_path.exists()
        and not migration_completed(db_path)
    ):
        return _retire(db_path, json_path, _outcome("resumed"), _failure_hook)

    if not json_path.exists():
        return _outcome("no-json")

    # BAYAT JSON KURALI. İşaret veritabanının İÇİNDE olduğu için DB
    # generation'ıyla taşınıyor: işaret varken ortaya çıkan bir JSON, restore
    # sonrasında geride kalmış bayat bir dosyadır. Onu göç ettirmek, tam da
    # düzeltmeye çalıştığımız "bayat kayıt güncel veriyle karışıyor" kusurunu
    # geri getirirdi.
    if migration_completed(db_path):
        return _quarantine_stale_json(json_path, db_path, _failure_hook)

    try:
        raw_records = _parse_json_records(json_path)
    except (OSError, UnicodeError, ValueError):
        return _quarantine_unreadable_json(json_path, db_path, _failure_hook)

    _write_journal(db_path, STATE_READ, {"records": len(raw_records)})

    records = []
    invalid = []
    for index, raw in enumerate(raw_records):
        coerced = _coerce_record(raw)
        if coerced is None:
            invalid.append((index, raw))
        else:
            records.append((index, coerced, raw))

    if not records and not invalid:
        # Dosya var ama içi boş: taşınacak bir şey yok. Yine de EMEKLİYE
        # ayrılır, yoksa her açılışta aynı boş dosya yeniden değerlendirilir.
        return _retire(db_path, json_path, _outcome("empty"), _failure_hook)

    try:
        # Anahtarı ÖNCE dene. SQL'de hiç hedef yoksa hiçbir çözme yapılmaz ve
        # arıza ilk YAZIMDA, yani transaction'ın ortasında patlardı. Fail-closed
        # olması gereken bir durumun yarım bir göçe dönüşmesi demekti.
        encrypt("anahtar-denemesi", SECRET_KEY)
        with closing(_connect(db_path)) as conn:
            existing = _existing_goals(conn)
            before = _financial_fingerprint(conn)
            applied = _applied_markers(conn)
            taken_ids = {goal["id"] for goal in existing}
    except KeyUnavailableError:
        # Anahtar yoksa hedef adları çözülemez, yani eşleştirme yapılamaz.
        # Fail-closed: hiçbir karar verilmez, JSON'a dokunulmaz, işaret
        # yazılmaz. Sonraki açılış yeniden dener.
        _write_journal(db_path, STATE_READ, {"aborted": "key-unavailable"})
        return _outcome("key-unavailable")
    except (DecryptionError, ValueError, TypeError) as exc:
        raise SavingsMigrationError(
            "Mevcut hedef adları çözülemedi; göç durduruldu."
        ) from exc

    decisions = classify([record for _, record, _ in records], existing)
    plan = [
        (index, record, raw, decision, payload)
        for (index, record, raw), (decision, _, payload)
        in zip(records, decisions)
    ]
    _write_journal(db_path, STATE_PLANNED, {
        "insert": sum(1 for item in plan if item[3] == DECISION_INSERT),
        "match": sum(1 for item in plan if item[3] == DECISION_MATCH),
        "quarantine": sum(1 for item in plan if item[3] == DECISION_QUARANTINE)
        + len(invalid),
    })

    snapshot = _safety_snapshot(db_path)
    if _failure_hook:
        _failure_hook("after_safety_snapshot")

    result = _outcome("migrated", safety_snapshot=str(snapshot))
    conn = _connect(db_path)
    # `except Exception` YOK, `try/finally` VAR. Buradaki tek gereksinim
    # "commit edilmediyse geri al ve bağlantıyı kapat" — bunu geniş bir
    # handler'la yazmak, kesinti enjeksiyonunun fırlattığı türden yabancı
    # istisnaları da yutma iznini beraberinde getirirdi. finally her çıkış
    # yolunda çalışır ve istisnayı olduğu gibi dışarı bırakır; Windows'ta
    # kapatılmayan bir bağlantı finance.db üzerinde kilit demek.
    committed = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        for index, raw in invalid:
            marker = _record_fingerprint(index, raw)
            if marker in applied:
                result["skipped"] += 1
                continue
            _quarantine(conn, REASON_INVALID, "legacy-json", None, raw)
            _mark_record(conn, marker, REASON_INVALID)
            result["quarantined"] += 1

        if _failure_hook:
            _failure_hook("after_invalid_records")

        for index, record, raw, decision, payload in plan:
            marker = _record_fingerprint(index, raw)
            if marker in applied:
                result["skipped"] += 1
                continue
            if decision == DECISION_INSERT:
                _insert_goal(conn, record, taken_ids)
                result["inserted"] += 1
                _mark_record(conn, marker, DECISION_INSERT)
            elif decision == DECISION_MATCH:
                if _complete_fields(conn, record, payload):
                    result["completed"] += 1
                _mark_record(conn, marker, DECISION_MATCH)
            else:
                _quarantine(conn, payload, "legacy-json", record, raw)
                result["quarantined"] += 1
                _mark_record(conn, marker, payload)

        if _failure_hook:
            _failure_hook("before_commit")
        conn.commit()
        committed = True
    finally:
        if not committed:
            conn.rollback()
        conn.close()

    _write_journal(db_path, STATE_APPLIED, result)
    if _failure_hook:
        _failure_hook("after_commit")

    _verify(db_path, before, result)
    _write_journal(db_path, STATE_VERIFIED, result)
    if _failure_hook:
        _failure_hook("after_verification")

    return _retire(db_path, json_path, result, _failure_hook)


def _mark_record(conn, marker, detail):
    """Kayıt-başına "uygulandı" işareti — INSERT'lerle AYNI transaction'da.

    Bu satır olmadan, commit ile emeklilik arasında çöken bir süreç bir
    sonraki açılışta AYNI kayıtları ikinci kez taşırdı.
    """
    conn.execute(
        "INSERT OR IGNORE INTO savings_migration_state"
        " (marker, completed_at, detail) VALUES (?,?,?)",
        (marker, datetime.now().isoformat(timespec="seconds"), str(detail)),
    )


def _verify(db_path, before, result):
    """Göçün DEĞİŞTİRMEMESİ gerekenleri ölçer.

    Bir sapma bulursa `SavingsMigrationError` fırlatır ve göç EMEKLİYE
    AYRILMAZ: JSON yerinde kalır, işaret yazılmaz. Böylece durum elle
    incelenebilir ve hiçbir veri kaybolmaz.
    """
    with closing(_connect(db_path)) as conn:
        after = _financial_fingerprint(conn)
        missing_uid = conn.execute(
            "SELECT COUNT(*) FROM savings_goals WHERE goal_uid IS NULL"
        ).fetchone()[0]

    if after["accounts_total"] != before["accounts_total"]:
        raise SavingsMigrationError("Göç hesap bakiyelerini değiştirdi.")
    if after["balance_events"] != before["balance_events"]:
        raise SavingsMigrationError("Göç defter satırı yazdı.")
    if after["balance_events_delta"] != before["balance_events_delta"]:
        raise SavingsMigrationError("Göç defter toplamını değiştirdi.")
    if after["savings_total"] != before["savings_total"]:
        # INSERT edilen kayıtların birikimi tanım gereği 0 (bkz. modül
        # docstring'i); toplam değiştiyse para yoktan var edilmiş demektir.
        raise SavingsMigrationError("Göç birikim toplamını değiştirdi.")
    if missing_uid:
        raise SavingsMigrationError("Göç sonrası kimliksiz hedef kaldı.")


def _retire(db_path, json_path, result, _failure_hook=None):
    """JSON'u emekliye ayırır ve nihai işareti yazar. SIRA ÖNEMLİ.

    Önce dosya taşınır, SONRA işaret yazılır. Ters sırada, iki adım arasında
    çöken bir süreç "göç tamamlandı" diyen bir işaretle ve hâlâ yerinde duran
    bir JSON'la kalırdı; bir sonraki açılış o dosyayı BAYAT sanıp karantinaya
    alır ve kullanıcıya gereksiz bir uyarı gösterirdi.
    """
    retired = None
    if json_path.exists():
        retired = _retire_path(json_path, "migrated")
        os.replace(json_path, retired)
        result["retired_path"] = str(retired)
    if _failure_hook:
        _failure_hook("after_json_retired")

    with closing(_connect(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO savings_migration_state"
            " (marker, completed_at, detail) VALUES (?,?,?)",
            (
                MIGRATION_MARKER,
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(
                    {
                        "inserted": result["inserted"],
                        "completed": result["completed"],
                        "quarantined": result["quarantined"],
                        "retired_path": str(retired) if retired else None,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    _write_journal(db_path, STATE_RETIRED, {"retired_path": str(retired)})
    if _failure_hook:
        _failure_hook("after_marker_written")
    _clear_journal(db_path)
    return result


def _quarantine_stale_json(json_path: Path, db_path: Path, _failure_hook=None):
    """Restore sonrası geride kalmış JSON: göç YOK, karantina VAR."""
    try:
        raw_records = _parse_json_records(json_path)
    except (OSError, UnicodeError, ValueError):
        raw_records = []

    result = _outcome("stale-json")
    with closing(_connect(db_path)) as conn:
        for raw in raw_records:
            record = _coerce_record(raw)
            _quarantine(conn, REASON_STALE_JSON, "stale-json", record, raw)
            result["quarantined"] += 1
        conn.commit()
    if _failure_hook:
        _failure_hook("after_stale_quarantine_rows")

    retired = _retire_path(json_path, "stale")
    os.replace(json_path, retired)
    result["retired_path"] = str(retired)
    _write_journal(db_path, STATE_RETIRED, {"stale_path": str(retired)})
    _clear_journal(db_path)
    return result


def _quarantine_unreadable_json(json_path: Path, db_path: Path,
                                _failure_hook=None):
    """Bozuk/kısmi JSON: KISMİ GÖÇ YOK.

    Dosyanın içeriği karantina satırına KOPYALANMAZ — okunamadığı için
    anlamlı bir kayda dönüştürülemez ve ne olduğu bilinmeyen ham veriyi
    veritabanına taşımak yeni bir sorun olurdu. Dosyanın kendisi
    `.unreadable-<zaman>` olarak olduğu gibi saklanır; karantina satırı ona
    işaret eder.
    """
    detail: dict[str, object] = {"file": json_path.name}
    try:
        detail["bytes"] = json_path.stat().st_size
    except OSError:
        detail["bytes"] = None

    retired = _retire_path(json_path, "unreadable")
    os.replace(json_path, retired)
    detail["stored_as"] = retired.name
    if _failure_hook:
        _failure_hook("after_unreadable_moved")

    with closing(_connect(db_path)) as conn:
        _quarantine(conn, REASON_UNREADABLE_FILE, "legacy-json", None, detail)
        conn.commit()
    result = _outcome("unreadable-json", quarantined=1,
                      retired_path=str(retired))
    _write_journal(db_path, STATE_RETIRED, detail)
    _clear_journal(db_path)
    return result
