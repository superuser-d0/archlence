from services.account_service import AccountService

try:
    AccountService.create_account(
        name="Test Card",
        account_type="credit_card",
        initial_balance=100.0,
        credit_limit=5000.0,
        statement_date=15
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
