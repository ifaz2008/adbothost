from datetime import timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.masking import mask_secrets
from app.core.security import utcnow
from app.models import AbuseFlag, Bot, BotEnvVar, BotLog, BotVersion, Deployment, User
from app.schemas import (
    BotCreate,
    BotRead,
    BotUpdate,
    BotVersionRead,
    DeployRequest,
    DeploymentRead,
    EnvVarRead,
    EnvVarUpsert,
    RuntimeRedeemRequest,
    RuntimeRedeemResponse,
)
from app.services.commands import validate_runtime_command, validate_start_command
from app.services.credits import apply_credit_transaction
from app.services.node_scheduler import choose_worker_node
from app.services.scanner import scan_zip
from app.services.storage import store_upload
from app.services.worker_client import call_worker_json, deploy_to_worker


router = APIRouter(prefix="/bots", tags=["bots"])
BASE_RUNTIME_HOURS_PER_CREDIT = 6


def _owned_bot(db: Session, bot_id: int, user: User) -> Bot:
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.user_id == user.id, Bot.is_deleted.is_(False)).one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    return bot


def _secret_values(bot: Bot) -> list[str]:
    return [env.value for env in bot.env_vars if env.is_secret]


def _as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _active_runtime_required(bot: Bot) -> None:
    active_until = _as_utc(bot.active_until)
    if not active_until or active_until <= utcnow():
        raise HTTPException(status_code=402, detail="Redeem credits for bot runtime before deploying or restarting.")


@router.get("", response_model=list[BotRead])
def list_bots(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Bot]:
    return (
        db.query(Bot)
        .filter(Bot.user_id == current_user.id, Bot.is_deleted.is_(False))
        .order_by(Bot.created_at.desc())
        .all()
    )


@router.post("", response_model=BotRead)
def create_bot(payload: BotCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Bot:
    validate_start_command(payload.start_command)
    plan = current_user.plan
    if not plan:
        raise HTTPException(status_code=400, detail="User has no plan.")
    active_count = (
        db.query(func.count(Bot.id))
        .filter(Bot.user_id == current_user.id, Bot.is_deleted.is_(False))
        .scalar()
    )
    if active_count >= plan.max_bots:
        raise HTTPException(status_code=403, detail=f"{plan.name} allows up to {plan.max_bots} bot(s).")
    bot = Bot(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        start_command=payload.start_command,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


@router.get("/{bot_id}", response_model=BotRead)
def get_bot(bot_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Bot:
    return _owned_bot(db, bot_id, current_user)


@router.patch("/{bot_id}", response_model=BotRead)
def update_bot(
    bot_id: int,
    payload: BotUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Bot:
    bot = _owned_bot(db, bot_id, current_user)
    if payload.start_command is not None:
        validate_start_command(payload.start_command)
        bot.start_command = payload.start_command
    if payload.name is not None:
        bot.name = payload.name
    if payload.description is not None:
        bot.description = payload.description
    db.commit()
    db.refresh(bot)
    return bot


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    bot = _owned_bot(db, bot_id, current_user)
    deployments = db.query(Deployment).filter(Deployment.bot_id == bot.id, Deployment.status == "running").all()
    for deployment in deployments:
        try:
            call_worker_json(
                deployment.worker_node,
                "POST",
                f"/containers/{deployment.container_name}/stop",
                {"container_name": deployment.container_name},
            )
        except Exception as exc:  # noqa: BLE001
            db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, level="warning", message=f"Stop failed: {exc}"))
        deployment.status = "stopped"
    bot.status = "deleted"
    bot.is_deleted = True
    db.commit()
    return {"status": "deleted"}


@router.post("/{bot_id}/upload", response_model=BotVersionRead)
async def upload_bot_version(
    bot_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BotVersion:
    bot = _owned_bot(db, bot_id, current_user)
    plan = current_user.plan
    if not plan:
        raise HTTPException(status_code=400, detail="User has no plan.")

    next_version = (db.query(func.max(BotVersion.version_number)).filter(BotVersion.bot_id == bot.id).scalar() or 0) + 1
    zip_path, digest, _size = await store_upload(file, current_user.id, bot.id, next_version, plan.max_upload_size_mb)
    scan = scan_zip(str(zip_path), plan.max_upload_size_mb)

    version = BotVersion(
        bot_id=bot.id,
        version_number=next_version,
        runtime=scan.runtime,
        filename=Path(zip_path).name,
        storage_path=str(zip_path),
        sha256=digest,
        scan_status=scan.status,
        scan_severity=scan.severity,
        scan_summary=scan.summary,
    )
    db.add(version)
    db.flush()

    if scan.status in {"blocked", "review"}:
        db.add(
            AbuseFlag(
                user_id=current_user.id,
                bot_id=bot.id,
                bot_version_id=version.id,
                severity=scan.severity,
                reason=scan.summary,
                details=scan.to_json(),
            )
        )
        bot.status = "flagged" if scan.status == "review" else "blocked"

    db.commit()
    db.refresh(version)
    return version


@router.get("/{bot_id}/versions", response_model=list[BotVersionRead])
def list_versions(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BotVersion]:
    bot = _owned_bot(db, bot_id, current_user)
    return db.query(BotVersion).filter(BotVersion.bot_id == bot.id).order_by(BotVersion.version_number.desc()).all()


@router.get("/{bot_id}/env", response_model=list[EnvVarRead])
def list_env_vars(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    bot = _owned_bot(db, bot_id, current_user)
    return [
        {"id": env.id, "key": env.key, "value": "********", "is_secret": env.is_secret, "updated_at": env.updated_at}
        for env in bot.env_vars
    ]


@router.post("/{bot_id}/env", response_model=EnvVarRead)
def upsert_env_var(
    bot_id: int,
    payload: EnvVarUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    bot = _owned_bot(db, bot_id, current_user)
    key = payload.key.strip().upper()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        raise HTTPException(status_code=400, detail="Environment variable keys must be uppercase letters, numbers, and underscores.")
    env = db.query(BotEnvVar).filter(BotEnvVar.bot_id == bot.id, BotEnvVar.key == key).one_or_none()
    if env:
        env.value = payload.value
        env.is_secret = payload.is_secret
    else:
        env = BotEnvVar(bot_id=bot.id, key=key, value=payload.value, is_secret=payload.is_secret)
        db.add(env)
    db.commit()
    db.refresh(env)
    return {"id": env.id, "key": env.key, "value": "********", "is_secret": env.is_secret, "updated_at": env.updated_at}


@router.delete("/{bot_id}/env/{key}")
def delete_env_var(
    bot_id: int,
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    bot = _owned_bot(db, bot_id, current_user)
    env = db.query(BotEnvVar).filter(BotEnvVar.bot_id == bot.id, BotEnvVar.key == key.upper()).one_or_none()
    if env:
        db.delete(env)
        db.commit()
    return {"status": "deleted"}


@router.post("/{bot_id}/redeem-credits", response_model=RuntimeRedeemResponse)
def redeem_credits_for_runtime(
    bot_id: int,
    payload: RuntimeRedeemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RuntimeRedeemResponse:
    bot = _owned_bot(db, bot_id, current_user)
    plan = current_user.plan
    if not plan:
        raise HTTPException(status_code=400, detail="User has no plan.")

    credits = round(float(payload.credits), 6)
    multiplier = float(plan.credit_multiplier or 1)
    runtime_hours = credits * BASE_RUNTIME_HOURS_PER_CREDIT / multiplier
    now = utcnow()
    current_expiry = _as_utc(bot.active_until)
    starts_at = current_expiry if current_expiry and current_expiry > now else now
    bot.active_until = starts_at + timedelta(hours=runtime_hours)

    account = apply_credit_transaction(
        db,
        user_id=current_user.id,
        amount=-credits,
        reason="runtime_redemption",
        reference=f"bot:{bot.id}",
        reference_type="runtime_redemption",
        visible_reason=f"Redeemed {credits:g} credits for {bot.name}",
        internal_reason=f"{runtime_hours:.4f} runtime hours on {plan.name} (multiplier {multiplier:g}).",
    )
    db.add(BotLog(bot_id=bot.id, message=f"Redeemed {credits:g} credits for runtime until {bot.active_until.isoformat()}."))
    db.commit()
    db.refresh(bot)
    return RuntimeRedeemResponse(
        bot_id=bot.id,
        credits_redeemed=credits,
        runtime_hours_added=runtime_hours,
        active_until=bot.active_until,
        balance=account.balance,
    )


@router.post("/{bot_id}/deploy", response_model=DeploymentRead)
def deploy_bot(
    bot_id: int,
    payload: DeployRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    bot = _owned_bot(db, bot_id, current_user)
    _active_runtime_required(bot)

    version_query = db.query(BotVersion).filter(BotVersion.bot_id == bot.id)
    if payload.version_id:
        version_query = version_query.filter(BotVersion.id == payload.version_id)
    version = version_query.order_by(BotVersion.version_number.desc()).first()
    if not version:
        raise HTTPException(status_code=400, detail="Upload a clean bot ZIP before deploying.")
    if version.scan_status != "clean":
        raise HTTPException(status_code=403, detail="This bot version is blocked or waiting for admin review.")

    command = validate_runtime_command(bot.start_command, version.runtime)
    plan = current_user.plan
    if not plan:
        raise HTTPException(status_code=400, detail="User has no plan.")
    node = choose_worker_node(db, plan.memory_mb, plan.storage_mb)
    if not node:
        raise HTTPException(status_code=503, detail="No healthy worker node has enough capacity.")

    deployment = Deployment(
        bot_id=bot.id,
        bot_version_id=version.id,
        worker_node_id=node.id,
        status="pending",
        cpu=plan.cpu,
        memory_mb=plan.memory_mb,
        storage_mb=plan.storage_mb,
    )
    db.add(deployment)
    db.flush()

    metadata = {
        "app": "adbothost",
        "bot_id": bot.id,
        "deployment_id": deployment.id,
        "version_id": version.id,
        "runtime": version.runtime,
        "start_command": command,
        "env": {env.key: env.value for env in bot.env_vars},
        "sha256": version.sha256,
        "resources": {
            "cpu": plan.cpu,
            "memory_mb": plan.memory_mb,
            "storage_mb": plan.storage_mb,
            "pids_limit": 128,
        },
    }

    try:
        result = deploy_to_worker(node, version.storage_path, metadata)
        deployment.container_id = result.get("container_id")
        deployment.container_name = result.get("container_name")
        deployment.image_tag = result.get("image_tag")
        deployment.status = "running"
        deployment.started_at = utcnow()
        deployment.last_credit_charge_at = deployment.started_at
        bot.status = "running"
        db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, message="Deployment started."))
    except Exception as exc:  # noqa: BLE001
        deployment.status = "failed"
        bot.status = "failed"
        db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, level="error", message=mask_secrets(str(exc), _secret_values(bot))))
        db.commit()
        raise HTTPException(status_code=502, detail="Worker deployment failed.") from exc

    db.commit()
    db.refresh(deployment)
    return deployment


@router.post("/{bot_id}/stop")
def stop_bot(bot_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    bot = _owned_bot(db, bot_id, current_user)
    deployment = (
        db.query(Deployment)
        .filter(Deployment.bot_id == bot.id, Deployment.status == "running")
        .order_by(Deployment.created_at.desc())
        .first()
    )
    if not deployment:
        bot.status = "stopped"
        db.commit()
        return {"status": "stopped"}
    call_worker_json(
        deployment.worker_node,
        "POST",
        f"/containers/{deployment.container_name}/stop",
        {"container_name": deployment.container_name},
    )
    deployment.status = "stopped"
    bot.status = "stopped"
    db.commit()
    return {"status": "stopped"}


@router.post("/{bot_id}/restart", response_model=DeploymentRead)
def restart_bot(bot_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Deployment:
    bot = _owned_bot(db, bot_id, current_user)
    _active_runtime_required(bot)
    deployment = (
        db.query(Deployment)
        .filter(Deployment.bot_id == bot.id, Deployment.status.in_(["running", "crashed"]))
        .order_by(Deployment.created_at.desc())
        .first()
    )
    if not deployment:
        return deploy_bot(bot_id, DeployRequest(), current_user, db)
    result = call_worker_json(
        deployment.worker_node,
        "POST",
        f"/containers/{deployment.container_name}/restart",
        {"container_name": deployment.container_name},
    )
    deployment.status = "running"
    deployment.restart_count += 1
    bot.status = "running"
    db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, message=f"Restarted: {result.get('status', 'ok')}"))
    db.commit()
    db.refresh(deployment)
    return deployment
