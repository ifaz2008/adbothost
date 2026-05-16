from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user, get_db
from app.core.security import utcnow
from app.models import Coupon, CouponRedemption, User
from app.schemas import (
    CouponCreate,
    CouponRead,
    CouponRedeemRequest,
    CouponRedeemResponse,
    CouponRedemptionRead,
    CouponUpdate,
)
from app.services.credits import add_credits


router = APIRouter(prefix="/coupons", tags=["coupons"])
admin_router = APIRouter(prefix="/admin/coupons", tags=["admin coupons"])


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _credits_for_coupon(coupon: Coupon) -> float:
    base = float(coupon.credit_amount)
    if coupon.percent_bonus:
        base = base * (1 + float(coupon.percent_bonus) / 100)
    return round(base, 6)


@router.post("/redeem", response_model=CouponRedeemResponse)
def redeem_coupon(
    payload: CouponRedeemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CouponRedeemResponse:
    code = _normalize_code(payload.code)
    coupon = db.query(Coupon).filter(Coupon.code == code).one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon code not found.")
    if not coupon.active:
        raise HTTPException(status_code=400, detail="Coupon is inactive.")

    now = utcnow()
    starts_at = _aware(coupon.starts_at)
    expires_at = _aware(coupon.expires_at)
    if starts_at and starts_at > now:
        raise HTTPException(status_code=400, detail="Coupon is not active yet.")
    if expires_at and expires_at < now:
        raise HTTPException(status_code=400, detail="Coupon has expired.")

    total_uses = db.query(func.count(CouponRedemption.id)).filter(CouponRedemption.coupon_id == coupon.id).scalar() or 0
    if coupon.max_uses_total is not None and total_uses >= coupon.max_uses_total:
        raise HTTPException(status_code=400, detail="Coupon has reached its total use limit.")

    user_uses = (
        db.query(func.count(CouponRedemption.id))
        .filter(CouponRedemption.coupon_id == coupon.id, CouponRedemption.user_id == current_user.id)
        .scalar()
        or 0
    )
    if user_uses >= coupon.max_uses_per_user:
        raise HTTPException(status_code=400, detail="You have already used this coupon the maximum number of times.")

    credits_added = _credits_for_coupon(coupon)
    redemption = CouponRedemption(coupon_id=coupon.id, user_id=current_user.id, credits_added=credits_added)
    db.add(redemption)
    account = add_credits(
        db,
        current_user.id,
        credits_added,
        "coupon_redemption",
        reference=f"coupon:{coupon.code}",
        reference_type="coupon",
        visible_reason=f"Coupon {coupon.code}",
    )
    db.commit()
    return CouponRedeemResponse(redeemed=True, credits_added=credits_added, balance=account.balance, code=coupon.code)


@router.get("/my-redemptions", response_model=list[CouponRedemptionRead])
def my_coupon_redemptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CouponRedemption]:
    return (
        db.query(CouponRedemption)
        .filter(CouponRedemption.user_id == current_user.id)
        .order_by(CouponRedemption.redeemed_at.desc())
        .limit(100)
        .all()
    )


@admin_router.post("", response_model=CouponRead)
def create_coupon(
    payload: CouponCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Coupon:
    code = _normalize_code(payload.code)
    existing = db.query(Coupon).filter(Coupon.code == code).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Coupon code already exists.")
    if payload.starts_at and payload.expires_at and _aware(payload.starts_at) >= _aware(payload.expires_at):
        raise HTTPException(status_code=400, detail="Coupon expires_at must be after starts_at.")
    coupon = Coupon(**payload.model_dump(exclude={"code"}), code=code, created_by_admin_id=admin.id)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@admin_router.get("", response_model=list[CouponRead])
def list_coupons(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[Coupon]:
    return db.query(Coupon).order_by(Coupon.created_at.desc()).limit(250).all()


@admin_router.patch("/{coupon_id}", response_model=CouponRead)
def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    data = payload.model_dump(exclude_unset=True)
    starts_at = _aware(data.get("starts_at", coupon.starts_at))
    expires_at = _aware(data.get("expires_at", coupon.expires_at))
    if starts_at and expires_at and starts_at >= expires_at:
        raise HTTPException(status_code=400, detail="Coupon expires_at must be after starts_at.")
    for key, value in data.items():
        setattr(coupon, key, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@admin_router.post("/{coupon_id}/disable", response_model=CouponRead)
def disable_coupon(
    coupon_id: int,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    coupon.active = False
    db.commit()
    db.refresh(coupon)
    return coupon
