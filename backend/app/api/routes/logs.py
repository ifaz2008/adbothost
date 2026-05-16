from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.masking import mask_secrets
from app.models import Bot, BotLog, Deployment, User
from app.schemas import BotLogRead
from app.services.worker_client import get_worker_logs


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/bots/{bot_id}", response_model=list[BotLogRead])
def read_bot_logs(
    bot_id: int,
    tail: int = Query(200, ge=1, le=1000),
    include_worker: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BotLog]:
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.user_id == current_user.id, Bot.is_deleted.is_(False)).one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")

    if include_worker:
        deployment = (
            db.query(Deployment)
            .filter(Deployment.bot_id == bot.id, Deployment.status == "running")
            .order_by(Deployment.created_at.desc())
            .first()
        )
        if deployment and deployment.container_name:
            try:
                raw = get_worker_logs(deployment.worker_node, deployment.container_name, tail=tail)
                masked = mask_secrets(raw, [env.value for env in bot.env_vars if env.is_secret])
                for line in masked.splitlines()[-tail:]:
                    if line.strip():
                        db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, level="stdout", message=line[:4000]))
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.add(BotLog(bot_id=bot.id, deployment_id=deployment.id, level="warning", message=f"Could not fetch worker logs: {exc}"))
                db.commit()

    return (
        db.query(BotLog)
        .filter(BotLog.bot_id == bot.id)
        .order_by(BotLog.created_at.desc())
        .limit(tail)
        .all()
    )
