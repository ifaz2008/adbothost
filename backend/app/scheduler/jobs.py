from datetime import timezone, timedelta

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models import BotLog, Deployment, WorkerNode
from app.services.worker_client import call_worker_json


def _aware(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _stop_deployment(db: Session, deployment: Deployment, reason: str) -> None:
    if deployment.container_name:
        try:
            call_worker_json(
                deployment.worker_node,
                "POST",
                f"/containers/{deployment.container_name}/stop",
                {"container_name": deployment.container_name},
            )
        except Exception as exc:  # noqa: BLE001
            db.add(BotLog(bot_id=deployment.bot_id, deployment_id=deployment.id, level="warning", message=f"Scheduler stop failed: {exc}"))
    deployment.status = "stopped"
    deployment.stopped_at = utcnow()
    deployment.bot.status = "stopped"
    db.add(BotLog(bot_id=deployment.bot_id, deployment_id=deployment.id, message=reason))


def stop_expired_bots() -> None:
    db = SessionLocal()
    try:
        now = utcnow()
        deployments = db.query(Deployment).filter(Deployment.status == "running").all()
        for deployment in deployments:
            active_until = _aware(deployment.bot.active_until) if deployment.bot.active_until else None
            if not active_until or active_until <= now:
                _stop_deployment(db, deployment, "Stopped because redeemed runtime expired.")
        db.commit()
    finally:
        db.close()


def restart_crashed_bots() -> None:
    db = SessionLocal()
    try:
        now = utcnow()
        deployments = db.query(Deployment).filter(Deployment.status == "crashed").all()
        for deployment in deployments:
            active_until = _aware(deployment.bot.active_until) if deployment.bot.active_until else None
            if not active_until or active_until <= now:
                _stop_deployment(db, deployment, "Crashed bot left stopped because redeemed runtime expired.")
                continue
            if not deployment.container_name:
                continue
            try:
                call_worker_json(
                    deployment.worker_node,
                    "POST",
                    f"/containers/{deployment.container_name}/restart",
                    {"container_name": deployment.container_name},
                )
                deployment.status = "running"
                deployment.bot.status = "running"
                deployment.restart_count += 1
                db.add(BotLog(bot_id=deployment.bot_id, deployment_id=deployment.id, message="Scheduler restarted crashed bot."))
            except Exception as exc:  # noqa: BLE001
                db.add(BotLog(bot_id=deployment.bot_id, deployment_id=deployment.id, level="warning", message=f"Scheduler restart failed: {exc}"))
        db.commit()
    finally:
        db.close()


def sync_container_statuses() -> None:
    db = SessionLocal()
    try:
        deployments = db.query(Deployment).filter(Deployment.status == "running").all()
        for deployment in deployments:
            if not deployment.container_name:
                continue
            try:
                data = call_worker_json(
                    deployment.worker_node,
                    "POST",
                    f"/containers/{deployment.container_name}/status",
                    {"container_name": deployment.container_name},
                )
                if data.get("status") not in {"running", "restarting"}:
                    deployment.status = "crashed"
                    deployment.bot.status = "crashed"
                    db.add(
                        BotLog(
                            bot_id=deployment.bot_id,
                            deployment_id=deployment.id,
                            level="warning",
                            message=f"Container exited with status {data.get('status')} and code {data.get('exit_code')}.",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                db.add(BotLog(bot_id=deployment.bot_id, deployment_id=deployment.id, level="warning", message=f"Status check failed: {exc}"))
        db.commit()
    finally:
        db.close()


def refresh_worker_nodes() -> None:
    db = SessionLocal()
    try:
        now = utcnow()
        for node in db.query(WorkerNode).filter(WorkerNode.is_active.is_(True)).all():
            try:
                response = httpx.get(
                    f"{node.base_url.rstrip('/')}/stats",
                    headers={"Authorization": f"Bearer {node.token}"},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                node.status = data.get("status", "healthy")
                node.cpu_percent = data.get("cpu_percent", node.cpu_percent)
                node.memory_total_mb = data.get("memory_total_mb", node.memory_total_mb)
                node.memory_used_mb = data.get("memory_used_mb", node.memory_used_mb)
                node.disk_total_mb = data.get("disk_total_mb", node.disk_total_mb)
                node.disk_used_mb = data.get("disk_used_mb", node.disk_used_mb)
                node.running_containers = data.get("running_containers", node.running_containers)
                node.max_containers = data.get("max_containers", node.max_containers)
                node.last_heartbeat_at = now
            except Exception:
                if not node.last_heartbeat_at or node.last_heartbeat_at < now - timedelta(minutes=3):
                    node.status = "unhealthy"
        db.commit()
    finally:
        db.close()


def mark_stale_nodes_unhealthy() -> None:
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(minutes=3)
        nodes = (
            db.query(WorkerNode)
            .filter(WorkerNode.is_active.is_(True))
            .filter(WorkerNode.last_heartbeat_at.isnot(None))
            .filter(WorkerNode.last_heartbeat_at < cutoff)
            .all()
        )
        for node in nodes:
            node.status = "unhealthy"
        db.commit()
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(refresh_worker_nodes, "interval", seconds=60, id="refresh_worker_nodes", replace_existing=True)
    scheduler.add_job(stop_expired_bots, "interval", seconds=60, id="stop_expired_bots", replace_existing=True)
    scheduler.add_job(sync_container_statuses, "interval", seconds=60, id="sync_container_statuses", replace_existing=True)
    scheduler.add_job(restart_crashed_bots, "interval", seconds=60, id="restart_crashed_bots", replace_existing=True)
    scheduler.add_job(mark_stale_nodes_unhealthy, "interval", seconds=60, id="mark_stale_nodes_unhealthy", replace_existing=True)
    return scheduler
