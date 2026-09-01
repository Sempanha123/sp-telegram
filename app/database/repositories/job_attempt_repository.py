from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import JobAttempt
from app.utils.formatters import utc_now_iso


class JobAttemptRepository(BaseRepository):
    table_name = "job_attempts"
    columns = (
        "id", "job_id", "attempt_number", "started_at", "finished_at", "status",
        "error_code", "error_message", "retry_classification", "created_at",
    )

    def start(self, job_id: int) -> JobAttempt:
        row = self.db.fetch_one("SELECT COALESCE(MAX(attempt_number),0)+1 AS n FROM job_attempts WHERE job_id=?", (job_id,))
        number = int(row["n"] if row else 1)
        now = utc_now_iso()
        attempt_id = self.insert({"job_id": job_id, "attempt_number": number, "started_at": now, "status": "RUNNING", "created_at": now})
        return JobAttempt.from_row(self.find_by_id(attempt_id))

    def finish(self, attempt_id: int, status: str, *, error_code: str | None = None, error_message: str | None = None, retry_classification: str = "UNKNOWN") -> bool:
        return self.update_fields(attempt_id, {
            "status": status, "finished_at": utc_now_iso(), "error_code": error_code,
            "error_message": error_message, "retry_classification": retry_classification,
        })

    def for_job(self, job_id: int) -> list[JobAttempt]:
        rows = self.db.fetch_all(
            f"SELECT {', '.join(self.columns)} FROM job_attempts WHERE job_id=? ORDER BY attempt_number DESC", (job_id,)
        )
        return [JobAttempt.from_row(row) for row in rows]

    def delete_for_job(self, job_id: int) -> bool:
        return self.db.execute("DELETE FROM job_attempts WHERE job_id=?", (job_id,)).rowcount >= 0
