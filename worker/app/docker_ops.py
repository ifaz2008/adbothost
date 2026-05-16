from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import docker
import psutil
from fastapi import HTTPException

from app.config import settings


client = docker.from_env()


def _safe_extract(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise HTTPException(status_code=400, detail="Unsafe archive path.")
            if member.is_dir():
                continue
            destination = target_dir / Path(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def _write_runtime_dockerfile(project_dir: Path, runtime: str) -> None:
    if runtime == "python":
        dockerfile = """FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system bot && adduser --system --ingroup bot --home /app bot
COPY . /app
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi \
    && mkdir -p /data \
    && chown -R bot:bot /app /data
USER bot
"""
    elif runtime == "node":
        dockerfile = """FROM node:20-slim
ENV NODE_ENV=production
WORKDIR /app
RUN groupadd --system bot && useradd --system --gid bot --home-dir /app bot
COPY . /app
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; elif [ -f package.json ]; then npm install --omit=dev; fi \
    && mkdir -p /data \
    && chown -R bot:bot /app /data
USER bot
"""
    else:
        raise HTTPException(status_code=400, detail="Unsupported runtime.")
    (project_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _container_name(bot_id: int, deployment_id: int) -> str:
    return f"adbothost-bot-{bot_id}-{deployment_id}"


def deploy_container(archive_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    expected_sha = metadata.get("sha256")
    if expected_sha and _hash_file(archive_path) != expected_sha:
        raise HTTPException(status_code=400, detail="Archive checksum mismatch.")

    bot_id = int(metadata["bot_id"])
    deployment_id = int(metadata["deployment_id"])
    runtime = metadata["runtime"]
    resources = metadata.get("resources", {})
    start_command = metadata.get("start_command", [])
    env = metadata.get("env", {})

    deployment_dir = settings.worker_data_dir / "deployments" / str(deployment_id)
    project_dir = deployment_dir / "project"
    if deployment_dir.exists():
        shutil.rmtree(deployment_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    _safe_extract(archive_path, project_dir)
    _write_runtime_dockerfile(project_dir, runtime)
    (deployment_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    image_tag = f"adbothost/bot-{bot_id}:v{metadata['version_id']}-{deployment_id}"
    image, _logs = client.images.build(path=str(project_dir), tag=image_tag, rm=True, forcerm=True)

    container_name = _container_name(bot_id, deployment_id)
    try:
        old = client.containers.get(container_name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    volume_name = f"adbothost-data-{deployment_id}"
    try:
        client.volumes.create(name=volume_name, labels={"app": "adbothost", "deployment_id": str(deployment_id)})
    except docker.errors.APIError:
        pass

    cpu = float(resources.get("cpu", 0.1))
    memory_mb = int(resources.get("memory_mb", 128))
    storage_mb = int(resources.get("storage_mb", 250))
    pids_limit = int(resources.get("pids_limit", 128))

    # No ports, no host mounts, no privileged mode, no shell API, and no Docker socket
    # are exposed to user containers. Outbound networking is left enabled for Telegram.
    run_options = {
        "image": image.id,
        "command": start_command,
        "name": container_name,
        "detach": True,
        "environment": env,
        "mem_limit": f"{memory_mb}m",
        "nano_cpus": int(cpu * 1_000_000_000),
        "pids_limit": pids_limit,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "privileged": False,
        "volumes": {volume_name: {"bind": "/data", "mode": "rw"}},
        "labels": {
            "app": "adbothost",
            "bot_id": str(bot_id),
            "deployment_id": str(deployment_id),
            "storage_mb": str(storage_mb),
        },
    }
    if settings.worker_enforce_storage_opt:
        # Docker storage_opt size only works on supported daemon/filesystem setups.
        # Leave disabled on generic RDP installs unless the node is provisioned for it.
        run_options["storage_opt"] = {"size": f"{storage_mb}m"}

    container = client.containers.run(**run_options)

    return {
        "status": "running",
        "container_id": container.id,
        "container_name": container.name,
        "image_tag": image_tag,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def _get_container(name: str):
    try:
        return client.containers.get(name)
    except docker.errors.NotFound as exc:
        raise HTTPException(status_code=404, detail="Container not found.") from exc


def stop_container(name: str) -> dict[str, str]:
    container = _get_container(name)
    container.stop(timeout=10)
    return {"status": "stopped"}


def start_container(name: str) -> dict[str, str]:
    container = _get_container(name)
    container.start()
    return {"status": "running"}


def restart_container(name: str) -> dict[str, str]:
    container = _get_container(name)
    container.restart(timeout=10)
    return {"status": "running"}


def status_container(name: str) -> dict[str, str | int | None]:
    container = _get_container(name)
    container.reload()
    state = container.attrs.get("State", {})
    return {
        "status": container.status,
        "exit_code": state.get("ExitCode"),
        "error": state.get("Error") or None,
    }


def delete_container(name: str) -> dict[str, str]:
    container = _get_container(name)
    deployment_id = container.labels.get("deployment_id")
    container.remove(force=True)
    if deployment_id:
        deployment_dir = settings.worker_data_dir / "deployments" / deployment_id
        shutil.rmtree(deployment_dir, ignore_errors=True)
    return {"status": "deleted"}


def container_logs(name: str, tail: int) -> str:
    container = _get_container(name)
    logs = container.logs(tail=tail, timestamps=True)
    return logs.decode("utf-8", errors="replace")


def node_stats() -> dict[str, Any]:
    disk = psutil.disk_usage(str(settings.worker_data_dir))
    memory = psutil.virtual_memory()
    containers = client.containers.list(filters={"label": "app=adbothost"})
    return {
        "status": "healthy",
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory_total_mb": int(memory.total / 1024 / 1024),
        "memory_used_mb": int((memory.total - memory.available) / 1024 / 1024),
        "disk_total_mb": int(disk.total / 1024 / 1024),
        "disk_used_mb": int(disk.used / 1024 / 1024),
        "running_containers": len(containers),
        "max_containers": settings.worker_max_containers,
    }
