"""Single-transaction asset sale boundary."""
from __future__ import annotations

from datetime import datetime

from database.db import SECRET_KEY, adjust_account_balance, get_connection
from utils.crypto import decrypt, encrypt
from utils.errors import DecryptionError, FinancialDataIntegrityError
from utils.financial_decimal import decimal_from, fiat


class AssetSaleService:
    @staticmethod
    def sell(asset_id, sell_price_per_unit, account_id, *, quantity=None, _fault_hook=None):
        price = decimal_from(sell_price_per_unit)
        if price <= 0:
            raise ValueError("Satış fiyatı sıfırdan büyük olmalıdır.")
        conn = get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                row = cursor.execute("SELECT * FROM active_assets WHERE id=?", (asset_id,)).fetchone()
                if row is None:
                    raise ValueError("Varlık bulunamadı.")


                try:
                    owned = decimal_from(decrypt(row["quantity"], SECRET_KEY))
                except (DecryptionError, TypeError, ValueError) as exc:
                    raise FinancialDataIntegrityError(
                        "active_assets", asset_id, "quantity", reason=exc
                    ) from exc
                sold = owned if quantity is None else decimal_from(quantity)
                if sold <= 0 or sold > owned:
                    raise ValueError("Satılacak miktar geçersiz.")
                proceeds = fiat(price * sold)
                if _fault_hook: _fault_hook("before_asset_write")
                remaining = owned - sold
                if remaining == 0:
                    cursor.execute("DELETE FROM active_assets WHERE id=?", (asset_id,))
                else:
                    cursor.execute("UPDATE active_assets SET quantity=? WHERE id=?", (encrypt(str(remaining), SECRET_KEY), asset_id))
                if _fault_hook: _fault_hook("after_asset_write")


                try:
                    unit_cost = decimal_from(
                        decrypt(row["purchase_price"], SECRET_KEY))
                except (DecryptionError, TypeError, ValueError) as exc:
                    raise FinancialDataIntegrityError(
                        "active_assets", asset_id, "purchase_price", reason=exc
                    ) from exc
                cost_basis = fiat(unit_cost * sold)
                pnl = proceeds - cost_basis
                sign = "+" if pnl >= 0 else "-"
                desc = (
                    f"{row['asset_name']} ({row['asset_code']}) satıldı — "
                    f"{sold:f} adet, birim fiyat {price:,.2f} ₺ "
                    f"(K/Z: {sign}{abs(pnl):,.2f} ₺)"
                )
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (account_id,amount,type,category,description,transaction_date) VALUES (?,?,'income','Varlık Satışı',?,?)", (account_id, encrypt(str(proceeds), SECRET_KEY), encrypt(desc, SECRET_KEY), now))


                transaction_id = cursor.lastrowid
                if _fault_hook: _fault_hook("after_transaction_write")
                adjust_account_balance(cursor, account_id, "income", float(proceeds), ref_id=transaction_id, source="asset_sale")
                if _fault_hook: _fault_hook("before_commit")
            return float(proceeds)
        finally:
            conn.close()
