from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import CreditAccount, CreditTransaction


def ensure_credit_account(db: Session, user_id: int) -> CreditAccount:
    account = db.query(CreditAccount).filter(CreditAccount.user_id == user_id).one_or_none()
    if account:
        return account
    account = CreditAccount(user_id=user_id, balance=0.0)
    db.add(account)
    db.flush()
    return account


def apply_credit_transaction(
    db: Session,
    user_id: int,
    amount: float,
    reason: str,
    reference: str | None = None,
    reference_type: str | None = None,
    visible_reason: str | None = None,
    internal_reason: str | None = None,
    admin_id: int | None = None,
    allow_negative_balance: bool = False,
) -> CreditAccount:
    account = ensure_credit_account(db, user_id)
    next_balance = round(account.balance + amount, 6)
    if next_balance < 0 and not allow_negative_balance:
        raise HTTPException(status_code=400, detail="Credit balance cannot go below 0.")
    account.balance = next_balance
    db.add(
        CreditTransaction(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference=reference,
            reference_type=reference_type,
            visible_reason=visible_reason,
            internal_reason=internal_reason,
            admin_id=admin_id,
            balance_after=account.balance,
        )
    )
    db.flush()
    return account


def add_credits(
    db: Session,
    user_id: int,
    amount: float,
    reason: str,
    reference: str | None = None,
    reference_type: str | None = None,
    visible_reason: str | None = None,
    internal_reason: str | None = None,
    admin_id: int | None = None,
) -> CreditAccount:
    return apply_credit_transaction(
        db,
        user_id=user_id,
        amount=amount,
        reason=reason,
        reference=reference,
        reference_type=reference_type,
        visible_reason=visible_reason,
        internal_reason=internal_reason,
        admin_id=admin_id,
    )


def debit_credits(db: Session, user_id: int, amount: float, reason: str, reference: str | None = None) -> CreditAccount:
    account = ensure_credit_account(db, user_id)
    debit = min(max(amount, 0.0), account.balance)
    if debit > 0:
        return apply_credit_transaction(
            db,
            user_id=user_id,
            amount=-debit,
            reason=reason,
            reference=reference,
            reference_type="runtime",
        )
    return account
