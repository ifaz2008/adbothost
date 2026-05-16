from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_db
from app.core.config import settings
from app.core.security import utcnow
from app.models import User, WorkerNode
from app.schemas import WorkerNodeCreate, WorkerNodeHeartbeat, WorkerNodeRead


router = APIRouter(prefix="/worker-nodes", tags=["worker nodes"])


@router.get("", response_model=list[WorkerNodeRead])
def list_worker_nodes(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[WorkerNode]:
    return db.query(WorkerNode).order_by(WorkerNode.name).all()


@router.post("", response_model=WorkerNodeRead)
def register_worker_node(
    payload: WorkerNodeCreate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> WorkerNode:
    node = db.query(WorkerNode).filter(WorkerNode.name == payload.name).one_or_none()
    if node:
        node.base_url = payload.base_url
        node.token = payload.token
        node.max_containers = payload.max_containers
        node.is_active = True
    else:
        node = WorkerNode(**payload.model_dump(), status="unknown")
        db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.post("/{node_name}/heartbeat", response_model=WorkerNodeRead)
def worker_heartbeat(
    node_name: str,
    payload: WorkerNodeHeartbeat,
    x_node_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> WorkerNode:
    node = db.query(WorkerNode).filter(WorkerNode.name == node_name).one_or_none()
    if not node:
        if x_node_token != settings.default_node_agent_token:
            raise HTTPException(status_code=401, detail="Unknown worker node.")
        node = WorkerNode(
            name=node_name,
            base_url=settings.public_base_url,
            token=x_node_token,
            max_containers=payload.max_containers or 20,
            is_active=True,
        )
        db.add(node)
        db.flush()
    elif x_node_token != node.token:
        raise HTTPException(status_code=401, detail="Invalid worker token.")

    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(node, key, value)
    node.last_heartbeat_at = utcnow()
    db.commit()
    db.refresh(node)
    return node
