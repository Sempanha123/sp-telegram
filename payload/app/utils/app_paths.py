from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys


RUNTIME_DIR_ENV = "SP_TELEGRAM_DATA_DIR"


def is_frozen_runtime() -> bool:
    """Return whether SP Telegram is running from a frozen executable."""
    return bool(getattr(sys, "frozen", False))


def default_runtime_root(source_root: str | Path | None = None) -> Path:
    """Return the writable root used for databases, sessions, media and logs.

    Development keeps the historical repository-local ``data`` layout so the
    current workflow and tests remain unchanged.  Frozen builds use the user's
    OS application-data directory; a PyInstaller one-file executable must never
    persist operator data inside its temporary extraction directory.

    ``SP_TELEGRAM_DATA_DIR`` is an explicit operator/developer override and is
    useful for portable QA, isolated test runs, or managed deployments.
    """
    explicit = str(os.getenv(RUNTIME_DIR_ENV, "") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    if not is_frozen_runtime():
        root = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[2]
        return root.expanduser().resolve()

    if sys.platform == "win32":
        base = str(os.getenv("LOCALAPPDATA", "") or os.getenv("APPDATA", "") or "").strip()
        if base:
            return (Path(base) / "SP Cambo" / "SP Telegram").resolve()
        return (Path.home() / "AppData" / "Local" / "SP Cambo" / "SP Telegram").resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "SP Telegram").resolve()

    xdg = str(os.getenv("XDG_DATA_HOME", "") or "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / "sp-telegram").resolve()


@dataclass(frozen=True)
class AppPaths:
    """Centralized filesystem paths for SP Telegram runtime data."""

    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "AppPaths":
        return cls(Path(root).expanduser().resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def sessions(self) -> Path:
        return self.data / "sessions"

    @property
    def media(self) -> Path:
        return self.data / "media"

    @property
    def cache(self) -> Path:
        return self.data / "cache"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def temp(self) -> Path:
        return self.data / "temp"

    @property
    def database(self) -> Path:
        return self.data / "tg_control.db"

    def ensure(self) -> None:
        for path in (
            self.root,
            self.data,
            self.sessions,
            self.media,
            self.media / "campaigns",
            self.cache,
            self.cache / "avatars",
            self.cache / "groups",
            self.logs,
            self.backups,
            self.exports,
            self.temp,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate(self, *, minimum_free_bytes: int = 100 * 1024 * 1024) -> dict[str, object]:
        self.ensure()
        writable = all(
            self._is_writable(path)
            for path in (self.data, self.sessions, self.logs, self.backups, self.exports)
        )
        usage = shutil.disk_usage(self.data)
        return {
            "writable": writable,
            "free_bytes": int(usage.free),
            "total_bytes": int(usage.total),
            "low_disk": int(usage.free) < int(minimum_free_bytes),
        }

    @staticmethod
    def _is_writable(path: Path) -> bool:
        try:
            probe = path / ".tg_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False
