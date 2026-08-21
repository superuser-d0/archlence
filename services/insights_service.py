"""Faz 1 içgörü motoru: abonelik radarı, anomali tespiti, finansal sağlık skoru.

ŞİFRELEME KISITI (bu dosyanın tüm şeklini belirleyen kural)
-----------------------------------------------------------
`transactions.amount` ve `transactions.description` AES-256-CBC ile şifreli
TEXT olarak saklanır (bkz. utils/crypto.py). Bu yüzden SQL tarafında
SUM/AVG/window function ile istatistik ÇIKARILAMAZ — şifreli metnin toplamı
anlamsızdır. main.py::update_metrics_and_goals ve generate_financial_advice
ile aynı deseni izliyoruz:

    satırları çek  ->  Python'da decrypt et  ->  Python'da hesapla

`category`, `type` ve `transaction_date` DÜZ tutulur; bu yüzden tarih aralığı
ve kategori filtrelemesi SQL'de yapılabilir (ve yapılır) — yalnızca sayısal
toplama Python'a taşınır.

Servis UI'dan bağımsızdır: hiçbir fonksiyon Kivy'ye dokunmaz, hepsi düz dict
döndürür. Arayüze bağlanması mixins/insights_mixin.py'nin işidir.
"""

import json
import sqlite3
from typing import Any
import statistics
from datetime import datetime, timedelta

from database.db import COMPLETED_TX, get_connection, managed_connection, SECRET_KEY
from utils.crypto import decrypt


AMOUNT_TOLERANCE = 0.10          # %10

MIN_OCCURRENCES = 3


MAX_INTERVAL_CV = 0.35

_FREQUENCY_BUCKETS = [
    ("weekly", 7, 3),
    ("biweekly", 14, 4),
    ("monthly", 30, 8),
    ("quarterly", 90, 15),
    ("yearly", 365, 40),
]


_EXPENSE_TYPES = ("expense", "Gider")
_INCOME_TYPES = ("income", "Gelir")


def _safe_decrypt_float(value, record_id=None):
    """Decode an amount or invalidate the complete insight result."""
    from services.financial_summary_service import decrypt_decimal

    return float(decrypt_decimal(
        value, table="transactions", record_id=record_id
    ))


def _safe_decrypt_text(value, record_id=None, table="transactions"):
    """Decode text or identify the exact unreadable contributing record."""
    from utils.errors import (
        DecryptionError,
        FinancialDataIntegrityError,
        KeyUnavailableError,
    )

    try:
        return decrypt(str(value), SECRET_KEY) or ""
    except KeyUnavailableError:
        raise
    except (DecryptionError, ValueError, TypeError) as exc:
        raise FinancialDataIntegrityError(
            table, record_id, "description", reason=exc
        ) from exc


def _parse_date(raw):
    """`transaction_date` metnini date'e çevirir; tanınmazsa None.

    Kayıtlar hem "%Y-%m-%d %H:%M:%S" hem de yalnız "%Y-%m-%d" biçiminde
    olabiliyor (mock veri ve CSV migration ikincisini üretiyor).
    """
    if not raw:
        return None
    text = str(raw).strip()
    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:width], fmt).date()
        except ValueError:
            continue
    return None


def normalize_name(text):
    """Açıklamayı karşılaştırılabilir bir ada indirger.

    "NETFLIX.COM 12/2026", "Netflix   Abonelik" ve "netflix" aynı adaya
    düşsün diye: küçük harf, noktalama -> boşluk, rakam/sık ekler atılır.
    """
    if not text:
        return ""
    lowered = str(text).lower()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in lowered)
    tokens = [t for t in cleaned.split() if t and not t.isdigit() and len(t) > 2]


    tokens = [t for t in tokens if t not in ("otomatik", "odeme", "ödeme")]
    return " ".join(tokens[:3])


def candidate_key(category, name):
    """Bir aday için kararlı anahtar — dismissal tablosu bunu saklar.

    Kategori düz, ad normalize edilmiş: kullanıcı "Netflix"i reddettiğinde
    tutarı değişse bile bir daha önerilmemeli.
    """
    return f"{(category or '').strip().lower()}|{normalize_name(name)}"


def _load_transactions(lookback_days, types, decrypt_description=True):
    """İşlemleri çeker ve tutar/açıklamayı Python'da çözer.

    Tarih ve tür filtresi SQL'de (o sütunlar düz), toplama Python'da.

    `decrypt_description=False` ile açıklama sütunu ÇÖZÜLMEZ ve `None` kalır.
    NEDEN (ölçüldü, 10K işlem): açıklama çözümü bu fonksiyonun maliyetinin
    ~yarısı (687 ms → 369 ms, 1.9x). Skor ve öngörü yolları yalnızca tutar
    ve tarih kullanıyor; onlar için AES işi tamamen boşa gidiyordu. Abonelik
    radarı ve anomali tespiti açıklamaya İHTİYAÇ DUYAR (adayı ondan türetir),
    o yüzden varsayılan `True` — sessizce boş açıklama görmesinler.
    """
    with managed_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in types)


        cursor.execute(
            f"""
            SELECT id, amount, type, category, description, transaction_date
            FROM transactions
            WHERE type IN ({placeholders})
              AND date(transaction_date) >= date('now', ?, 'localtime')
              AND {COMPLETED_TX}
            ORDER BY transaction_date ASC
            """,
            (*types, f"-{int(lookback_days)} days"),
        )
        rows = cursor.fetchall()

    records = []
    for r in rows:
        parsed = _parse_date(r["transaction_date"])
        if parsed is None:
            continue
        records.append({
            "id": r["id"],
            "amount": _safe_decrypt_float(r["amount"], r["id"]),
            "type": r["type"],
            "category": r["category"] or "Diğer",
            "description": (
                _safe_decrypt_text(r["description"], r["id"])
                if decrypt_description else None
            ),
            "date": parsed,
        })
    return records


def _dismissed_keys():
    """Kullanıcının 'bu abonelik değil' dediği adayların anahtarları."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT candidate_key FROM recurring_candidate_dismissals")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.Error:


        return set()
    finally:
        conn.close()


def _tracked_names():
    """Aktif recurring_payments kayıtlarının normalize edilmiş adları.

    database.db::has_active_recurring_payment ile aynı mantık — isimler
    şifreli olduğu için SQL WHERE ile aranamaz, aktif kayıtlar çözülüp
    Python'da karşılaştırılır. Farkı: birebir eşitlik yerine normalize
    edilmiş ad kullanılır, çünkü aday adı işlem açıklamasından türetiliyor
    ("NETFLIX.COM 12/26" vs "Netflix").

    Aday başına değil, tarama başına BİR kez çağrılır: her çağrı tüm aktif
    aboneliklerin adını decrypt ediyor, aday sayısı kadar tekrarlamak
    gereksiz AES işi olurdu.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name FROM recurring_payments WHERE is_active = 1"
        )
        rows = cursor.fetchall()
    except sqlite3.Error:


        raise
    finally:
        conn.close()

    names = {
        normalize_name(
            _safe_decrypt_text(
                r["name"],
                r["id"],
                "recurring_payments",
            )
        )
        for r in rows
    }
    return {n for n in names if n}


def _matches_tracked(name, tracked):
    """Aday adı, takip edilen adlardan biriyle çakışıyor mu?"""
    target = normalize_name(name)
    if not target:
        return False
    return any(
        existing == target or existing in target or target in existing
        for existing in tracked
    )


def _classify_frequency(mean_interval):
    """Ortalama gün aralığını insan-okunur sıklığa çevirir."""
    for label, expected, tolerance in _FREQUENCY_BUCKETS:
        if abs(mean_interval - expected) <= tolerance:
            return label
    return "irregular"


def detect_recurring_candidates(lookback_days=180):
    """Manuel eklenmemiş, tekrarlayan gider kalıplarını bulur.

    Aday olma koşulları (hepsi birden):
      * aynı kategori + benzer açıklama ile en az MIN_OCCURRENCES kez görülmüş,
      * tutarlar birbirine %AMOUNT_TOLERANCE içinde yakın,
      * görülme aralıkları düzenli (varyasyon katsayısı <= MAX_INTERVAL_CV),
      * recurring_payments'ta zaten aktif DEĞİL,
      * kullanıcı tarafından reddedilmemiş.

    Döner: [{name, category, average_amount, frequency, occurrences,
             last_seen, average_interval_days, monthly_cost, key}, ...]
    en pahalıdan ucuza sıralı.
    """
    records = _load_transactions(lookback_days, _EXPENSE_TYPES)


    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        if rec["amount"] <= 0:
            continue
        name = normalize_name(rec["description"])
        if not name:
            continue
        groups.setdefault((rec["category"], name), []).append(rec)

    dismissed = _dismissed_keys()
    tracked = _tracked_names()
    candidates = []

    for (category, name), items in groups.items():
        if len(items) < MIN_OCCURRENCES:
            continue

        amounts = [i["amount"] for i in items]
        mean_amount = statistics.fmean(amounts)
        if mean_amount <= 0:
            continue


        if max(abs(a - mean_amount) for a in amounts) > mean_amount * AMOUNT_TOLERANCE:
            continue

        dates = sorted(i["date"] for i in items)
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        intervals = [d for d in intervals if d > 0]
        if len(intervals) < MIN_OCCURRENCES - 1:
            continue

        mean_interval = statistics.fmean(intervals)
        if mean_interval <= 0:
            continue

        spread = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
        if spread / mean_interval > MAX_INTERVAL_CV:
            continue

        frequency = _classify_frequency(mean_interval)
        if frequency == "irregular":
            continue

        key = candidate_key(category, name)
        if key in dismissed:
            continue
        if _matches_tracked(name, tracked):
            continue

        candidates.append({
            "key": key,
            "name": name.title(),
            "category": category,
            "average_amount": round(mean_amount, 2),
            "frequency": frequency,
            "occurrences": len(items),
            "last_seen": dates[-1].isoformat(),
            "average_interval_days": round(mean_interval, 1),


            "monthly_cost": round(mean_amount * (30.0 / mean_interval), 2),

            "next_due_date": (
                dates[-1] + timedelta(days=int(round(mean_interval)))
            ).isoformat(),


            "can_track": frequency in {
                "weekly", "biweekly", "monthly", "quarterly", "yearly",
            },
        })

    candidates.sort(key=lambda c: c["monthly_cost"], reverse=True)
    return candidates


def dismiss_recurring_candidate(key):
    """Bir adayı kalıcı olarak reddeder (radar bir daha önermez)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recurring_candidate_dismissals (candidate_key, dismissed_at) VALUES (?, ?)",
            (key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()


# ── 2. Anomali tespiti ─────────────────────────────────────────────────────

def _dismissed_anomaly_ids():
    """Kullanıcının gördüm/gizle dediği transaction kimlikleri."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT transaction_id FROM anomaly_dismissals")
        return {row["transaction_id"] for row in cursor.fetchall()}
    finally:
        conn.close()


def dismiss_anomaly(transaction_id):
    """Bir anomalinin kaynak işlemini kalıcı olarak gizler (idempotent)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO anomaly_dismissals "
            "(transaction_id, dismissed_at) VALUES (?, ?)",
            (int(transaction_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()


def detect_anomalies(lookback_days=90, z_threshold=2.0):
    """Kategori bazında olağandışı büyük harcamaları işaretler.

    Her kategori için ortalama ve standart sapma Python'da hesaplanır; z-skoru
    eşiği aşan işlemler anomali sayılır. Yalnızca ÜSTE doğru sapmalar
    işaretlenir — normalden ucuz bir market alışverişi uyarı değildir.

    En az 3 işlemi olmayan kategoriler atlanır: iki noktadan sapma çıkarmak
    istatistiksel olarak anlamsız, kullanıcı için de gürültü olurdu.

    Döner: [{id, category, amount, date, description, z_score, mean, deviation}]
    z_score'a göre azalan sıralı.
    """
    records = _load_transactions(lookback_days, _EXPENSE_TYPES)
    dismissed_ids = _dismissed_anomaly_ids()

    by_category: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        if rec["amount"] > 0:
            by_category.setdefault(rec["category"], []).append(rec)

    anomalies = []
    for category, items in by_category.items():
        if len(items) < 3:
            continue
        amounts = [i["amount"] for i in items]
        mean = statistics.fmean(amounts)
        stdev = statistics.pstdev(amounts)
        if stdev <= 0:

            continue
        for rec in items:
            if rec["id"] in dismissed_ids:
                continue
            z = (rec["amount"] - mean) / stdev
            if z >= z_threshold:
                anomalies.append({
                    "id": rec["id"],
                    "category": category,
                    "amount": round(rec["amount"], 2),
                    "date": rec["date"].isoformat(),
                    "description": rec["description"],
                    "z_score": round(z, 2),
                    "category_mean": round(mean, 2),
                    "deviation": round(rec["amount"] - mean, 2),
                })

    anomalies.sort(key=lambda a: a["z_score"], reverse=True)
    return anomalies


def _monthly_expense_series(records):
    """Gider kayıtlarını "YYYY-MM" -> toplam sözlüğüne indirger."""
    buckets: dict[str, float] = {}
    for rec in records:
        key = rec["date"].strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0.0) + rec["amount"]
    return buckets


def _score_savings_rate(income, expense):
    """Tasarruf oranını 0-100'e haritalar.

    generate_financial_advice'daki ((gelir-gider)/gelir) oranının aynısı;
    burada ek olarak skora çevrilir. %20 tasarruf tam puan kabul edilir
    (yaygın kişisel finans eşiği), negatif oran 0'a kırpılır.
    """
    if income <= 0:

        return 50.0, 0.0
    rate = (income - expense) / income
    return max(0.0, min(100.0, (rate / 0.20) * 100.0)), rate


def _score_debt_ratio(monthly_debt_payment, monthly_income):
    """Aylık borç ödemesi / aylık gelir oranını 0-100'e haritalar.

    %0 borç -> 100 puan, %40 ve üzeri -> 0 puan (kredi değerlendirmesinde
    yaygın olarak kullanılan üst sınır).
    """
    if monthly_income <= 0:
        return 50.0, 0.0
    ratio = monthly_debt_payment / monthly_income
    return max(0.0, min(100.0, (1.0 - ratio / 0.40) * 100.0)), ratio


def _score_volatility(monthly_totals):
    """Gider oynaklığını 0-100'e haritalar.

    Varyasyon katsayısı (stdev/ortalama) kullanılır: 0 oynaklık -> 100 puan,
    %50 ve üzeri -> 0 puan. Öngörülebilir harcama iyi sinyaldir.
    """
    values = [v for v in monthly_totals.values() if v > 0]
    if len(values) < 2:
        return 50.0, 0.0
    mean = statistics.fmean(values)
    if mean <= 0:
        return 50.0, 0.0
    cv = statistics.pstdev(values) / mean
    return max(0.0, min(100.0, (1.0 - cv / 0.50) * 100.0)), cv


def compute_financial_health_score(lookback_days=90, persist=True):
    """0-100 arası kompozit finansal sağlık skoru üretir ve kaydeder.

    Bileşenler ve ağırlıkları:
      * tasarruf oranı      %50 — en güçlü tek gösterge
      * borç/gelir oranı    %30 — active_debts'teki aylık taksit toplamı
      * gider oynaklığı     %20 — aylık gider dalgalanması

    `persist=True` ise anlamlı skor financial_health_history'e zaman
    damgasıyla yazılır (gelecekteki geçmiş sorguları için). Testlerde
    persist=False kullanılabilir.

    Döner: {score, breakdown: {...}, computed_at, insufficient_data}
    """

    expenses = _load_transactions(
        lookback_days, _EXPENSE_TYPES, decrypt_description=False)
    incomes = _load_transactions(
        lookback_days, _INCOME_TYPES, decrypt_description=False)

    total_expense = sum(r["amount"] for r in expenses)
    total_income = sum(r["amount"] for r in incomes)
    computed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    if total_income <= 0 and total_expense <= 0:
        return {
            "score": None,
            "breakdown": {},
            "computed_at": computed_at,
            "insufficient_data": True,
        }


    monthly_debt_payment = 0.0
    try:
        from database.db import get_active_debts
        monthly_debt_payment = sum(d.get("monthly_payment", 0.0) for d in get_active_debts())
    except sqlite3.Error:
        from utils.logging_config import get_logger
        get_logger().exception("[DB] Aylık borç yükü hesaplanamadı")
        monthly_debt_payment = 0.0


    months = max(1.0, lookback_days / 30.0)
    monthly_income = total_income / months

    savings_score, savings_rate = _score_savings_rate(total_income, total_expense)
    debt_score, debt_ratio = _score_debt_ratio(monthly_debt_payment, monthly_income)
    volatility_score, volatility_cv = _score_volatility(_monthly_expense_series(expenses))

    score = round(
        savings_score * 0.50 + debt_score * 0.30 + volatility_score * 0.20, 1
    )

    breakdown = {
        "savings_rate": round(savings_rate, 4),
        "debt_ratio": round(debt_ratio, 4),
        "expense_volatility": round(volatility_cv, 4),
        "savings_score": round(savings_score, 1),
        "debt_score": round(debt_score, 1),
        "volatility_score": round(volatility_score, 1),
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "monthly_debt_payment": round(monthly_debt_payment, 2),
        "lookback_days": lookback_days,
    }

    if persist:
        save_health_score(score, breakdown, computed_at)

    return {
        "score": score,
        "breakdown": breakdown,
        "computed_at": computed_at,
        "insufficient_data": False,
    }


def save_health_score(score, breakdown, computed_at=None):
    """Günde tek sağlık skoru saklar; aynı gün yeniden hesaplanırsa günceller."""
    timestamp = computed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO financial_health_history "
            "(date, score, breakdown_json) VALUES (?, ?, ?) "
            "ON CONFLICT DO UPDATE SET "
            "date = excluded.date, score = excluded.score, "
            "breakdown_json = excluded.breakdown_json",
            (
                timestamp,
                float(score),
                json.dumps(breakdown, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_health_history(limit=30):
    """Son N skoru en yeniden eskiye döndürür (gelecekteki geçmiş görünümü için)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, score, breakdown_json FROM financial_health_history"
            " ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        rows = cursor.fetchall()

    history = []
    for r in rows:
        try:
            breakdown = json.loads(r["breakdown_json"]) if r["breakdown_json"] else {}
        except (ValueError, TypeError):


            breakdown = {}
        history.append({"date": r["date"], "score": r["score"], "breakdown": breakdown})
    return history


def generate_monthly_forecast(lookback_days=90, min_days=85):
    """En az ~3 aylık nakit-akışı istatistiğine dayanan ay-sonu bakiye öngörüsü.

    `lookback_days`'lik gelir/gider ortalaması RK4 projeksiyonuna (bkz.
    services/projection_service) günlük girdi olarak verilir ve bulunulan
    ayın son gününe kadar ileri sürülür. En eski kayıt `min_days`'ten daha
    yakınsa (yani gerçekte 3 aya yakın geçmiş yoksa) güvenilmez bir tahmin
    üretmek yerine insufficient_data=True döner.
    """
    from calendar import monthrange

    from services.projection_service import project_final_wealth
    from services.queries import DashboardService


    expenses = _load_transactions(
        lookback_days, _EXPENSE_TYPES, decrypt_description=False)
    incomes = _load_transactions(
        lookback_days, _INCOME_TYPES, decrypt_description=False)
    records = expenses + incomes

    if not records:
        return {"insufficient_data": True, "days_available": 0}

    earliest = min(r["date"] for r in records)
    days_available = (datetime.now().date() - earliest).days
    if days_available < min_days:
        return {"insufficient_data": True, "days_available": days_available}

    total_expense = sum(r["amount"] for r in expenses)
    total_income = sum(r["amount"] for r in incomes)
    daily_income = total_income / lookback_days
    daily_expense = total_expense / lookback_days

    current_balance = DashboardService.get_total_balance()
    today = datetime.now().date()
    days_remaining = max(0, monthrange(today.year, today.month)[1] - today.day)

    projected_month_end_balance = project_final_wealth(
        initial_wealth=current_balance,
        daily_income=daily_income,
        daily_expense=daily_expense,
        days=days_remaining,
        r=0.0001,
    )
    savings_rate = (
        (total_income - total_expense) / total_income if total_income > 0 else 0.0
    )

    return {
        "insufficient_data": False,
        "days_available": days_available,
        "current_balance": round(current_balance, 2),
        "projected_month_end_balance": round(projected_month_end_balance, 2),
        "projected_surplus": round(projected_month_end_balance - current_balance, 2),
        "savings_rate": round(savings_rate, 4),
        "days_remaining": days_remaining,
    }


def score_label(score):
    """Skoru Türkçe etikete çevirir — UI hem etiketi hem rengi buradan alsın."""
    if score >= 80:
        return "Çok İyi"
    if score >= 60:
        return "İyi"
    if score >= 40:
        return "Orta"
    if score >= 20:
        return "Zayıf"
    return "Kritik"
