from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso


class BackupRepository(BaseRepository):
    table_name = "backup_records"
    columns = ("id", "backup_path", "manifest_path", "schema_version", "app_version", "status", "checksum", "created_at", "verified_at", "restored_at")

    def record(self, backup_path: str, manifest_path: str | None, schema_version: int, app_version: str, checksum: str | None = None) -> int:
        return self.insert({"backup_path": backup_path, "manifest_path": manifest_path, "schema_version": schema_version,
                            "app_version": app_version, "status": "CREATED", "checksum": checksum, "created_at": utc_now_iso()})

    def mark_verified(self, record_id: int, ok: bool) -> bool:
        return self.update_fields(record_id, {"status": "VERIFIED" if ok else "INVALID", "verified_at": utc_now_iso()})

    def mark_restored(self, record_id: int) -> bool:
        return self.update_fields(record_id, {"status": "RESTORED", "restored_at": utc_now_iso()})

    def latest(self):
        row = self.db.fetch_one(f"SELECT {', '.join(self.columns)} FROM backup_records ORDER BY id DESC LIMIT 1")
        return dict(row) if row else None
