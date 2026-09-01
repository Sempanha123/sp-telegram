from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionSecurityFinding:
    severity: str
    code: str
    message: str
    account_id: int | None = None


class SessionSecurity:
    ALLOWED_SUFFIXES = {".session", ".journal", ".gitkeep"}

    def __init__(self, session_dir: str | Path) -> None:
        self.session_dir = Path(session_dir).resolve()

    def audit(self, accounts) -> list[SessionSecurityFinding]:
        findings: list[SessionSecurityFinding] = []
        seen: dict[Path, int] = {}
        self.session_dir.mkdir(parents=True, exist_ok=True)
        for account in accounts:
            raw = getattr(account, "session_path", None)
            if not raw:
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = (self.session_dir.parent.parent / path).resolve()
            else:
                path = path.resolve()
            try:
                path.relative_to(self.session_dir)
            except ValueError:
                findings.append(SessionSecurityFinding("WARNING", "SESSION_OUTSIDE_APPROVED_DIR", "Session path is outside the approved session directory.", getattr(account, "id", None)))
            if path in seen:
                findings.append(SessionSecurityFinding("CRITICAL", "DUPLICATE_SESSION_PATH", "Two account records reference the same Telegram session path.", getattr(account, "id", None)))
            else:
                seen[path] = int(getattr(account, "id", 0) or 0)
            if not path.exists():
                findings.append(SessionSecurityFinding("WARNING", "SESSION_MISSING", "Configured Telegram session file is missing.", getattr(account, "id", None)))
        for item in self.session_dir.iterdir():
            if item.is_file() and item.name != ".gitkeep" and item.suffix.lower() not in {".session", ".journal"} and not item.name.endswith(".session-journal"):
                findings.append(SessionSecurityFinding("WARNING", "UNEXPECTED_SESSION_FILE", "Unexpected file type exists in the Telegram session directory."))
        return findings
