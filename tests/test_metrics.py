import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SECRET_KEY = 'finora_secure_2026'

def main():
    from database.db import get_connection
    from utils.crypto import decrypt

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.amount, t.type, IFNULL(c.importance, 'extra')
        FROM transactions t
        LEFT JOIN categories c ON t.category = c.name
    """)
    rows = cursor.fetchall()
    conn.close()

    ana_gelir, ek_gelir, temel_gider, ekstra_gider = 0.0, 0.0, 0.0, 0.0
    for amount, t_type, importance in rows:
        try:
            dec = float(decrypt(str(amount), SECRET_KEY))
        except Exception:
            dec = 0.0

        if t_type in ("income", "Gelir"):
            if importance == "main":
                ana_gelir += dec
            else:
                ek_gelir += dec
        elif t_type in ("expense", "Gider"):
            if importance == "main":
                temel_gider += dec
            else:
                ekstra_gider += dec

    print(f"Income: {ana_gelir + ek_gelir}, Expense: {temel_gider + ekstra_gider}")


if __name__ == "__main__":
    main()
