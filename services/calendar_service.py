"""Takvim görünümü için ay/gün bazlı işlem sorguları.

insights_service.py'deki şifreleme kısıtının aynısı geçerli: `amount` ve
`description` AES ile şifreli TEXT, bu yüzden SQL'de toplanamaz/aranamaz.
Ay ızgarası için yalnızca GÜN ve SAYI gerekiyor (düz `transaction_date`
üzerinden SQL'de sayılabiliyor); tek bir günün işlemlerini çözmek içinse
satırlar çekilip Python'da decrypt edilir. Servis Kivy'den bağımsızdır.
"""
from database.db import COMPLETED_TX, SECRET_KEY, get_connection
from utils.crypto import decrypt


def get_month_transaction_days(year, month):
    """`{gün: işlem_sayısı}` döner — ay ızgarasında hangi günler işaretlenecek."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT CAST(strftime('%d', transaction_date) AS INTEGER) AS day,
               COUNT(*) AS cnt
        FROM transactions
        WHERE strftime('%Y-%m', transaction_date) = ?
          AND {COMPLETED_TX}
        GROUP BY day
        """,
        (f"{int(year):04d}-{int(month):02d}",),
    )
    rows = cursor.fetchall()
    conn.close()
    return {row["day"]: row["cnt"] for row in rows}


def get_day_transactions(date_obj):
    """Belirli bir günün işlemlerini çözülmüş halde döner.

    Döner: [{type, category, amount, description, time}, ...] saat sırasına
    göre artan. Tutar çözülemezse 0.0'a düşer — tek bir bozuk satır tüm
    günü listeden düşürmemeli (bkz. update_metrics_and_goals'daki aynı desen).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT type, category, amount, description,
               strftime('%H:%M', transaction_date) AS time
        FROM transactions
        WHERE date(transaction_date) = ?
          AND {COMPLETED_TX}
        ORDER BY transaction_date ASC
        """,
        (date_obj.isoformat(),),
    )
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        try:
            amount = float(decrypt(str(row["amount"]), SECRET_KEY))
        except (ValueError, TypeError):
            amount = 0.0
        try:
            description = (
                decrypt(str(row["description"]), SECRET_KEY)
                if row["description"] else ""
            )
        except (ValueError, TypeError):
            description = ""
        items.append({
            "type": row["type"],
            "category": row["category"] or "Diğer",
            "amount": amount,
            "description": description,
            "time": row["time"],
        })
    return items
