from __future__ import annotations

from app.operations.retry_policy import RetryPolicy


class JobMonitor:
    def __init__(self, job_repository, attempt_repository=None, alert_manager=None, logger=None) -> None:
        self.jobs = job_repository
        self.attempts = attempt_repository
        self.alerts = alert_manager
        self.logger = logger

    def recover_interrupted(self) -> dict[str, int]:
        result = self.jobs.mark_interrupted_jobs()
        if result.get("reconcile_required") and self.alerts:
            self.alerts.raise_alert(
                "WARNING", "INTERRUPTED_OUTGOING_JOB", "Outgoing jobs require reconciliation",
                f"{result['reconcile_required']} interrupted outgoing job(s) require review before any retry.",
                dedupe_key="jobs:reconcile-required", source_type="JOB", requires_action=True, action_type="REVIEW_JOBS",
            )
        return result

    def classify_failure(self, job_id: int, error_code: str | None, message: str | None) -> str:
        classification = str(RetryPolicy.classify(error_code, message))
        self.jobs.update_fields(job_id, {"retry_classification": classification})
        return classification
