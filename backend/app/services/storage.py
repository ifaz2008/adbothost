import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(filename: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", Path(filename).name).strip(".-")
    return cleaned or "upload.zip"


async def store_upload(
    file: UploadFile,
    user_id: int,
    bot_id: int,
    version_number: int,
    max_size_mb: int,
) -> tuple[Path, str, int]:
    filename = safe_filename(file.filename or "bot.zip")
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .zip uploads are allowed.")

    target_dir = settings.upload_dir / f"user_{user_id}" / f"bot_{bot_id}" / f"v{version_number}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    max_bytes = max_size_mb * 1024 * 1024
    total = 0
    digest = hashlib.sha256()
    with target_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds plan limit of {max_size_mb} MB.",
                )
            digest.update(chunk)
            output.write(chunk)

    if total == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Upload is empty.")

    return target_path, digest.hexdigest(), total
