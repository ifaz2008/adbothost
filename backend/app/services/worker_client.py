import json
from datetime import timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.security import sign_payload, utcnow
from app.models import WorkerNode


def _timestamp() -> str:
    return utcnow().astimezone(timezone.utc).isoformat()


def _signed_headers(payload: bytes, token: str) -> dict[str, str]:
    timestamp = _timestamp()
    return {
        "Authorization": f"Bearer {token}",
        "X-Controller-Timestamp": timestamp,
        "X-Controller-Signature": sign_payload(payload, token, timestamp),
    }


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def deploy_to_worker(node: WorkerNode, zip_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
    metadata_bytes = _json_bytes(metadata)
    headers = _signed_headers(metadata_bytes, node.token)
    with httpx.Client(timeout=300) as client:
        with Path(zip_path).open("rb") as archive:
            response = client.post(
                f"{node.base_url.rstrip('/')}/containers/deploy",
                headers=headers,
                data={"metadata": metadata_bytes.decode("utf-8")},
                files={"archive": (Path(zip_path).name, archive, "application/zip")},
            )
    response.raise_for_status()
    return response.json()


def call_worker_json(node: WorkerNode, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = _json_bytes(payload or {})
    headers = _signed_headers(body, node.token)
    headers["Content-Type"] = "application/json"
    with httpx.Client(timeout=60) as client:
        response = client.request(
            method,
            f"{node.base_url.rstrip('/')}/{path.lstrip('/')}",
            headers=headers,
            content=body,
        )
    response.raise_for_status()
    return response.json()


def get_worker_logs(node: WorkerNode, container_name: str, tail: int = 200) -> str:
    body = _json_bytes({})
    headers = _signed_headers(body, node.token)
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{node.base_url.rstrip('/')}/containers/{container_name}/logs",
            headers=headers,
            params={"tail": tail},
        )
    response.raise_for_status()
    return response.text
