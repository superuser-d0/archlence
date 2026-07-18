from database.db import get_connection

class CategoryService:

    @staticmethod
    def get_categories(category_type=None):
        """
        Belirtilen türe (income/expense) göre kategorileri getirir.
        Eğer tür belirtilmezse, tüm kategorileri çeker.
        """
        conn = get_connection()

        if category_type:
            # Sadece Gelir veya sadece Gider kategorilerini getir (Virgül eklendi)
            rows = conn.execute(
                "SELECT id, name FROM categories WHERE type = ?",
                (category_type,)
            ).fetchall()

        else: 
            # Tüm kategorileri getir
            rows = conn.execute(
                "SELECT id, name FROM categories"
            ).fetchall()
        
        conn.close()
        return rows