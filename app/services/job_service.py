from __future__ import annotations

from app.operations.retry_policy import RetryPolicy


class JobService:
    def __init__(self, repository, attempt_repository=None) -> None:
        self.repository = repository
        self.attempts = attempt_repository

    def get_page(self, page=1, page_size=100, *, status=None, search=""):
        return self.repository.get_page(page, page_size, status=status, search=search)

    def running_count(self): return self.repository.count_running()

    def get_details(self, job_id: int) -> dict:
        job = self.repository.get_by_id(job_id)
        if not job: return {}
        attempts = self.attempts.for_job(job_id) if self.attempts else []
        items = [dict(r) for r in self.repository.db.fetch_all(
            "SELECT id,item_type,item_id,status,error_code,error_message,started_at,finished_at,created_at,updated_at FROM job_items WHERE job_id=? ORDER BY id", (job_id,)
        )]
        return {"job": job, "attempts": attempts, "items": items}

    def pause(self, job_id: int) -> bool:
        job = self.repository.get_by_id(job_id)
        if not job or job.status not in {"RUNNING", "WAITING"}: return False
        return bool(self.repository.update_status(job_id, "PAUSED"))

    def resume(self, job_id: int) -> bool:
        job = self.repository.get_by_id(job_id)
        if not job or job.status not in {"PAUSED", "INTERRUPTED"}: return False
        # Generic resume only returns the job to the queue. Domain-specific workers still own execution.
        return bool(self.repository.update_status(job_id, "QUEUED"))

    def cancel(self, job_id: int) -> bool:
        job = self.repository.get_by_id(job_id)
        if not job or job.status in {"COMPLETED", "CANCELLED", "STOPPED"}: return False
        return bool(self.repository.update_status(job_id, "CANCELLED"))

    def retry(self, job_id: int) -> bool:
        job = self.repository.get_by_id(job_id)
        if not job or job.status == "RECONCILE_REQUIRED": return False
        classification = str(RetryPolicy.classify(job.retry_classification if job.retry_classification != "UNKNOWN" else None, job.last_error))
        # Preserve an explicitly persisted safe classification.
        if job.retry_classification in {"SAFE_RETRY", "WAIT_AND_RETRY"}: classification = job.retry_classification
        if classification not in {"SAFE_RETRY", "WAIT_AND_RETRY"}: return False
        if self.attempts: self.attempts.start(job_id)
        return bool(self.repository.update_fields(job_id, {
            "status": "QUEUED", "progress": 0, "finished_at": None, "last_error": None,
            "retry_classification": classification,
        }))

    def delete_history(self, job_id: int) -> bool:
        """Safely delete finished job history. Running/queued jobs are never deleted."""
        job = self.repository.get_by_id(job_id)
        if not job or job.status in {"RUNNING", "QUEUED", "WAITING", "PAUSED"}: return False
        if self.attempts: self.attempts.delete_for_job(job_id)
        if self.repository.db:
            self.repository.db.execute("DELETE FROM job_items WHERE job_id=?", (job_id,))
        return bool(self.repository.delete(job_id))

    def export_rows(self, path, jobs) -> None:
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["job_id", "type", "account", "group", "campaign", "progress", "success", "skipped", "failed", "status", "created", "started", "finished", "retry_classification"])
            for job in jobs:
                writer.writerow([job.id, job.job_type, job.account_id, job.group_id, job.campaign_id, job.progress, job.success_count, job.skipped_count, job.failed_count, job.status, job.created_at, job.started_at, job.finished_at, job.retry_classification])
