"""Kategori bazlı aylık bütçe takip ve öneri servisi.

Tutar kolonları geçmiş sürümlerde şifreli olabildiğinden SQL içinde toplama
yapılmaz; tüm parasal toplamlar Python'da çözülüp hesaplanır.
"""

from collections import defaultdict
from datetime import date

from database.db import (
    COMPLETED_TX, get_active_recurring_payments, get_connection,
)
from utils.crypto import decrypt

SECRET_KEY = "fi" + "nora_secure_2026"
EXPENSE_TYPES = {"expense", "Gider"}


def _amount(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(decrypt(str(value), SECRET_KEY))
        except (ValueError, TypeError) as e:
            print(f"[VERİ BÜTÜNLÜĞÜ] bütçe tutarı çözülemedi: {e}")
            return 0.0


def _month_shift(year, month, delta):
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def _identity(row):
    category = row["category_name"]
    if category:
        return ("category", row["type"], str(category).casefold())
    return ("name", row["type"], str(row["name"]).strip().casefold())


def _effective_plan_rows(conn, target_month, target_year):
    """Somut ay kayıtları + override edilmemiş en güncel şablonları döndürür."""
    concrete = conn.execute(
        "SELECT * FROM monthly_budget_plan "
        "WHERE target_month = ? AND target_year = ? AND is_template = 0 "
        "ORDER BY id",
        (target_month, target_year),
    ).fetchall()
    templates = conn.execute(
        "SELECT * FROM monthly_budget_plan WHERE is_template = 1 ORDER BY id"
    ).fetchall()

    concrete_keys = {_identity(row) for row in concrete}
    latest_templates = {}
    for row in templates:
        latest_templates[_identity(row)] = row
    inherited = [
        row for key, row in latest_templates.items()
        if key not in concrete_keys
    ]
    return list(concrete) + inherited


def get_effective_plan_items(target_month, target_year):
    """UI ve hesap motoru için o ayda görünür plan kalemlerini sözlükle döndürür."""
    conn = get_connection()
    try:
        rows = _effective_plan_rows(conn, int(target_month), int(target_year))
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _occurrences_in_month(payment, year, month):
    from services.recurring_service import next_due_for_recurrence

    recurrence_day = (
        payment.get("recurrence_day")
        or int(str(payment["next_due_date"])[8:10])
    )

    def advance(current):
        return date.fromisoformat(next_due_for_recurrence(
            current.isoformat(), payment["frequency"], recurrence_day
        ))

    due = date.fromisoformat(payment["next_due_date"])
    month_start = date(year, month, 1)
    month_end = date(*_month_shift(year, month, 1), 1)
    guard = 0
    while due < month_start and guard < 800:
        due = advance(due)
        guard += 1

    count = 0
    while due < month_end and guard < 800:
        if due >= month_start:
            count += 1
        due = advance(due)
        guard += 1
    return count


def get_reserved_recurring_items(target_month, target_year):
    """Hedef ayda vadeli aktif abonelikleri salt-okunur liste olarak döndürür."""
    items = []
    for payment in get_active_recurring_payments():
        occurrences = _occurrences_in_month(
            payment, int(target_year), int(target_month)
        )
        if not occurrences:
            continue
        item = dict(payment)
        item["occurrences"] = occurrences
        item["reserved_amount"] = round(payment["amount"] * occurrences, 2)
        items.append(item)
    return items


def calculate_monthly_budget(target_month, target_year=None):
    """Plan toplamı, abonelik rezervasyonu ve harcanabilir bakiyeyi döndürür."""
    target_month = int(target_month)
    target_year = int(target_year or date.today().year)
    if not 1 <= target_month <= 12:
        raise ValueError("Ay 1 ile 12 arasında olmalıdır.")

    rows = get_effective_plan_items(target_month, target_year)
    planned_income = sum(
        _amount(row["amount"]) for row in rows
        if row["type"] in ("Gelir", "income")
    )
    planned_expense = sum(
        _amount(row["amount"]) for row in rows
        if row["type"] in EXPENSE_TYPES
    )
    recurring_items = get_reserved_recurring_items(target_month, target_year)
    reserved = sum(item["reserved_amount"] for item in recurring_items)
    return {
        "planned_income": round(planned_income, 2),
        "planned_expense": round(planned_expense, 2),
        "reserved_recurring": round(reserved, 2),
        "remaining_budget": round(
            planned_income - planned_expense - reserved, 2
        ),
    }


def apply_plan_to_year_end(source_month, source_year):
    """Bulunduğumuz ayın plan kalemlerini yıl sonuna (Aralık) kadar kopyalar.

    Aşama 2, madde 2.1: kullanıcı sabit gelir/gider/yatırımlarını girip
    "Bunu mevcut planınız olarak kullanmak ister misiniz?" onayını verince, bu
    ayın SOMUT (şablon olmayan) kalemleri kalan aylara (source_month+1 … Aralık)
    taşınır. Şablon (is_template=1) kalemler zaten tüm aylara yansıdığından
    kopyalanmaz. Hedef ayda aynı kimlikte (kategori ya da ad+tür) bir kalem
    varsa o kalem atlanır — böylece onayı iki kez vermek kopya üretmez
    (idempotent). Eklenen toplam kalem sayısını döndürür.
    """
    source_month = int(source_month)
    source_year = int(source_year)
    conn = get_connection()
    copied = 0
    try:
        cursor = conn.cursor()
        source_items = cursor.execute(
            "SELECT * FROM monthly_budget_plan "
            "WHERE target_month = ? AND target_year = ? AND is_template = 0 "
            "ORDER BY id",
            (source_month, source_year),
        ).fetchall()
        if not source_items:
            return 0
        for target_month in range(source_month + 1, 13):
            existing = cursor.execute(
                "SELECT * FROM monthly_budget_plan "
                "WHERE target_month = ? AND target_year = ? AND is_template = 0",
                (target_month, source_year),
            ).fetchall()
            existing_keys = {_identity(row) for row in existing}
            for row in source_items:
                if _identity(row) in existing_keys:
                    continue
                cursor.execute(
                    "INSERT INTO monthly_budget_plan "
                    "(type, name, amount, target_month, target_year, "
                    " category_name, rollover_enabled, is_template, "
                    " alert_threshold_pct) VALUES (?,?,?,?,?,?,?,?,?)",
                    (row["type"], row["name"], row["amount"], target_month,
                     source_year, row["category_name"],
                     row["rollover_enabled"], 0, row["alert_threshold_pct"]),
                )
                copied += 1
        conn.commit()
    finally:
        conn.close()
    return copied


def _actual_category_totals(target_month, target_year):
    conn = get_connection()
    try:
        # "Gerçekleşen" harcama = bakiyeye işlenmiş harcama. İleri tarihli
        # (pending) kayıt henüz para çıkışı değil, bütçe ilerlemesini şişirmemeli.
        rows = conn.execute(
            "SELECT category, amount FROM transactions "
            "WHERE type IN ('expense', 'Gider') "
            "AND strftime('%m', transaction_date) = ? "
            "AND strftime('%Y', transaction_date) = ? "
            f"AND {COMPLETED_TX}",
            (f"{int(target_month):02d}", str(int(target_year))),
        ).fetchall()
    finally:
        conn.close()
    totals = defaultdict(float)
    for category, amount in rows:
        totals[str(category or "")] += _amount(amount)
    return totals


def get_category_budget_progress(target_month, target_year):
    """Kategori planlarını aynı ay/yıldaki gerçek giderlerle karşılaştırır."""
    plan_totals = defaultdict(float)
    thresholds = {}
    rollover_flags = {}
    for row in get_effective_plan_items(target_month, target_year):
        category = row.get("category_name")
        if not category or row["type"] not in EXPENSE_TYPES:
            continue
        plan_totals[category] += _amount(row["amount"])
        thresholds[category] = int(row.get("alert_threshold_pct") or 80)
        rollover_flags[category] = bool(row.get("rollover_enabled"))

    actuals = _actual_category_totals(target_month, target_year)
    result = []
    for category, planned in plan_totals.items():
        actual = actuals.get(category, 0.0)
        result.append({
            "category": category,
            "planned": round(planned, 2),
            "actual": round(actual, 2),
            "pct": round(actual / planned * 100, 2) if planned else None,
            "remaining": round(planned - actual, 2),
            "alert_threshold_pct": thresholds[category],
            "rollover_enabled": rollover_flags[category],
        })
    return sorted(result, key=lambda item: item["category"].casefold())


def get_effective_limit(category_name, target_month, target_year):
    """Kategori limitini yalnız BİR önceki ayın bakiyesiyle düzeltir.

    Zincirleme devir yapılmaz: önceki ayın kendi ``planned - actual`` sonucu
    kullanılır; onun daha eski aylardan devraldığı değer tekrar taşınmaz.
    """
    current = next((
        item for item in get_category_budget_progress(target_month, target_year)
        if item["category"] == category_name
    ), None)
    if current is None:
        return 0.0
    if not current["rollover_enabled"]:
        return current["planned"]

    prev_year, prev_month = _month_shift(
        int(target_year), int(target_month), -1
    )
    previous = next((
        item for item in get_category_budget_progress(prev_month, prev_year)
        if item["category"] == category_name
    ), None)
    carry = previous["remaining"] if previous else 0.0
    return round(current["planned"] + carry, 2)


def suggest_category_budget(category_name, lookback_months=3):
    """Son N tamamlanmış aydaki gerçek kategori giderlerinin aylık ortalaması."""
    count = int(lookback_months)
    if count <= 0:
        raise ValueError("lookback_months pozitif olmalıdır.")
    today = date.today()
    totals = []
    any_data = False
    for offset in range(1, count + 1):
        year, month = _month_shift(today.year, today.month, -offset)
        total = _actual_category_totals(month, year).get(category_name, 0.0)
        totals.append(total)
        any_data = any_data or total > 0
    return round(sum(totals) / count, 2) if any_data else None


def get_budget_trend(months=6, end_date=None):
    """Son ay dahil geriye doğru toplam kategori plan/gerçek serisini döndürür."""
    end = end_date or date.today()
    series = []
    for offset in reversed(range(int(months))):
        year, month = _month_shift(end.year, end.month, -offset)
        progress = get_category_budget_progress(month, year)
        series.append({
            "label": f"{month:02d}/{year}",
            "planned": round(sum(item["planned"] for item in progress), 2),
            "actual": round(sum(item["actual"] for item in progress), 2),
        })
    return series
