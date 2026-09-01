from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class AppPaths:
    """Centralized filesystem paths for SP Telegram runtime data."""

    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "AppPaths":
        return cls(Path(root).resolve())

    @property
    def data(self) -> Path: return self.root / "data"
    @property
    def sessions(self) -> Path: return self.data / "sessions"
    @property
    def media(self) -> Path: return self.data / "media"
    @property
    def cache(self) -> Path: return self.data / "cache"
    @property
    def logs(self) -> Path: return self.root / "logs"
    @property
    def backups(self) -> Path: return self.root / "backups"
    @property
    def exports(self) -> Path: return self.root / "exports"
    @property
    def temp(self) -> Path: return self.data / "temp"
    @property
    def database(self) -> Path: return self.data / "tg_control.db"

    def ensure(self) -> None:
        for path in (self.data, self.sessions, self.media, self.cache, self.logs, self.backups, self.exports, self.temp):
            path.mkdir(parents=True, exist_ok=True)

    def validate(self, *, minimum_free_bytes: int = 100 * 1024 * 1024) -> dict[str, object]:
        self.ensure()
        writable = all(self._is_writable(path) for path in (self.data, self.logs, self.backups, self.exports))
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
