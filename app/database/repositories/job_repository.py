from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import Job
from app.utils.formatters import utc_now_iso


COLS = (
    "id", "job_type", "status", "account_id", "group_id", "campaign_id", "progress",
    "total_items", "success_count", "skipped_count", "failed_count", "started_at", "finished_at",
    "last_error", "metadata_json", "created_at", "updated_at", "retry_classification",
    "interrupted_at", "resource_type", "resource_id",
)


class JobRepository(BaseRepository):
    table_name = "jobs"
    columns = COLS

    def create_job(self, job_type: str, **values):
        now = utc_now_iso()
        data = {"job_type": job_type, "status": values.pop("status", "QUEUED"), "created_at": now, "updated_at": now, **values}
        job_id = self.insert(data)
        return Job.from_row(self.find_by_id(job_id))

    def update_status(self, job_id: int, status: str, *, error: str | None = None, retry_classification: str | None = None):
        payload = {"status": status, "updated_at": utc_now_iso()}
        if error is not None: payload["last_error"] = error
        if retry_classification is not None: payload["retry_classification"] = retry_classification
        if status == "RUNNING": payload["started_at"] = self.get_by_id(job_id).started_at or utc_now_iso()
        if status in {"COMPLETED", "FAILED", "STOPPED", "CANCELLED", "PARTIAL_SUCCESS"}: payload["finished_at"] = utc_now_iso()
        return self.update_fields(job_id, payload)

    def update_progress(self, job_id: int, progress: int):
        return self.update_fields(job_id, {"progress": max(0, min(100, progress)), "updated_at": utc_now_iso()})

    def _inc(self, job_id: int, column: str):
        return self.db.execute(f"UPDATE jobs SET {column}={column}+1,updated_at=? WHERE id=?", (utc_now_iso(), job_id)).rowcount > 0

    def increment_success(self, job_id: int): return self._inc(job_id, "success_count")
    def increment_skip(self, job_id: int): return self._inc(job_id, "skipped_count")
    def increment_failure(self, job_id: int): return self._inc(job_id, "failed_count")
    def get_by_id(self, job_id: int): return Job.from_row(self.find_by_id(job_id))

    def get_running_jobs(self):
        rows = self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM jobs WHERE status='RUNNING' ORDER BY id DESC")
        return [Job.from_row(r) for r in rows]

    def get_page(self, page: int, page_size: int, *, status: str | None = None, search: str = ""):
        clauses: list[str] = []; params: list[object] = []
        if status and status != "ALL": clauses.append("status=?"); params.append(status)
        if search.strip():
            clauses.append("(CAST(id AS TEXT) LIKE ? OR job_type LIKE ? OR COALESCE(last_error,'') LIKE ?)")
            like = f"%{search.strip()}%"; params.extend([like, like, like])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        row = self.db.fetch_one(f"SELECT COUNT(*) AS n FROM jobs{where}", params); total = int(row["n"] if row else 0)
        offset = (max(1, page) - 1) * page_size
        rows = self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM jobs{where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        )
        return [Job.from_row(r) for r in rows], total

    def count_running(self): return self.count("status='RUNNING'")
    def count_by_status(self, status: str): return self.count("status=?", (status,))


    def queue_summary(self) -> dict[str, dict[str, object]]:
        """Small aggregate-only queue snapshot for the Operations Center."""
        categories = {
            "Campaign Queue": ("CAMPAIGN_SEND",),
            "Sync Queue": ("ACCOUNT_HEALTH_CHECK", "GROUP_SYNC", "GROUP_DISCOVERY", "MEMBER_SYNC", "TARGET_MEMBER_SYNC", "TARGET_MEMBER_INVITE"),
            "Scheduler Queue": ("CAMPAIGN_SCHEDULE", "SCHEDULE_SYNC"),
        }
        result: dict[str, dict[str, object]] = {}
        for label, job_types in categories.items():
            placeholders = ",".join("?" for _ in job_types)
            row = self.db.fetch_one(
                f"SELECT "
                f"SUM(CASE WHEN status='QUEUED' THEN 1 ELSE 0 END) AS pending, "
                f"SUM(CASE WHEN status='RUNNING' THEN 1 ELSE 0 END) AS running, "
                f"MIN(CASE WHEN status='QUEUED' THEN created_at END) AS oldest "
                f"FROM jobs WHERE job_type IN ({placeholders})",
                job_types,
            )
            result[label] = {
                "pending": int(row["pending"] or 0) if row else 0,
                "running": int(row["running"] or 0) if row else 0,
                "oldest": row["oldest"] if row and row["oldest"] else None,
            }
        return result

    def mark_interrupted_jobs(self) -> dict[str, int]:
        """Recover persisted RUNNING jobs conservatively after an unclean exit."""
        rows = self.db.fetch_all("SELECT id,job_type FROM jobs WHERE status='RUNNING'")
        result = {"interrupted": 0, "reconcile_required": 0}
        ambiguous = {"CAMPAIGN_SEND", "CAMPAIGN_SCHEDULE", "SCHEDULE_SYNC", "TARGET_MEMBER_INVITE"}
        now = utc_now_iso()
        for row in rows:
            status = "RECONCILE_REQUIRED" if str(row["job_type"]) in ambiguous else "INTERRUPTED"
            self.update_fields(int(row["id"]), {"status": status, "interrupted_at": now, "updated_at": now})
            result["reconcile_required" if status == "RECONCILE_REQUIRED" else "interrupted"] += 1
        return result

    def retryable_failed(self, job_id: int) -> bool:
        job = self.get_by_id(job_id)
        return bool(job and job.status in {"FAILED", "INTERRUPTED"} and job.retry_classification in {"SAFE_RETRY", "WAIT_AND_RETRY"})
