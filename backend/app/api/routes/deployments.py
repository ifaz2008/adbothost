from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Bot, Deployment, User
from app.schemas import DeploymentRead


router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("", response_model=list[DeploymentRead])
def list_deployments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Deployment]:
    return (
        db.query(Deployment)
        .join(Bot, Bot.id == Deployment.bot_id)
        .filter(Bot.user_id == current_user.id)
        .order_by(Deployment.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/{deployment_id}", response_model=DeploymentRead)
def get_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    deployment = db.get(Deployment, deployment_id)
    if not deployment or deployment.bot.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return deployment
