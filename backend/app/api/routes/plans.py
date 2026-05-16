from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Plan
from app.schemas import PlanRead


router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanRead])
def list_plans(db: Session = Depends(get_db)) -> list[Plan]:
    return db.query(Plan).order_by(Plan.id).all()
