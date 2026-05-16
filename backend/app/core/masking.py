import re
from typing import Iterable


TELEGRAM_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(TELEGRAM_BOT_TOKEN|BOT_TOKEN|TOKEN|API_KEY|SECRET)\s*=\s*([^\s]+)"
)


def mask_secrets(text: str, known_values: Iterable[str] | None = None) -> str:
    masked = TELEGRAM_TOKEN_RE.sub("[masked-telegram-token]", text)
    masked = SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=[masked]", masked)
    for value in known_values or []:
        if value and len(value) >= 6:
            masked = masked.replace(value, "[masked-secret]")
    return masked
