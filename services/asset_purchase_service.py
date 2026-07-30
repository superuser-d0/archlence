"""Atomic portfolio purchase boundary.

An asset row, its liquid-account transaction, the balance mutation and the
balance-event ledger entry are one financial operation.  They must therefore
share one SQLite transaction.
"""

from datetime import datetime

from database.db import (
    DEFAULT_ACCOUNT_ID,
    SECRET_KEY,
    adjust_account_balance,
    get_connection,
)
from services.account_service import AccountService
from utils.crypto import encrypt


class AssetPurchaseService:
    @staticmethod
    def create_purchase(
        *,
        asset_name,
        asset_code,
        asset_type,
        purchase_price,
        quantity,
        account_id=DEFAULT_ACCOUNT_ID,
        purchase_date=None,
    ):
        price = float(purchase_price)
        qty = float(quantity)
        if price <= 0 or qty <= 0:
            raise ValueError("Fiyat ve miktar sıfırdan büyük olmalıdır.")
        invested_amount = price * qty
        allowed, reason = AccountService.check_spending_allowed(
            account_id, invested_amount, "expense"
        )
        if not allowed:
            raise ValueError(reason)

        when = purchase_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        description = (
            f"{asset_name} ({str(asset_code).upper()}) alındı — "
            f"{qty:g} adet, birim fiyat {price:,.2f} ₺"
        )
        conn = get_connection()
        try:
            # sqlite3 connection context commits on success and rolls the
            # complete unit back for every exception type.
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO active_assets
                        (asset_name, asset_code, asset_type, purchase_price,
                         quantity, purchase_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_name,
                        str(asset_code).upper(),
                        asset_type,
                        encrypt(str(price), SECRET_KEY),
                        encrypt(str(qty), SECRET_KEY),
                        when,
                    ),
                )
                asset_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO transactions
                        (account_id, amount, type, category, description,
                         transaction_date)
                    VALUES (?, ?, 'expense', 'Varlık Alımı', ?, ?)
                    """,
                    (
                        account_id,
                        encrypt(str(invested_amount), SECRET_KEY),
                        encrypt(description, SECRET_KEY),
                        when,
                    ),
                )
                transaction_id = cursor.lastrowid
                adjust_account_balance(
                    cursor,
                    account_id,
                    "expense",
                    invested_amount,
                    ref_id=transaction_id,
                    source="asset_purchase",
                )
            return {
                "asset_id": asset_id,
                "transaction_id": transaction_id,
                "invested_amount": invested_amount,
            }
        finally:
            conn.close()
