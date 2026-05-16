import shlex

from fastapi import HTTPException, status


DISALLOWED_SHELL_CHARS = set(";|&`$<>\n\r")


def validate_start_command(command: str) -> list[str]:
    if any(char in command for char in DISALLOWED_SHELL_CHARS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start command contains shell metacharacters that are not allowed.",
        )
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid start command: {exc}") from exc
    if not parts:
        raise HTTPException(status_code=400, detail="Start command cannot be empty.")
    if len(parts) > 8:
        raise HTTPException(status_code=400, detail="Start command is too long for the MVP runtime.")
    return parts


def validate_runtime_command(command: str, runtime: str) -> list[str]:
    parts = validate_start_command(command)
    first = parts[0].lower()
    if runtime == "python":
        if first not in {"python", "python3"}:
            raise HTTPException(status_code=400, detail="Python bots must start with python or python3.")
    elif runtime == "node":
        if first == "npm" and parts[1:] != ["start"]:
            raise HTTPException(status_code=400, detail="Node bots may use npm start only.")
        if first not in {"node", "npm"}:
            raise HTTPException(status_code=400, detail="Node bots must start with node or npm start.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported runtime.")
    return parts
