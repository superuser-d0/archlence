"""Atomic automatic debt installment settlement."""
from datetime import datetime
from database.db import SECRET_KEY, adjust_account_balance, get_connection
from utils.crypto import decrypt, encrypt
from utils.financial_decimal import fiat


class DebtPaymentService:
    @staticmethod
    def pay_auto(debt_id, account_id, installments, month, _fault_hook=None):
        conn = get_connection()
        try:
            with conn:
                cur = conn.cursor(); cur.execute("BEGIN IMMEDIATE")
                row = cur.execute("SELECT * FROM active_debts WHERE id=? AND is_active=1", (debt_id,)).fetchone()
                if row is None or row["last_auto_pay_date"] == month:
                    return False
                remaining = row["total_installments"] - row["paid_installments"]
                count = min(int(installments), remaining)
                if count <= 0: return False
                amount = float(fiat(decrypt(row["monthly_payment"], SECRET_KEY)) * count)
                desc = decrypt(row["debt_name"], SECRET_KEY) + " (Otomatik Taksit Ödemesi)"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO transactions (account_id,amount,type,category,description,transaction_date) VALUES (?,?,'expense','Kredi Taksiti',?,?)", (account_id, encrypt(str(amount), SECRET_KEY), encrypt(desc, SECRET_KEY), now))
                # Taksit işleminin id'si HEMEN alınıyor: `lastrowid` cursor'a
                # ait, araya giren her INSERT (ve buradaki `_fault_hook`) onu
                # ezebilir. Defterin `ref_id`'si bu satırı göstermek zorunda.
                transaction_id = cur.lastrowid
                if _fault_hook: _fault_hook("after_transaction")
                adjust_account_balance(cur, account_id, "expense", amount, ref_id=transaction_id, source="debt_payment")
                if _fault_hook: _fault_hook("after_balance")
                paid = row["paid_installments"] + count
                cur.execute("UPDATE active_debts SET paid_installments=?, last_auto_pay_date=?, is_active=? WHERE id=?", (paid, month, 0 if paid >= row["total_installments"] else 1, debt_id))
                if _fault_hook: _fault_hook("before_commit")
            return True
        finally:
            conn.close()
