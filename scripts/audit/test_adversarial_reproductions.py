"""Intentionally failing v0.0.9 audit reproductions.

This module is deliberately outside ``tests/`` so ``run_tests.py`` remains a
release-candidate signal.  Run it explicitly:

    python -m unittest scripts.audit.test_adversarial_reproductions -v

Every test uses a temporary database/key/archive.  A failure means the named
production invariant is *not* currently enforced; it is audit evidence, not a
test-suite regression to hide with skip/xfail.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest import mock

from utils.errors import FinancialDataIntegrityError, IntegrityVerificationError


class _TemporaryProfile(unittest.TestCase):
    PASSPHRASE = "yalnizca-audit-icin-parola"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="archlence-audit-")
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "finance.db"
        self.key_path = self.root / "encryption.key"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)
        os.chmod(self.key_path, 0o600)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()

        from database.init_db import initialize_database

        initialize_database()

    def tearDown(self):
        self.key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def create_account(self, balance=1000.0):
        from services.account_service import AccountService

        return AccountService.create_account(
            "Audit Hesabı", "checking", initial_balance=balance
        )

    def balance(self, account_id):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]


class BackupAuthenticityReproduction(_TemporaryProfile):
    def test_plaintext_financial_state_cannot_be_rewritten_with_a_new_hash(self):
        """A manifest digest must be authenticated, not attacker-replaceable."""
        from services.backup_service import create_backup, verify_backup
        from services.transaction_service import TransactionService

        account_id = self.create_account()
        TransactionService.add_transaction(
            account_id, 125.50, "expense", "Market", "Sentetik kayıt"
        )
        package = self.root / "original.archlence-backup"
        create_backup(
            package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )

        unpacked = self.root / "rewritten"
        unpacked.mkdir()
        with zipfile.ZipFile(package) as archive:
            archive.extractall(unpacked)

        with closing(sqlite3.connect(unpacked / "finance.db")) as conn:
            conn.execute(
                "UPDATE accounts SET balance=777777.77 WHERE id=?",
                (account_id,),
            )
            conn.commit()

        metadata_path = unpacked / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["database_sha256"] = hashlib.sha256(
            (unpacked / "finance.db").read_bytes()
        ).hexdigest()
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        rewritten = self.root / "rewritten.archlence-backup"
        with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in ("finance.db", "metadata.json", "key.recovery.json"):
                archive.write(unpacked / name, name)

        caught = None
        try:
            verify_backup(rewritten, self.PASSPHRASE)
        except IntegrityVerificationError as exc:
            caught = exc
        print(
            "AUDIT_STATE backup_authenticity "
            "before_balance=874.5 after_balance=777777.77 "
            f"expected_exception=IntegrityVerificationError "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'}"
        )
        self.assertIsNotNone(
            caught, "DB ve manifest birlikte değiştirildiğinde backup kabul edildi"
        )


class RecurringIdempotencyReproduction(_TemporaryProfile):
    def _payment(self, account_id, *, amount=100.0, auto_deduct=False):
        from database.db import (
            get_active_recurring_payments,
            insert_recurring_payment,
        )

        insert_recurring_payment(
            "Audit Aboneliği",
            amount,
            "Dijital Platformlar",
            "monthly",
            date.today().isoformat(),
            auto_deduct,
            account_id=account_id,
            recurrence_day=date.today().day,
        )
        return get_active_recurring_payments()[0]

    def test_retrying_the_same_due_object_has_one_financial_effect(self):
        from database.db import get_connection, process_due_recurring_payment

        account_id = self.create_account()
        payment = self._payment(account_id)

        process_due_recurring_payment(payment)
        process_due_recurring_payment(payment)  # retry/stale UI object

        with closing(get_connection()) as conn, conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions "
                "WHERE category='Dijital Platformlar'"
            ).fetchone()[0]
            due = conn.execute(
                "SELECT next_due_date FROM recurring_payments WHERE id=?",
                (payment["id"],),
            ).fetchone()[0]
        after_balance = self.balance(account_id)
        print(
            "AUDIT_STATE recurring_retry "
            f"before_balance=1000.0 after_balance={after_balance} "
            f"transaction_count={count} before_due={date.today().isoformat()} "
            f"after_due={due} expected_exception=NONE caught_exception=NONE"
        )
        self.assertEqual(count, 1, "aynı vade iki işlem üretti")
        self.assertEqual(after_balance, 900.0)

    def test_refund_retry_cannot_credit_the_same_charge_twice(self):
        from database.db import process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge

        account_id = self.create_account()
        payment = self._payment(account_id)
        process_due_recurring_payment(payment)

        first = refund_current_period_charge(payment["id"])
        second = refund_current_period_charge(payment["id"])

        with closing(sqlite3.connect(self.db_path)) as conn:
            counts = conn.execute(
                "SELECT type, COUNT(*) FROM transactions GROUP BY type"
            ).fetchall()
        after_balance = self.balance(account_id)
        print(
            "AUDIT_STATE recurring_refund_retry "
            f"before_balance=1000.0 after_balance={after_balance} "
            f"first_refund={first} second_refund={second} "
            f"transaction_counts={dict(counts)} "
            "expected_exception=NONE caught_exception=NONE"
        )

        self.assertEqual(first, 100.0)
        self.assertEqual(second, 0.0, "aynı tahsilat ikinci kez iade edildi")
        self.assertEqual(after_balance, 1000.0)

    def test_corrupt_auto_amount_fails_closed_without_advancing_due_date(self):
        from database.db import get_active_recurring_payments, get_connection

        account_id = self.create_account()
        payment = self._payment(account_id, auto_deduct=True)
        original_due = payment["next_due_date"]
        with closing(get_connection()) as conn, conn:
            conn.execute(
                "UPDATE recurring_payments SET amount=? WHERE id=?",
                ("AEADv1:bozuk-zarf", payment["id"]),
            )
            conn.commit()

        degraded = get_active_recurring_payments()[0]
        self.assertFalse(degraded["amount_is_valid"])
        from database.db import process_due_recurring_payment

        # v0.0.9'un non-finite/geçersiz tutar reddi (998584e) bozuk zarfı
        # `FinancialDataIntegrityError`'dan ÖNCE, servis sınırında ValueError
        # ile reddediyor. Beklenen tip genişletildi: önemli olan hangi tipin
        # fırlatıldığı değil, işlemin FAIL-CLOSED olması ve vadeyi
        # ilerletmemesi. Tip daraltması testin gerçek değişmezi kaçırmasına
        # yol açıyordu (ERROR olarak düşüyordu).
        caught = None
        try:
            process_due_recurring_payment(degraded)
        except (FinancialDataIntegrityError, ValueError) as exc:
            caught = exc

        with closing(get_connection()) as conn, conn:
            row = conn.execute(
                "SELECT next_due_date FROM recurring_payments WHERE id=?",
                (payment["id"],),
            ).fetchone()
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
        print(
            "AUDIT_STATE corrupt_recurring_amount "
            f"before_due={original_due} after_due={row['next_due_date']} "
            f"transaction_count={tx_count} balance={self.balance(account_id)} "
            "expected_exception=FinancialDataIntegrityError|ValueError "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'}"
        )
        self.assertIsNotNone(caught)
        self.assertEqual(row["next_due_date"], original_due)
        self.assertEqual(tx_count, 0)


class CrossTransactionAtomicityReproduction(_TemporaryProfile):
    """P0-4 / P0-5 kapanış kanıtı: her fault noktasında tam rollback.

    ÖNCEKİ HÂLİ BAYATTI. Reproduction `database.db.delete_asset` ve
    `insert_asset_transaction` (o gün var olan) fonksiyonlarını patch'leyerek hata enjekte
    ediyordu; v0.0.9'un atomiklik düzeltmesi (96049ee, df46a31) bu yolları
    kaldırıp işi `AssetSaleService` / `DebtPaymentService` altında tek
    transaction'a taşıdı. Patch'ler artık HİÇ TETİKLENMİYORDU: satış ve ödeme
    normal şekilde tamamlanıyor, test ise "varlık korunmalı" dediği için
    YANLIŞ SEBEPLE kırmızı kalıyordu — düzeltmenin işe yarayıp yaramadığı
    hakkında hiçbir sinyal vermiyordu.

    Ayrıca "before" değerleri ölçülmek yerine AUDIT_STATE satırına sabit
    yazılıyordu; artık gerçekten okunuyorlar.

    Testler şimdi servislerin kendi `_fault_hook` noktalarını kullanıyor.
    """

    def _asset_state(self, asset_id, account_id):
        from database.db import get_connection

        with closing(get_connection()) as conn, conn:
            assets = conn.execute(
                "SELECT COUNT(*) FROM active_assets WHERE id=?", (asset_id,)
            ).fetchone()[0]
            sales = conn.execute(
                "SELECT COUNT(*) FROM transactions "
                "WHERE category='Varlık Satışı'"
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM balance_events WHERE source='asset_sale'"
            ).fetchone()[0]
        return assets, sales, events, self.balance(account_id)

    def test_asset_sale_rolls_back_completely_at_every_fault_point(self):
        from database.db import get_connection, insert_asset
        from services.asset_sale_service import AssetSaleService

        for hook_point in (
            "before_asset_write",
            "after_asset_write",
            "after_transaction_write",
            "before_commit",
        ):
            with self.subTest(fault=hook_point):
                account_id = self.create_account()
                insert_asset(f"Audit {hook_point}", "AUD", "Altın", 100.0, 2.0)
                with closing(get_connection()) as conn, conn:
                    asset_id = conn.execute(
                        "SELECT id FROM active_assets ORDER BY id DESC LIMIT 1"
                    ).fetchone()[0]

                before = self._asset_state(asset_id, account_id)

                # HOOK'UN GERÇEKTEN TETİKLENDİĞİNİ SAY. Yalnızca son
                # duruma bakmak yetmez: patch yanlış sembole bağlanırsa
                # fault hiç çalışmaz, işlem normal tamamlanır ve test
                # YANLIŞ SEBEPLE kırmızı/yeşil olur. Bu tam olarak bu
                # dosyada bir kez yaşandı (bkz. bfb2b37).
                fired = []

                def _fault(point, _target=hook_point):
                    if point == _target:
                        fired.append(point)
                        raise OSError(f"injected at {point}")

                raised = None
                try:
                    AssetSaleService.sell(
                        asset_id, 150.0, account_id, quantity=2.0,
                        _fault_hook=_fault,
                    )
                except OSError as exc:
                    raised = str(exc)
                self.assertEqual(
                    fired, [hook_point],
                    f"{hook_point} noktasına HİÇ ULAŞILMADI; test yanlış "
                    "sebeple sonuç veriyor",
                )

                after = self._asset_state(asset_id, account_id)
                print(
                    f"AUDIT_STATE asset_sale_fault point={hook_point} "
                    f"raised={raised!r} "
                    f"assets={before[0]}->{after[0]} sales={before[1]}->{after[1]} "
                    f"events={before[2]}->{after[2]} "
                    f"balance={before[3]}->{after[3]}"
                )
                self.assertIsNotNone(raised, "fault enjekte edilemedi")
                self.assertEqual(
                    after, before,
                    f"{hook_point} noktasında yarım state kaldı",
                )

    def test_debt_payment_rolls_back_completely_at_every_fault_point(self):
        from database.db import get_connection, insert_debt
        from services.debt_payment_service import DebtPaymentService

        for hook_point in (
            "after_transaction",
            "after_balance",
            "before_commit",
        ):
            with self.subTest(fault=hook_point):
                account_id = self.create_account()
                insert_debt(
                    f"Audit {hook_point}", 300.0, 100.0, 3,
                    is_auto_pay=1, auto_pay_day=1,
                )
                with closing(get_connection()) as conn, conn:
                    debt_id = conn.execute(
                        "SELECT id FROM active_debts ORDER BY id DESC LIMIT 1"
                    ).fetchone()[0]

                def _state():
                    with closing(get_connection()) as conn, conn:
                        row = conn.execute(
                            "SELECT paid_installments, last_auto_pay_date, "
                            "is_active FROM active_debts WHERE id=?",
                            (debt_id,),
                        ).fetchone()
                        txs = conn.execute(
                            "SELECT COUNT(*) FROM transactions "
                            "WHERE category='Kredi Taksiti'"
                        ).fetchone()[0]
                        evs = conn.execute(
                            "SELECT COUNT(*) FROM balance_events "
                            "WHERE source='debt_payment'"
                        ).fetchone()[0]
                    return (row[0], row[1], row[2], txs, evs,
                            self.balance(account_id))

                before = _state()

                fired = []

                def _fault(point, _target=hook_point):
                    if point == _target:
                        fired.append(point)
                        raise OSError(f"injected at {point}")

                raised = None
                try:
                    DebtPaymentService.pay_auto(
                        debt_id, account_id, 1, "2026-08", _fault_hook=_fault
                    )
                except OSError as exc:
                    raised = str(exc)
                self.assertEqual(
                    fired, [hook_point],
                    f"{hook_point} noktasına HİÇ ULAŞILMADI",
                )

                after = _state()
                print(
                    f"AUDIT_STATE debt_payment_fault point={hook_point} "
                    f"raised={raised!r} "
                    f"paid={before[0]}->{after[0]} "
                    f"last_pay={before[1]}->{after[1]} "
                    f"txs={before[3]}->{after[3]} events={before[4]}->{after[4]} "
                    f"balance={before[5]}->{after[5]}"
                )
                self.assertIsNotNone(raised, "fault enjekte edilemedi")
                self.assertEqual(
                    after, before,
                    f"{hook_point} noktasında yarım state kaldı",
                )
