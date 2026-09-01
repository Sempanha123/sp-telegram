from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

from app.constants import APP_NAME, APP_VERSION
from app.utils.formatters import utc_now_iso


class BackupError(RuntimeError):
    pass


class BackupService:
    """Manifested SQLite-safe backups. Telegram session credentials are excluded by default."""

    def __init__(self, database, settings_repository, paths, backup_repository=None, audit_repository=None) -> None:
        self.database = database
        self.settings = settings_repository
        self.paths = paths
        self.repository = backup_repository
        self.audit = audit_repository

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def create_backup(self, destination_root: str | Path | None = None, *, prefix: str | None = None) -> dict:
        if self.database.has_active_transactions():
            raise BackupError("Backup cannot start while an application database transaction is active.")
        root = Path(destination_root or self.paths.backups).resolve(); root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        folder = root / f"{prefix + '_' if prefix else ''}{stamp}"
        suffix = 1
        while folder.exists():
            folder = root / f"{prefix + '_' if prefix else ''}{stamp}_{suffix}"; suffix += 1
        folder.mkdir(parents=True)
        db_file = folder / "tg_control.db"
        self.database.backup_to(db_file)
        settings_file = folder / "settings.json"
        settings_file.write_text(json.dumps(self.settings.get_all(), indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        checksums = {"tg_control.db": self._sha256(db_file), "settings.json": self._sha256(settings_file)}
        manifest = {
            "app": APP_NAME, "app_version": APP_VERSION,
            "schema_version": self.database.get_schema_version(), "created_at": utc_now_iso(),
            "included_components": ["database", "application_settings"],
            "excluded_components": ["telegram_sessions", "api_credentials", "otp", "2fa_password"],
            "checksums": checksums,
        }
        manifest_file = folder / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        record_id = None
        if self.repository:
            record_id = self.repository.record(str(db_file), str(manifest_file), manifest["schema_version"], APP_VERSION, checksums["tg_control.db"])
        if self.audit:
            self.audit.add("BACKUP_CREATED", resource_type="BACKUP", resource_id=record_id or folder.name,
                           description="Application database/settings backup created. Telegram sessions were excluded.")
        return {"folder": folder, "database": db_file, "manifest": manifest_file, "record_id": record_id, "manifest_data": manifest}

    def verify_backup(self, backup_folder: str | Path) -> dict:
        folder = Path(backup_folder).resolve()
        manifest_file = folder / "manifest.json"; db_file = folder / "tg_control.db"; settings_file = folder / "settings.json"
        errors: list[str] = []
        if not manifest_file.is_file(): errors.append("Backup manifest is missing.")
        if not db_file.is_file(): errors.append("Backup database is missing.")
        manifest = {}
        if not errors:
            try: manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception: errors.append("Backup manifest is not valid JSON.")
        if db_file.is_file() and not self.database.validate_database_file(db_file):
            errors.append("Backup SQLite database failed integrity validation.")
        checksums = manifest.get("checksums", {}) if isinstance(manifest, dict) else {}
        for name, expected in checksums.items():
            path = folder / name
            if not path.is_file(): errors.append(f"Backup component {name} is missing.")
            elif self._sha256(path) != expected: errors.append(f"Checksum mismatch for {name}.")
        schema = int(manifest.get("schema_version", 0) or 0) if isinstance(manifest, dict) else 0
        if schema > self.database.get_schema_version():
            errors.append("Backup schema is newer than this application build.")
        ok = not errors
        return {"ok": ok, "errors": errors, "manifest": manifest, "database": db_file, "folder": folder}

    def restore_backup(self, backup_folder: str | Path) -> dict:
        if self.database.has_active_transactions():
            raise BackupError("Restore cannot start while an application database transaction is active.")
        check = self.verify_backup(backup_folder)
        if not check["ok"]:
            raise BackupError("Backup validation failed: " + "; ".join(check["errors"]))
        safety = self.create_backup(self.paths.backups, prefix="pre_restore")
        self.database.restore_from(check["database"], safety_backup_dir=None)
        # Migration runner brings older compatible backups forward safely.
        self.database.initialize()
        if self.audit:
            self.audit.add("BACKUP_RESTORED", resource_type="BACKUP", resource_id=Path(backup_folder).name,
                           description="Backup restored after validation and creation of a safety backup.")
        return {"restored": True, "safety_backup": safety["folder"], "schema_version": self.database.get_schema_version()}

    def enforce_retention(self, keep_last: int = 10) -> int:
        keep_last = max(1, int(keep_last)); folders = []
        if self.paths.backups.exists():
            for item in self.paths.backups.iterdir():
                if item.is_dir() and (item / "manifest.json").exists(): folders.append(item)
        folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        removed = 0
        for folder in folders[keep_last:]:
            try:
                shutil.rmtree(folder)
                removed += 1
            except OSError:
                continue
        return removed
