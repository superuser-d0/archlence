import sys, os
from database.db import get_connection
from utils.crypto import decrypt

SECRET_KEY = 'finora_secure_2026'

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
        print(f"Decrypted {amount} -> {dec} (Type: {t_type}, Imp: {importance})")
    except Exception as e:
        print(f"Failed to decrypt {amount}: {e}")
        dec = 0.0
        
    if t_type == "income" or t_type == "Gelir":
        if importance == "main": ana_gelir += dec
        else: ek_gelir += dec
    elif t_type == "expense" or t_type == "Gider":
        if importance == "main": temel_gider += dec
        else: ekstra_gider += dec

print(f"Income: {ana_gelir + ek_gelir}, Expense: {temel_gider + ekstra_gider}")
