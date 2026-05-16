import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models import AdReward, User
from app.schemas import AdRewardCallback, AdRewardResponse
from app.services.credits import add_credits, ensure_credit_account
from app.services.plans import get_free_plan


router = APIRouter(prefix="/ad-rewards", tags=["ad rewards"])


def _find_or_create_user(db: Session, payload: AdRewardCallback) -> User:
    query = None
    if payload.user_id is not None:
        query = User.id == payload.user_id
    elif payload.email:
        query = User.email == payload.email.lower()
    elif payload.telegram_id:
        query = User.telegram_id == payload.telegram_id
    if query is None:
        raise HTTPException(status_code=400, detail="user_id, email, or telegram_id is required.")

    user = db.query(User).filter(query).one_or_none()
    if user:
        return user

    plan = get_free_plan(db)
    user = User(
        email=payload.email.lower() if payload.email else None,
        telegram_id=payload.telegram_id,
        display_name=payload.email or payload.telegram_id,
        plan_id=plan.id,
    )
    db.add(user)
    db.flush()
    ensure_credit_account(db, user.id)
    return user


@router.post("/callback", response_model=AdRewardResponse)
def rewarded_ad_callback(payload: AdRewardCallback, db: Session = Depends(get_db)) -> AdRewardResponse:
    existing = db.query(AdReward).filter(AdReward.reward_id == payload.reward_id).one_or_none()
    if existing:
        account = ensure_credit_account(db, existing.user_id)
        return AdRewardResponse(credited=False, balance=account.balance, reward_id=payload.reward_id)

    # TODO: validate the real ad provider signature before crediting production accounts.
    user = _find_or_create_user(db, payload)
    amount = payload.credits if payload.credits is not None else settings.ad_reward_credits
    if amount <= 0 or amount > 10:
        raise HTTPException(status_code=400, detail="Invalid credit amount.")

    account = add_credits(db, user.id, amount, "rewarded_ad", payload.reward_id)
    db.add(
        AdReward(
            reward_id=payload.reward_id,
            user_id=user.id,
            credits_awarded=amount,
            raw_payload=json.dumps(payload.model_dump(), sort_keys=True),
        )
    )
    db.commit()
    return AdRewardResponse(credited=True, balance=account.balance, reward_id=payload.reward_id)
