from database.db import get_connection


class TransactionHistoryService:

    @staticmethod
    def get_last_transactions(limit=10):

        conn = get_connection()

        rows = conn.execute("""
            SELECT *
            FROM transactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        conn.close()

        return rows