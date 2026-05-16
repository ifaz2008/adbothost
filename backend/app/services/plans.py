from sqlalchemy.orm import Session

from app.models import Plan


DEFAULT_PLANS = [
    {
        "name": "1x Basic",
        "max_bots": 1,
        "cpu": 0.10,
        "memory_mb": 128,
        "storage_mb": 250,
        "max_upload_size_mb": 50,
        "runtime_per_credit_hours": 6,
        "credit_multiplier": 1,
    },
    {
        "name": "2x Plus",
        "max_bots": 3,
        "cpu": 0.20,
        "memory_mb": 256,
        "storage_mb": 500,
        "max_upload_size_mb": 100,
        "runtime_per_credit_hours": 6,
        "credit_multiplier": 2,
    },
    {
        "name": "4x Boost",
        "max_bots": 6,
        "cpu": 0.40,
        "memory_mb": 512,
        "storage_mb": 1024,
        "max_upload_size_mb": 150,
        "runtime_per_credit_hours": 6,
        "credit_multiplier": 4,
    },
    {
        "name": "8x Max",
        "max_bots": 10,
        "cpu": 0.80,
        "memory_mb": 1024,
        "storage_mb": 2048,
        "max_upload_size_mb": 200,
        "runtime_per_credit_hours": 6,
        "credit_multiplier": 8,
    },
]


def ensure_default_plans(db: Session) -> None:
    for plan_data in DEFAULT_PLANS:
        plan = db.query(Plan).filter(Plan.name == plan_data["name"]).one_or_none()
        if plan:
            for key, value in plan_data.items():
                setattr(plan, key, value)
        else:
            db.add(Plan(**plan_data))
    db.commit()


def get_free_plan(db: Session) -> Plan:
    plan = db.query(Plan).filter(Plan.name == "1x Basic").one_or_none()
    if not plan:
        ensure_default_plans(db)
        plan = db.query(Plan).filter(Plan.name == "1x Basic").one()
    return plan
