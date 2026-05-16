from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import WorkerNode


def choose_worker_node(db: Session, memory_mb: int, storage_mb: int) -> WorkerNode | None:
    cutoff = utcnow() - timedelta(minutes=2)
    candidates = (
        db.query(WorkerNode)
        .filter(WorkerNode.is_active.is_(True))
        .filter(WorkerNode.status == "healthy")
        .filter(WorkerNode.last_heartbeat_at.isnot(None))
        .filter(WorkerNode.last_heartbeat_at >= cutoff)
        .all()
    )

    healthy: list[WorkerNode] = []
    for node in candidates:
        if node.running_containers >= node.max_containers:
            continue
        available_memory = max(node.memory_total_mb - node.memory_used_mb, 0)
        available_disk = max(node.disk_total_mb - node.disk_used_mb, 0)
        if available_memory < memory_mb:
            continue
        if available_disk < storage_mb:
            continue
        if node.cpu_percent >= 85:
            continue
        healthy.append(node)

    if not healthy:
        return None

    def load_score(node: WorkerNode) -> float:
        memory_ratio = node.memory_used_mb / node.memory_total_mb if node.memory_total_mb else 1
        disk_ratio = node.disk_used_mb / node.disk_total_mb if node.disk_total_mb else 1
        container_ratio = node.running_containers / node.max_containers if node.max_containers else 1
        return node.cpu_percent / 100 + memory_ratio + disk_ratio + container_ratio

    return min(healthy, key=load_score)
