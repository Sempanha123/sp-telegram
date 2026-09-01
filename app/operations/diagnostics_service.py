from __future__ import annotations

import json
import platform
from pathlib import Path
import sys
import zipfile

from app.constants import APP_NAME, APP_VERSION
from app.security.sensitive_data_filter import SensitiveDataFilter
from app.utils.formatters import utc_now_iso


class DiagnosticsService:
    def __init__(self, context_view, maintenance_service, worker_registry, performance_monitor, paths,
                 sensitive_filter: SensitiveDataFilter | None = None) -> None:
        self.context = context_view
        self.maintenance = maintenance_service
        self.workers = worker_registry
        self.performance = performance_monitor
        self.paths = paths
        self.filter = sensitive_filter or SensitiveDataFilter(mask_phone=True, mask_ip=True, mask_session_path=True)

    def collect(self) -> dict:
        try:
            import PySide6
            pyside = getattr(PySide6, "__version__", "unknown")
        except Exception:
            pyside = "unavailable"
        try:
            import telethon
            telethon_version = getattr(telethon, "__version__", "unknown")
        except Exception:
            telethon_version = "unavailable"
        db = self.maintenance.database_stats()
        accounts = self.context.account_repository.count_all()
        groups = self.context.group_repository.count_all()
        members = self.context.member_repository.count_all()
        active_jobs = self.context.job_repository.count_running()
        report = {
            "application": {"name": APP_NAME, "version": APP_VERSION, "generated_at": utc_now_iso()},
            "runtime": {"python": sys.version.split()[0], "platform": platform.platform(), "pyside6": pyside, "telethon": telethon_version},
            "database": db,
            "workers": [vars(w).copy() for w in self.workers.all()],
            "performance": self.performance.sample(),
            "counts": {"accounts": accounts, "groups": groups, "members": members, "active_jobs": active_jobs},
            "directories": {"data": str(self.paths.data), "logs": str(self.paths.logs), "backups": str(self.paths.backups), "exports": str(self.paths.exports)},
        }
        return self.filter.redact(report)

    def to_text(self, report: dict | None = None) -> str:
        return json.dumps(report or self.collect(), indent=2, ensure_ascii=False, sort_keys=True)

    def export(self, path: str | Path) -> Path:
        destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_text(), encoding="utf-8")
        return destination

    def create_support_bundle(self, path: str | Path, *, recent_log_lines: int = 500) -> Path:
        destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
        diagnostics = self.to_text()
        log_text = ""
        log_file = self.paths.logs / "app.log"
        if log_file.exists():
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-recent_log_lines:]
                log_text = "\n".join(str(self.filter.redact(line)) for line in lines)
            except OSError:
                pass
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostics.json", diagnostics)
            archive.writestr("recent_sanitized.log", log_text)
            archive.writestr("README.txt", f"Sanitized {APP_NAME} support bundle. Telegram sessions and API credentials are intentionally excluded.\n")
        return destination
