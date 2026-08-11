"""Faz 2 zaman makinesi: geçmiş bir tarihteki bakiyeyi defterden yeniden kurar.

ÇALIŞMA MANTIĞI
---------------
İki kaynak birlikte kullanılır:

  * `daily_balance_snapshot` — günde bir kez yazılan toplam (hızlı başlangıç),
  * `balance_events`         — her bakiye değişikliğinin işaretli kaydı.

`get_balance_at(date)` istenen tarihe eşit/ondan küçük EN YAKIN snapshot'ı
bulur, sonra yalnızca o snapshot ile hedef tarih arasındaki olayları oynatır.
Snapshot yoksa defterin başından replay eder. Böylece maliyet, geçmişe gidilen
mesafeyle değil son snapshot'tan bu yana biriken olay sayısıyla orantılı kalır.

NEDEN ŞİFRE ÇÖZME YOK
---------------------
insights_service'in aksine burada decrypt gerekmiyor: `balance_events.delta`
ve `accounts.balance` düz REAL. Defterin düz tutulmasının sebebi tam olarak bu —
replay her satırı AES ile çözmek zorunda kalsaydı uzun geçmişlerde
kullanılamazdı (bkz. init_db.py'deki balance_events şema notu).

İŞARET KONVANSİYONU
-------------------
`entity_type='account'` olaylarının deltası doğrudan toplam bakiyeye işler.
`entity_type='savings_goal'` olayları toplam bakiyeye İŞLEMEZ: hedefe para
aktarımı zaten hesap tarafında bir çıkış olayı üretiyor, ikisini de toplamak
parayı iki kez saydırırdı. Hedef olayları ayrı bir `savings_total` altında
izlenir.
"""

import json
import sqlite3
from datetime import datetime

from database.db import get_connection

ACCOUNT = "account"
SAVINGS_GOAL = "savings_goal"


def _normalize_date(value):
    """date/datetime/str girdisini 'YYYY-MM-DD' biçimine indirger."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def _day_end(date_str):
    """Gün sonu sınırı: o günün TÜM olayları dahil edilsin.

    `ts` 'YYYY-MM-DD HH:MM:SS' biçiminde saklandığı için düz metin
    karşılaştırması kronolojik sırayla aynıdır; '<= tarih 23:59:59' demek
    o günü tamamen kapsamak demektir.
    """
    return f"{date_str} 23:59:59"


# ── Snapshot yazımı ────────────────────────────────────────────────────────

def _compute_current_totals(cursor):
    """Şu anki hesap toplamı ve hesap/hedef dökümü."""
    cursor.execute("SELECT id, balance FROM accounts")
    accounts = {str(r["id"]): (r["balance"] or 0.0) for r in cursor.fetchall()}
    try:
        cursor.execute("SELECT id, current_amount FROM savings_goals")
        goals = {str(r["id"]): (r["current_amount"] or 0.0) for r in cursor.fetchall()}
    except sqlite3.Error:
        # savings_goals eski bir DB'de henüz mevcut olmayabilir — DB
        # hatası kategorisi, decrypt ile ilgisi yok (bkz. docs/ROADMAP.md
        # Faz 2 "except ayrımı").
        goals = {}
    return sum(accounts.values()), accounts, goals


def write_daily_snapshot(force=False):
    """Bugün için bir snapshot yazar; aynı gün ikinci kez yazmaz.

    `snapshot_date` UNIQUE olduğu için tekrar yazım zaten reddedilirdi; yine de
    açıkça kontrol ediyoruz ki `force=True` ile bilinçli güncelleme mümkün olsun
    (gün içinde snapshot'ı tazelemek isteyen bir çağıran için).

    Döner: yazıldıysa snapshot dict'i, o gün zaten varsa None.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM daily_balance_snapshot WHERE snapshot_date = ?", (today,)
        )
        existing = cursor.fetchone()
        if existing and not force:
            return None

        total, accounts, goals = _compute_current_totals(cursor)
        breakdown = json.dumps(
            {"accounts": accounts, "savings_goals": goals}, ensure_ascii=False
        )

        if existing:
            cursor.execute(
                "UPDATE daily_balance_snapshot SET total_balance = ?, breakdown_json = ?"
                " WHERE snapshot_date = ?",
                (total, breakdown, today),
            )
        else:
            cursor.execute(
                "INSERT INTO daily_balance_snapshot (snapshot_date, total_balance, breakdown_json)"
                " VALUES (?, ?, ?)",
                (today, total, breakdown),
            )
        conn.commit()
        return {"snapshot_date": today, "total_balance": total,
                "breakdown": {"accounts": accounts, "savings_goals": goals}}
    finally:
        conn.close()


# ── Geçmişe bakış ──────────────────────────────────────────────────────────

def ledger_start_date(cursor=None):
    """Defterdeki en eski olayın tarihi ('YYYY-MM-DD') ya da defter boşsa None.

    Bu tarihten önceki sorgular cevaplanamaz: uygulama Faz 2'den önce bakiye
    hareketi kaydetmiyordu, o dönem için elimizde veri YOK. Sıfır döndürmek
    "hiç paranız yoktu" demek olurdu — bu yanlış olurdu.
    """
    # SAHİPLİK AÇIK YAZILIYOR. Eskiden `own = cursor is None` bayrağı ve
    # `conn = get_connection() if own else None` ile kuruluyordu; çalışma
    # zamanında doğruydu (bayrak ile `conn is not None` birebir korele) ama
    # ilişkiyi yalnız insan görebiliyordu. İki dalı ayırmak aynı davranışı
    # veriyor ve bağlantıyı kimin kapattığını okunur kılıyor.
    if cursor is None:
        conn = get_connection()
        try:
            return _ledger_start_date(conn.cursor())
        finally:
            conn.close()
    return _ledger_start_date(cursor)


def _ledger_start_date(cursor):
    """Sorgunun kendisi — bağlantı sahipliğinden bağımsız."""
    cursor.execute("SELECT MIN(ts) AS first_ts FROM balance_events")
    row = cursor.fetchone()
    first = row["first_ts"] if row else None
    return first[:10] if first else None


def _latest_snapshot_on_or_before(cursor, date_str):
    cursor.execute(
        "SELECT snapshot_date, total_balance, breakdown_json"
        " FROM daily_balance_snapshot WHERE snapshot_date <= ?"
        " ORDER BY snapshot_date DESC LIMIT 1",
        (date_str,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    try:
        breakdown = json.loads(row["breakdown_json"]) if row["breakdown_json"] else {}
    except (json.JSONDecodeError, TypeError):
        breakdown = {}
    return {
        "snapshot_date": row["snapshot_date"],
        "total_balance": row["total_balance"] or 0.0,
        "breakdown": breakdown,
    }


def get_balance_at(date):
    """Verilen tarihin SONUNDAKİ bakiyeyi döndürür.

    Döner:
        {
          "date": "YYYY-MM-DD",
          "total_balance": float,     # hesapların toplamı
          "savings_total": float,     # birikim hedeflerindeki toplam
          "basis": "snapshot" | "replay",
          "snapshot_date": str | None,
          "events_replayed": int,
        }
    """
    date_str = _normalize_date(date)
    boundary = _day_end(date_str)

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Defter başlamadan önceki bir tarih soruluyorsa dürüst cevap "bilmiyorum".
        start = ledger_start_date(cursor)
        if start is not None and date_str < start:
            return {
                "date": date_str,
                "total_balance": None,
                "savings_total": None,
                "basis": "before_ledger",
                "snapshot_date": None,
                "events_replayed": 0,
                "ledger_start": start,
            }

        snapshot = _latest_snapshot_on_or_before(cursor, date_str)

        if snapshot:
            total = snapshot["total_balance"]
            savings = sum(
                float(v) for v in (snapshot["breakdown"].get("savings_goals") or {}).values()
            )
            # Snapshot o günün SONU değil, yazıldığı AN'ı temsil eder; bu yüzden
            # snapshot gününün olaylarını da replay'e dahil etmek çift sayıma
            # yol açardı. Sınırı snapshot gününün sonundan başlatıyoruz.
            lower = _day_end(snapshot["snapshot_date"])
            basis = "snapshot"
        else:
            total = 0.0
            savings = 0.0
            lower = ""            # defterin başı
            basis = "replay"

        cursor.execute(
            "SELECT entity_type, delta FROM balance_events"
            " WHERE ts > ? AND ts <= ? ORDER BY ts ASC, id ASC",
            (lower, boundary),
        )
        rows = cursor.fetchall()
        for r in rows:
            if r["entity_type"] == ACCOUNT:
                total += r["delta"] or 0.0
            elif r["entity_type"] == SAVINGS_GOAL:
                savings += r["delta"] or 0.0

        return {
            "date": date_str,
            "total_balance": round(total, 2),
            "savings_total": round(savings, 2),
            "basis": basis,
            "snapshot_date": snapshot["snapshot_date"] if snapshot else None,
            "events_replayed": len(rows),
            "ledger_start": start,
        }
    finally:
        conn.close()


def diff_between(date_a, date_b):
    """İki tarih arasındaki değişimi ve onu oluşturan olayları özetler.

    `date_a` dışlayıcıdır (o günün sonundan itibaren), `date_b` kapsayıcıdır —
    yani "a'dan b'ye ne oldu" sorusunun doğal karşılığı.

    Döner:
        {
          "from", "to",
          "balance_from", "balance_to", "balance_change",
          "savings_from", "savings_to", "savings_change",
          "by_source": {kaynak: {"delta": float, "count": int}},
          "event_count": int,
        }
    """
    a = _normalize_date(date_a)
    b = _normalize_date(date_b)
    if a > b:
        a, b = b, a

    start = get_balance_at(a)
    end = get_balance_at(b)

    # Başlangıç tarihi defterden eskiyse DEĞİŞİM HESAPLANAMAZ: karşılaştırma
    # noktası yok.
    #
    # Aralığı defterin başlangıcına "kırpmak" cazip ama yanlış olurdu — o
    # durumda defterin ilk günündeki hareketler başlangıç durumunun içinde
    # kalır ve değişim olarak sayılmaz. Uydurma bir karşılaştırma noktası
    # üretmek yerine değişimi None bırakıyoruz; bildiğimiz hareketleri
    # (by_source) yine gösteriyoruz, çağıran `truncated` ile durumu anlatır.
    truncated = start["basis"] == "before_ledger"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT source, entity_type, delta FROM balance_events"
            " WHERE ts > ? AND ts <= ? ORDER BY ts ASC, id ASC",
            (_day_end(a), _day_end(b)),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    by_source: dict[str, dict[str, float]] = {}
    for r in rows:
        # Kaynak kırılımı hesap tarafına bakar: "bu dönemde parayı ne hareket
        # ettirdi" sorusunun cevabı hesap deltalarıdır (hedef olayları aynı
        # hareketin diğer ucu, tekrar saymamak için dışarıda).
        if r["entity_type"] != ACCOUNT:
            continue
        key = r["source"] or "bilinmiyor"
        bucket = by_source.setdefault(key, {"delta": 0.0, "count": 0})
        bucket["delta"] += r["delta"] or 0.0
        bucket["count"] += 1
    for bucket in by_source.values():
        bucket["delta"] = round(bucket["delta"], 2)

    return {
        "from": a,
        "to": b,
        "balance_from": start["total_balance"],
        "balance_to": end["total_balance"],
        "balance_change": (
            None if truncated
            else round(end["total_balance"] - start["total_balance"], 2)
        ),
        "savings_from": start["savings_total"],
        "savings_to": end["savings_total"],
        "savings_change": (
            None if truncated
            else round(end["savings_total"] - start["savings_total"], 2)
        ),
        "by_source": by_source,
        "event_count": len(rows),
        # True ise istenen başlangıç tarihi defterden eskiydi ve aralık
        # defterin başlangıcına kırpıldı.
        "truncated": truncated,
        "ledger_start": end.get("ledger_start"),
    }


def get_recent_events(limit=50):
    """Defterin son N satırı (geçmiş diyaloğunun listesi için)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ts, entity_type, entity_id, delta, resulting_value, source, ref_id"
            " FROM balance_events ORDER BY ts DESC, id DESC LIMIT ?",
            (int(limit),),
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
