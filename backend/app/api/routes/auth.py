import hmac

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models import User
from app.schemas import AuthRequest, AuthResponse, LoginRequest, TelegramLoginRequest
from app.services.credits import ensure_credit_account
from app.services.plans import get_free_plan


router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User) -> AuthResponse:
    token = create_access_token(str(user.id), {"is_admin": user.is_admin})
    return AuthResponse(access_token=token, user=user)


@router.post("/dev-login", response_model=AuthResponse)
def dev_login(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="Development login is disabled in production.")
    plan = get_free_plan(db)
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if not user:
        user = User(
            email=payload.email.lower(),
            display_name=payload.display_name or payload.email.split("@")[0],
            plan_id=plan.id,
            is_admin=payload.email.lower() == settings.admin_email.lower(),
        )
        db.add(user)
        db.flush()
        ensure_credit_account(db, user.id)
    else:
        if payload.display_name:
            user.display_name = payload.display_name
        if payload.email.lower() == settings.admin_email.lower():
            user.is_admin = True
    db.commit()
    user = db.query(User).options(joinedload(User.plan)).filter(User.id == user.id).one()
    return _issue_token(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    # MVP placeholder auth. Replace with proper password hashing and session controls.
    valid_admin = hmac.compare_digest(payload.username, settings.admin_username) and hmac.compare_digest(
        payload.password,
        settings.admin_password,
    )
    if not valid_admin:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    plan = get_free_plan(db)
    user = db.query(User).filter(User.email == settings.admin_email.lower()).one_or_none()
    if not user:
        user = User(
            email=settings.admin_email.lower(),
            display_name=settings.admin_username,
            plan_id=plan.id,
            is_admin=True,
        )
        db.add(user)
        db.flush()
        ensure_credit_account(db, user.id)
    else:
        user.is_admin = True
        user.display_name = settings.admin_username
    db.commit()
    user = db.query(User).options(joinedload(User.plan)).filter(User.id == user.id).one()
    return _issue_token(user)


@router.post("/telegram-login", response_model=AuthResponse)
def telegram_login(payload: TelegramLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    plan = get_free_plan(db)
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).one_or_none()
    if not user:
        user = User(
            telegram_id=payload.telegram_id,
            display_name=payload.display_name or f"telegram-{payload.telegram_id}",
            plan_id=plan.id,
        )
        db.add(user)
        db.flush()
        ensure_credit_account(db, user.id)
    else:
        if payload.display_name:
            user.display_name = payload.display_name
    db.commit()
    user = db.query(User).options(joinedload(User.plan)).filter(User.id == user.id).one()
    # TODO: verify Telegram login widget signatures before production use.
    return _issue_token(user)
