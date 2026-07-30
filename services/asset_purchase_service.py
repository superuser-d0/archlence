"""Atomic portfolio purchase boundary.

An asset row, its liquid-account transaction, the balance mutation and the
balance-event ledger entry are one financial operation.  They must therefore
share one SQLite transaction.
"""

from datetime import datetime

from database.db import (
    SECRET_KEY,
    adjust_account_balance,
    get_connection,
)
from services.account_service import AccountService, _fmt_try
from utils.crypto import encrypt


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

        Sonuç: "Yetersiz Bakiye! Bu hesap eksiye düşemez." — kullanıcı ise
        ekranda dolu bir bakiye görüyordu. Artık tutarı KARŞILAYABİLEN ilk
        vadesiz hesap seçilir; hiçbiri yetmiyorsa mesaj neyin eksik olduğunu
        söyler (eskiden hangi hesabın kastedildiği bile belli değildi).

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
        raise ValueError(
            "Yetersiz bakiye: bu alım için "
            f"{_fmt_try(invested_amount)} gerekiyor, en yüksek vadesiz hesap "
            f"bakiyeniz ({richest['name']}) {_fmt_try(float(richest['balance']))}."
        )

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
    ):
        price = float(purchase_price)
        qty = float(quantity)
        if price <= 0 or qty <= 0:
            raise ValueError("Fiyat ve miktar sıfırdan büyük olmalıdır.")
        invested_amount = price * qty

        if account_id is None:
            account_id = AssetPurchaseService._pick_funding_account(
                invested_amount)

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
