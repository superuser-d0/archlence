from database.db import get_connection


class DashboardService:

    @staticmethod
    def get_total_balance():

        conn = get_connection()

        result = conn.execute(
            "SELECT SUM(balance) as total FROM accounts"
        ).fetchone()

        conn.close()

        return round(result["total"] or 0, 2)

    @staticmethod
    def get_accounts():

        conn = get_connection()

        rows = conn.execute(
            "SELECT * FROM accounts"
        ).fetchall()

        conn.close()

        return rows

    @staticmethod
    def refresh_data():

        return {
            "total": DashboardService.get_total_balance(),
            "accounts": DashboardService.get_accounts()
        }