from database.db import get_connection, adjust_account_balance
from utils.crypto import encrypt, decrypt
from datetime import datetime

SECRET_KEY = 'finora_secure_2026'

class TransactionService:
    @staticmethod
    def add_transaction(account_id, amount, transaction_type, category, description,
                        transaction_date=None):
        """transaction_date verilmezse şu an kullanılır; CSV içe aktarımı gibi
        geçmiş tarihli kayıtlar tarihi açıkça geçer — bakiye senkronu dahil
        aynı atomik yoldan geçmiş olurlar."""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Yalnızca tutar ve açıklama şifrelenir; type/category düz metin kalır
            # çünkü SQL sorguları (filtreleme ve categories JOIN'i) bu kolonlar
            # üzerinden çalışıyor — şifrelenirlerse raporlama sorguları bozulur.
            str_amount = str(amount)
            encrypted_amount = encrypt(str_amount, SECRET_KEY)
            encrypted_description = encrypt(description, SECRET_KEY)

            # transaction_date DB tarafında değil uygulamada üretilir; böylece
            # get_transactions_by_period'daki 'localtime' filtreleriyle aynı
            # saat diliminde kalır.
            date_now = transaction_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (account_id, encrypted_amount, transaction_type, category, encrypted_description, date_now))

            # Hesaplar Kopuk düzeltmesi: accounts.balance işlemle aynı commit'te
            # senkron güncellenir (gelir artırır, gider azaltır).
            adjust_account_balance(cursor, account_id, transaction_type, amount)

            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_transactions_by_period(filter_type):
        conn = get_connection()
        cursor = conn.cursor()
        
        # date_cond f-string ile SQL'e gömülüyor ama güvenli: değerler yalnızca
        # buradaki sabit listeden gelir, kullanıcı girdisi asla doğrudan girmez.
        if filter_type == "1 Hafta":
            date_cond = ">= date('now', '-7 days', 'localtime')"
        elif filter_type == "1 Ay":
            date_cond = ">= date('now', '-1 month', 'localtime')"
        elif filter_type == "1 Yıl":
            date_cond = ">= date('now', '-1 year', 'localtime')"
        elif filter_type == "Hayat Boyu":
            date_cond = "IS NOT NULL"
        else:
            date_cond = "= date('now', 'localtime')"
            
        cursor.execute(f"""
            SELECT t.amount, t.type, t.category, t.transaction_date, c.importance 
            FROM transactions t 
            LEFT JOIN categories c ON t.category = c.name 
            WHERE date(t.transaction_date) {date_cond}
        """)
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for r in rows:
            try:
                decrypted_amount = float(decrypt(r[0], SECRET_KEY))
            except Exception:
                decrypted_amount = 0.0

            data.append({
                'amount': decrypted_amount,
                'type': r[1],
                'category': r[2] if r[2] else 'Diğer',
                'transaction_date': r[3],
                'importance': r[4] if r[4] else 'extra'
            })
        return data