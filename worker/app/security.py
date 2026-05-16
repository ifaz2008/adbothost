import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request

from app.config import settings


def _verify_bearer(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.node_agent_token}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid worker token.")


def sign_payload(payload: bytes, timestamp: str) -> str:
    message = timestamp.encode("utf-8") + b"." + payload
    return hmac.new(settings.node_agent_token.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signed_payload(
    payload: bytes,
    authorization: str,
    timestamp: str,
    signature: str,
) -> None:
    _verify_bearer(authorization)
    try:
        signed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid signature timestamp.") from exc
    if signed_at.tzinfo is None:
        signed_at = signed_at.replace(tzinfo=timezone.utc)
    drift = abs((datetime.now(timezone.utc) - signed_at.astimezone(timezone.utc)).total_seconds())
    if drift > 300:
        raise HTTPException(status_code=401, detail="Signed request expired.")
    expected = sign_payload(payload, timestamp)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid request signature.")


async def signed_json(request: Request) -> dict:
    body = await request.body()
    verify_signed_payload(
        body,
        request.headers.get("authorization", ""),
        request.headers.get("x-controller-timestamp", ""),
        request.headers.get("x-controller-signature", ""),
    )
    if not body:
        return {}
    return await request.json()


def verify_metadata_signature(metadata: str, authorization: str, timestamp: str, signature: str) -> None:
    verify_signed_payload(metadata.encode("utf-8"), authorization, timestamp, signature)
