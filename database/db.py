import sqlite3
import os
from utils.crypto import encrypt, decrypt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "finance.db")
SECRET_KEY = 'finora_secure_2026'

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def insert_debt(debt_name, total_amount, monthly_payment, total_installments):
    conn = get_connection()
    cursor = conn.cursor()
    enc_name = encrypt(str(debt_name), SECRET_KEY)
    enc_total = encrypt(str(total_amount), SECRET_KEY)
    enc_monthly = encrypt(str(monthly_payment), SECRET_KEY)
    
    cursor.execute("""
        INSERT INTO active_debts (debt_name, total_amount, monthly_payment, total_installments, paid_installments, is_active)
        VALUES (?, ?, ?, ?, 0, 1)
    """, (enc_name, enc_total, enc_monthly, total_installments))
    conn.commit()
    conn.close()

def update_debt_progress(debt_id, extra_installments_paid, is_active=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE active_debts 
        SET paid_installments = paid_installments + ?, is_active = ?
        WHERE id = ?
    """, (extra_installments_paid, is_active, debt_id))
    conn.commit()
    conn.close()

def get_active_debts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_debts WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    
    debts = []
    for r in rows:
        try:
            dec_name = decrypt(r["debt_name"], SECRET_KEY)
            dec_total = float(decrypt(r["total_amount"], SECRET_KEY))
            dec_monthly = float(decrypt(r["monthly_payment"], SECRET_KEY))
        except Exception:
            dec_name = "Bilinmeyen Borç"
            dec_total = 0.0
            dec_monthly = 0.0
            
        debts.append({
            "id": r["id"],
            "debt_name": dec_name,
            "total_amount": dec_total,
            "monthly_payment": dec_monthly,
            "total_installments": r["total_installments"],
            "paid_installments": r["paid_installments"]
        })
    return debts

# ─── Aktif Varlıklar ─────────────────────────────────────────────────────────

def insert_asset(asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date=None):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    enc_purchase_price = encrypt(str(purchase_price), SECRET_KEY)
    enc_quantity       = encrypt(str(quantity),       SECRET_KEY)
    if purchase_date is None:
        purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO active_assets (asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (asset_name, asset_code.upper(), asset_type, enc_purchase_price, enc_quantity, purchase_date))
    conn.commit()
    conn.close()


def get_all_assets():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_assets ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    assets = []
    for r in rows:
        try:
            dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
            dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
        except Exception:
            dec_price    = 0.0
            dec_quantity = 0.0
        assets.append({
            "id":             r["id"],
            "asset_name":     r["asset_name"],
            "asset_code":     r["asset_code"],
            "asset_type":     r["asset_type"],
            "purchase_price": dec_price,
            "quantity":       dec_quantity,
        })
    return assets


def delete_asset(asset_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_assets WHERE id = ?", (asset_id,))
    conn.commit()
    conn.close()


def get_asset_by_id(asset_id):
    """Returns a single asset row as a dict (decrypted)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_assets WHERE id = ?", (asset_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    try:
        dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
        dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
    except Exception:
        dec_price    = 0.0
        dec_quantity = 0.0
    return {
        "id":             r["id"],
        "asset_name":     r["asset_name"],
        "asset_code":     r["asset_code"],
        "asset_type":     r["asset_type"],
        "purchase_price": dec_price,
        "quantity":       dec_quantity,
        "purchase_date":  r["purchase_date"],
    }


def insert_asset_transaction(account_id, amount, tx_type, category, description):
    """
    Records an asset buy (type='expense', category='Varlık Alımı') or
    an asset sale (type='income', category='Varlık Satışı') into the
    transactions table so the liquid wallet balance is updated correctly.
    """
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    enc_amount = encrypt(str(amount), SECRET_KEY)
    enc_desc   = encrypt(str(description), SECRET_KEY)
    tx_date    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (account_id, enc_amount, tx_type, category, enc_desc, tx_date))
    conn.commit()
    conn.close()


def get_asset_transaction_history(limit=50):
    """
    Returns all investment ledger entries (Varlık Alımı + Varlık Satışı)
    ordered by most recent first, for the 'Varlık Geçmişi' section.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT type, category, amount, description,
               strftime('%d/%m/%Y %H:%M', transaction_date) as t_date
        FROM transactions
        WHERE category IN ('Varlık Alımı', 'Varlık Satışı')
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        try:
            dec_amount = float(decrypt(str(r["amount"]), SECRET_KEY))
        except Exception:
            dec_amount = 0.0
        try:
            dec_desc = decrypt(str(r["description"]), SECRET_KEY)
        except Exception:
            dec_desc = ""
        result.append({
            "type":        r["type"],
            "category":    r["category"],
            "amount":      dec_amount,
            "description": dec_desc,
            "date":        r["t_date"],
        })
    return result