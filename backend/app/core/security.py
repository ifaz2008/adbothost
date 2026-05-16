import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str, extra: Optional[Dict[str, Any]] = None) -> str:
    expires_at = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: Dict[str, Any] = {"sub": subject, "exp": expires_at}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def sign_payload(payload: bytes, token: str, timestamp: str) -> str:
    message = timestamp.encode("utf-8") + b"." + payload
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, token: str, timestamp: str, signature: str) -> bool:
    expected = sign_payload(payload, token, timestamp)
    return hmac.compare_digest(expected, signature)
