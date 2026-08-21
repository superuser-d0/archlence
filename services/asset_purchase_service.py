"""Atomic portfolio asset-entry boundary.

For a newly purchased asset, its asset row, liquid-account transaction,
balance mutation and balance-event ledger entry are one financial operation.
An asset the user already owned only creates the portfolio row; it must not
retroactively alter today's wallet balance or expense reports.
"""

from datetime import datetime

from database.db import (
    SECRET_KEY,
    adjust_account_balance,
    get_connection,
)
from services.account_service import AccountService
from utils.crypto import encrypt
from utils.financial_decimal import decimal_from, fiat


class AssetPurchaseService:

    @staticmethod
    def _pick_funding_account(invested_amount):
        """Alımın düşüleceği vadesiz hesabı seçer.

        NEDEN (kullanıcı raporu: "Windows'ta altın eklenmiyor"): burası
        eskiden koşulsuz `DEFAULT_ACCOUNT_ID` (=1) kullanıyordu. İki ayrı
        şekilde patlıyordu:

          * Uygulama artık açılışta varsayılan hesap SEED ETMİYOR, yani taze
            kurulumda id=1 diye bir satır hiç olmayabiliyor.
          * Kullanıcının parası başka bir hesapta olsa bile alım hep 1
            numaralı hesaptan düşülmeye çalışılıyordu.

        Sonuç: Hesap bakiyesinin eksiye düşmesine izin verilir.
        Eğer işlemi karşılayabilecek hiçbir vadesiz hesap yoksa (hepsi yetersizse),
        en yüksek bakiyeye sahip olan hesap seçilir ve onun bakiyesi eksiye indirilir.

        Kredi kartları bilinçli olarak dışarıda: varlık alımını karta borç
        yazmak ayrı bir ürün kararı ve burada sessizce yapılmamalı.
        """
        from services.account_service import CHECKING

        accounts = [
            account for account in AccountService.get_accounts()
            if account["account_type"] == CHECKING
        ]
        if not accounts:
            raise ValueError(
                "Varlık alımı için vadesiz/nakit hesap bulunamadı. "
                "Önce Kartlarım sekmesinden bir hesap ekleyin."
            )

        affordable = [
            account for account in accounts
            if float(account["balance"]) >= invested_amount
        ]
        if affordable:
            return affordable[0]["id"]

        richest = max(accounts, key=lambda account: float(account["balance"]))
        return richest["id"]

    @staticmethod
    def create_purchase(
        *,
        asset_name,
        asset_code,
        asset_type,
        purchase_price,
        quantity,
        account_id=None,
        purchase_date=None,
        deduct_from_balance=True,
    ):
        price = float(purchase_price)
        qty = float(quantity)
        if price <= 0 or qty <= 0:
            raise ValueError("Fiyat ve miktar sıfırdan büyük olmalıdır.")


        invested_amount = float(
            fiat(decimal_from(purchase_price) * decimal_from(quantity))
        )

        if deduct_from_balance and account_id is None:
            account_id = AssetPurchaseService._pick_funding_account(
                invested_amount)

        when = purchase_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        description = (
            f"{asset_name} ({str(asset_code).upper()}) alındı — "
            f"{qty:g} adet, birim fiyat {price:,.2f} ₺"
        )
        conn = get_connection()
        try:
            cursor = conn.cursor()


            cursor.execute("BEGIN IMMEDIATE")
            if deduct_from_balance:
                AccountService.assert_spending_allowed(
                    cursor, account_id, invested_amount, "expense"
                )
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
            transaction_id = None
            if deduct_from_balance:
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


            conn.commit()
            return {
                "asset_id": asset_id,
                "transaction_id": transaction_id,
                "invested_amount": invested_amount,
                "deducted_from_balance": bool(deduct_from_balance),
            }
        finally:
            conn.close()
