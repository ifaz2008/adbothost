from app.core.config import settings
from app.core.security import utcnow
from app.db.session import SessionLocal, init_db
from app.models import User, WorkerNode
from app.services.credits import ensure_credit_account
from app.services.plans import ensure_default_plans, get_free_plan


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_default_plans(db)
        plan = get_free_plan(db)

        admin = db.query(User).filter(User.email == settings.admin_email.lower()).one_or_none()
        if not admin:
            admin = User(
                email=settings.admin_email.lower(),
                display_name=settings.admin_username,
                plan_id=plan.id,
                is_admin=True,
            )
            db.add(admin)
            db.flush()
        admin.is_admin = True
        admin.display_name = settings.admin_username
        ensure_credit_account(db, admin.id)

        node = db.query(WorkerNode).filter(WorkerNode.name == settings.worker_name).one_or_none()
        if not node:
            node = WorkerNode(
                name=settings.worker_name,
                base_url=settings.worker_public_base_url,
                token=settings.default_node_agent_token,
                status="healthy",
                cpu_percent=0,
                memory_total_mb=4096,
                memory_used_mb=0,
                disk_total_mb=20480,
                disk_used_mb=0,
                running_containers=0,
                max_containers=settings.worker_max_containers,
                is_active=True,
                last_heartbeat_at=utcnow(),
            )
            db.add(node)
        else:
            node.base_url = settings.worker_public_base_url
            node.token = settings.default_node_agent_token
            node.max_containers = settings.worker_max_containers
            node.is_active = True
            node.status = "healthy"
            node.last_heartbeat_at = utcnow()

        db.commit()
        print("Seeded default plans, admin user, and local worker node.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
