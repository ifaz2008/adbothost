from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.core.config import settings


SUSPICIOUS_KEYWORDS = {
    "mining",
    "xmrig",
    "proxy",
    "socks5",
    "spam",
    "mass_dm",
    "phishing",
    "steal_token",
    "keylogger",
    "selenium",
    "playwright",
    "puppeteer",
    "chromedriver",
}

DANGEROUS_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".scr",
    ".com",
    ".apk",
    ".jar",
    ".class",
    ".pyc",
    ".pyd",
}

DISALLOWED_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


@dataclass
class ScanIssue:
    severity: str
    file: str
    reason: str


@dataclass
class ScanResult:
    status: str
    severity: str
    runtime: str
    summary: str
    issues: list[ScanIssue] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "severity": self.severity,
                "runtime": self.runtime,
                "summary": self.summary,
                "issues": [issue.__dict__ for issue in self.issues],
            },
            indent=2,
        )


def _severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity, 0)


def _join_severity(issues: list[ScanIssue]) -> str:
    if not issues:
        return "low"
    return max((issue.severity for issue in issues), key=_severity_rank)


def _is_textish(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _safe_archive_path(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def scan_zip(zip_path: str, max_upload_size_mb: int) -> ScanResult:
    issues: list[ScanIssue] = []
    has_python = False
    has_node = False
    total_size = 0
    max_file_bytes = settings.scan_max_file_mb * 1024 * 1024

    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        return ScanResult("blocked", "high", "unknown", "Upload is not a valid ZIP archive.")

    with archive:
        members = archive.infolist()
        if not members:
            return ScanResult("blocked", "high", "unknown", "ZIP archive is empty.")

        for member in members:
            if member.is_dir():
                continue
            name = member.filename.replace("\\", "/")
            total_size += member.file_size
            lower_name = name.lower()
            suffix = PurePosixPath(lower_name).suffix

            if not _safe_archive_path(name):
                issues.append(ScanIssue("high", name, "Archive path traversal is not allowed."))
                continue

            if PurePosixPath(lower_name).name in DISALLOWED_FILENAMES:
                issues.append(ScanIssue("high", name, "Custom Docker or compose files are not allowed in MVP."))

            if member.file_size > max_file_bytes:
                issues.append(ScanIssue("high", name, f"File exceeds per-file limit of {settings.scan_max_file_mb} MB."))

            if suffix in DANGEROUS_EXTENSIONS:
                issues.append(ScanIssue("high", name, f"Dangerous executable or binary extension {suffix}."))

            if "requirements.txt" in lower_name or suffix == ".py":
                has_python = True
            if lower_name.endswith("package.json") or suffix in {".js", ".mjs", ".cjs", ".ts"}:
                has_node = True

            if any(keyword in lower_name for keyword in SUSPICIOUS_KEYWORDS):
                issues.append(ScanIssue("high", name, "Suspicious keyword found in file path."))

            with archive.open(member, "r") as member_file:
                sample = member_file.read(256 * 1024)
            if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"} and not _is_textish(sample):
                issues.append(ScanIssue("high", name, "Binary content is not allowed in bot uploads."))
                continue

            text = sample.decode("utf-8", errors="ignore").lower()
            for keyword in SUSPICIOUS_KEYWORDS:
                if keyword in text:
                    issues.append(ScanIssue("high", name, f"Suspicious keyword '{keyword}' found."))
                    break

        if total_size > max_upload_size_mb * 1024 * 1024:
            issues.append(ScanIssue("high", str(zip_path), "Uncompressed upload exceeds plan limit."))

    if has_python and has_node:
        issues.append(ScanIssue("high", str(zip_path), "Mixed Python and Node runtimes are not supported in MVP."))

    runtime = "python" if has_python else "node" if has_node else "unknown"
    if runtime == "unknown":
        issues.append(ScanIssue("high", str(zip_path), "Could not detect Python or Node.js Telegram bot project."))

    severity = _join_severity(issues)
    status = "blocked" if severity == "high" else "review" if severity == "medium" else "clean"
    if status == "clean":
        summary = f"Clean {runtime} project. {len(issues)} issue(s)."
    elif status == "review":
        summary = f"Upload requires admin review. {len(issues)} issue(s)."
    else:
        summary = f"Upload blocked. {len(issues)} high-severity issue(s)."

    # TODO: add optional OpenRouter/OpenClaw AI code scanning after this deterministic pass.
    return ScanResult(status, severity, runtime, summary, issues)
