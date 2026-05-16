from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user, get_db
from app.core.config import settings
from app.core.security import utcnow
from app.models import PaymentRequest, User
from app.schemas import (
    AdminPaymentRequestRead,
    PaymentConfigRead,
    PaymentRequestCreate,
    PaymentRequestRead,
    PaymentReviewRequest,
)
from app.services.credits import add_credits


router = APIRouter(prefix="/payment-requests", tags=["payment requests"])
admin_router = APIRouter(prefix="/admin/payment-requests", tags=["admin payment requests"])


def _normalize_transaction_id(transaction_id: str) -> str:
    return transaction_id.strip().upper()


@router.get("/config", response_model=PaymentConfigRead)
def payment_config() -> PaymentConfigRead:
    return PaymentConfigRead(
        enabled=settings.manual_payment_enabled,
        provider_name=settings.manual_payment_provider_name,
        receiver_id=settings.manual_payment_receiver_id,
        instructions=settings.manual_payment_instructions,
        currency=settings.manual_payment_currency,
    )


@router.post("", response_model=PaymentRequestRead)
def create_payment_request(
    payload: PaymentRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRequest:
    if not settings.manual_payment_enabled:
        raise HTTPException(status_code=403, detail="Manual payments are currently disabled.")

    tx_id = _normalize_transaction_id(payload.transaction_id)
    approved_duplicate = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.transaction_id == tx_id, PaymentRequest.status == "approved")
        .first()
    )
    if approved_duplicate:
        raise HTTPException(status_code=409, detail="This transaction ID has already been approved.")

    request = PaymentRequest(
        user_id=current_user.id,
        payment_method=payload.payment_method.strip(),
        payer_binance_id=payload.payer_binance_id.strip(),
        transaction_id=tx_id,
        amount_paid=payload.amount_paid.strip(),
        currency=payload.currency.strip().upper(),
        requested_credits=payload.requested_credits,
        proof_note=payload.proof_note,
        proof_image_url=payload.proof_image_url,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/my", response_model=list[PaymentRequestRead])
def my_payment_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PaymentRequest]:
    return (
        db.query(PaymentRequest)
        .filter(PaymentRequest.user_id == current_user.id)
        .order_by(PaymentRequest.created_at.desc())
        .limit(100)
        .all()
    )


@admin_router.get("", response_model=list[AdminPaymentRequestRead])
def admin_list_payment_requests(
    status: str | None = None,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[PaymentRequest]:
    query = db.query(PaymentRequest)
    if status:
        query = query.filter(PaymentRequest.status == status)
    return query.order_by(PaymentRequest.created_at.desc()).limit(500).all()


@admin_router.post("/{request_id}/approve", response_model=AdminPaymentRequestRead)
def approve_payment_request(
    request_id: int,
    payload: PaymentReviewRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> PaymentRequest:
    request = db.get(PaymentRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found.")
    if request.status == "approved":
        return request

    duplicate = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.id != request.id,
            PaymentRequest.transaction_id == request.transaction_id,
            PaymentRequest.status == "approved",
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Another payment request with this transaction ID is already approved.")

    request.status = "approved"
    request.admin_note = payload.admin_note
    request.reviewed_by_admin_id = admin.id
    request.reviewed_at = utcnow()
    add_credits(
        db,
        request.user_id,
        float(request.requested_credits),
        "manual_payment",
        reference=f"payment_request:{request.id}:{request.transaction_id}",
        reference_type="manual_payment",
        visible_reason=f"Manual payment approved ({request.currency})",
        internal_reason=payload.admin_note,
        admin_id=admin.id,
    )
    db.commit()
    db.refresh(request)
    return request


@admin_router.post("/{request_id}/reject", response_model=AdminPaymentRequestRead)
def reject_payment_request(
    request_id: int,
    payload: PaymentReviewRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> PaymentRequest:
    request = db.get(PaymentRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found.")
    if request.status == "approved":
        raise HTTPException(status_code=400, detail="Approved payment requests cannot be rejected.")
    request.status = "rejected"
    request.admin_note = payload.admin_note
    request.reviewed_by_admin_id = admin.id
    request.reviewed_at = utcnow()
    db.commit()
    db.refresh(request)
    return request


@admin_router.post("/{request_id}/needs-more-info", response_model=AdminPaymentRequestRead)
def mark_payment_needs_more_info(
    request_id: int,
    payload: PaymentReviewRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> PaymentRequest:
    request = db.get(PaymentRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Payment request not found.")
    if request.status == "approved":
        raise HTTPException(status_code=400, detail="Approved payment requests cannot be changed to needs_more_info.")
    request.status = "needs_more_info"
    request.admin_note = payload.admin_note
    request.reviewed_by_admin_id = admin.id
    request.reviewed_at = utcnow()
    db.commit()
    db.refresh(request)
    return request
