from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_db
from app.core.config import settings
from app.core.security import utcnow
from app.models import AbuseFlag, Bot, CreditTransaction, Deployment, User, WorkerNode
from app.schemas import (
    AbuseFlagRead,
    AdminCreditTransactionRead,
    BotRead,
    CreditAdjustmentRequest,
    DeploymentRead,
    UserRead,
    WorkerNodeRead,
)
from app.services.credits import apply_credit_transaction, ensure_credit_account
from app.services.worker_client import call_worker_json


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
def admin_list_users(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).limit(250).all()


@router.get("/bots", response_model=list[BotRead])
def admin_list_bots(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[Bot]:
    return db.query(Bot).order_by(Bot.created_at.desc()).limit(250).all()


@router.get("/deployments", response_model=list[DeploymentRead])
def admin_list_deployments(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[Deployment]:
    return db.query(Deployment).order_by(Deployment.created_at.desc()).limit(250).all()


@router.get("/abuse-flags", response_model=list[AbuseFlagRead])
def admin_list_abuse_flags(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[AbuseFlag]:
    return db.query(AbuseFlag).order_by(AbuseFlag.created_at.desc()).limit(250).all()


@router.post("/users/{user_id}/suspend", response_model=UserRead)
def admin_suspend_user(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_suspended = True
    for bot in user.bots:
        bot.status = "suspended"
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/unsuspend", response_model=UserRead)
def admin_unsuspend_user(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_suspended = False
    db.commit()
    db.refresh(user)
    return user


@router.post("/bots/{bot_id}/stop")
def admin_stop_bot(bot_id: int, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, str]:
    bot = db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    deployments = db.query(Deployment).filter(Deployment.bot_id == bot.id, Deployment.status == "running").all()
    for deployment in deployments:
        if deployment.container_name:
            try:
                call_worker_json(
                    deployment.worker_node,
                    "POST",
                    f"/containers/{deployment.container_name}/stop",
                    {"container_name": deployment.container_name},
                )
            except Exception:
                pass
        deployment.status = "stopped"
        deployment.stopped_at = utcnow()
    bot.status = "stopped"
    db.commit()
    return {"status": "stopped"}


@router.delete("/bots/{bot_id}")
def admin_delete_bot(bot_id: int, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, str]:
    bot = db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    admin_stop_bot(bot_id, _admin, db)
    bot.is_deleted = True
    bot.status = "deleted"
    db.commit()
    return {"status": "deleted"}


@router.post("/abuse-flags/{flag_id}/approve", response_model=AbuseFlagRead)
def admin_approve_flag(
    flag_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> AbuseFlag:
    flag = db.get(AbuseFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found.")
    flag.status = "approved"
    flag.reviewed_by_id = admin.id
    flag.reviewed_at = utcnow()
    if flag.version:
        flag.version.scan_status = "clean"
        flag.version.scan_severity = "low"
    flag.bot.status = "created"
    db.commit()
    db.refresh(flag)
    return flag


@router.post("/abuse-flags/{flag_id}/reject", response_model=AbuseFlagRead)
def admin_reject_flag(
    flag_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> AbuseFlag:
    flag = db.get(AbuseFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found.")
    flag.status = "rejected"
    flag.reviewed_by_id = admin.id
    flag.reviewed_at = utcnow()
    if flag.version:
        flag.version.scan_status = "blocked"
        flag.version.scan_severity = "high"
    flag.bot.status = "blocked"
    db.commit()
    db.refresh(flag)
    return flag


@router.get("/node-health", response_model=list[WorkerNodeRead])
def admin_node_health(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[WorkerNode]:
    return db.query(WorkerNode).order_by(WorkerNode.name).all()


@router.get("/credit-transactions", response_model=list[AdminCreditTransactionRead])
def admin_credit_transactions(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[CreditTransaction]:
    return db.query(CreditTransaction).order_by(CreditTransaction.created_at.desc()).limit(500).all()


@router.post("/users/{user_id}/credit-adjustment", response_model=AdminCreditTransactionRead)
def admin_credit_adjustment(
    user_id: int,
    payload: CreditAdjustmentRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> CreditTransaction:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="Adjustment amount cannot be 0.")

    ensure_credit_account(db, user.id)
    previous_count = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).count()
    apply_credit_transaction(
        db,
        user_id=user.id,
        amount=payload.amount,
        reason=payload.reference_type,
        reference=f"admin:{admin.id}:adjustment:{previous_count + 1}",
        reference_type=payload.reference_type,
        visible_reason=payload.visible_reason,
        internal_reason=payload.internal_reason,
        admin_id=admin.id,
        allow_negative_balance=settings.allow_negative_credits,
    )
    transaction = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
        .first()
    )
    db.commit()
    db.refresh(transaction)
    return transaction
