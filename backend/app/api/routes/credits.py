from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import CreditTransaction, User
from app.schemas import CreditSummary, CreditTransactionRead
from app.services.credits import ensure_credit_account


router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/me", response_model=CreditSummary)
def credit_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CreditSummary:
    account = ensure_credit_account(db, current_user.id)
    plan = current_user.plan
    return CreditSummary(
        balance=account.balance,
        runtime_per_credit_hours=6,
        credit_multiplier=plan.credit_multiplier if plan else 1,
        plan_name=plan.name if plan else None,
    )


@router.get("/transactions", response_model=list[CreditTransactionRead])
def my_credit_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CreditTransaction]:
    return (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(100)
        .all()
    )
