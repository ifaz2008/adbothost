import json
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.docker_ops import (
    container_logs,
    delete_container,
    deploy_container,
    node_stats,
    restart_container,
    start_container,
    status_container,
    stop_container,
)
from app.security import _verify_bearer, signed_json, verify_metadata_signature


app = FastAPI(title="AdBotHost Worker Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "worker"}


@app.get("/stats")
def stats(_auth: None = Depends(_verify_bearer)) -> dict:
    return node_stats()


@app.post("/containers/deploy")
async def deploy(
    metadata: str = Form(...),
    archive: UploadFile = File(...),
    authorization: str = Header(default=""),
    x_controller_timestamp: str = Header(default=""),
    x_controller_signature: str = Header(default=""),
) -> dict:
    verify_metadata_signature(metadata, authorization, x_controller_timestamp, x_controller_signature)
    parsed = json.loads(metadata)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
        temp_path = Path(temp_file.name)
        while chunk := await archive.read(1024 * 1024):
            temp_file.write(chunk)
    try:
        return deploy_container(temp_path, parsed)
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/containers/{container_name}/start")
async def start(container_name: str, request: Request) -> dict:
    await signed_json(request)
    return start_container(container_name)


@app.post("/containers/{container_name}/stop")
async def stop(container_name: str, request: Request) -> dict:
    await signed_json(request)
    return stop_container(container_name)


@app.post("/containers/{container_name}/restart")
async def restart(container_name: str, request: Request) -> dict:
    await signed_json(request)
    return restart_container(container_name)


@app.post("/containers/{container_name}/status")
async def status(container_name: str, request: Request) -> dict:
    await signed_json(request)
    return status_container(container_name)


@app.delete("/containers/{container_name}")
async def delete(container_name: str, request: Request) -> dict:
    await signed_json(request)
    return delete_container(container_name)


@app.get("/containers/{container_name}/logs", response_class=PlainTextResponse)
async def logs(
    container_name: str,
    request: Request,
    tail: int = Query(200, ge=1, le=1000),
) -> str:
    # GET requests have no body in the controller client; it signs an empty JSON object.
    from app.security import verify_signed_payload

    verify_signed_payload(
        b"{}",
        request.headers.get("authorization", ""),
        request.headers.get("x-controller-timestamp", ""),
        request.headers.get("x-controller-signature", ""),
    )
    return container_logs(container_name, tail)
