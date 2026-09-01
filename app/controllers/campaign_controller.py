from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from app.models.pagination import PaginationState


class CampaignController(QObject):
    campaignsChanged = Signal(list)
    campaign_selected = Signal(int)
    campaign_created = Signal(object)
    campaign_updated = Signal(object)
    campaignRemoved = Signal(int)
    campaignStarted = Signal(int)
    campaignProgress = Signal(object)
    campaignTargetStarted = Signal(int, int)
    campaignTargetCompleted = Signal(int, int)
    campaignTargetFailed = Signal(int, int, str)
    campaignCompleted = Signal(int)
    campaignFailed = Signal(int, str)
    scheduleUpdated = Signal(int)
    scheduledMessageSynced = Signal(int)
    errorOccurred = Signal(str)
    toast_requested = Signal(str, str)
    featureLocked = Signal(str, str)

    def __init__(self, service, worker=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.worker = worker
        self.pagination = PaginationState(page_size=50)
        self.search_text = ""
        self.status_filter = None
        self.type_filter = None
        self.schedule_filter = None
        self.group_filter = None
        self.account_filter = None
        self.current_items = []
        self._handlers = {}
        self.feature_gate = None
        if worker:
            worker.operationCompleted.connect(self._done)
            worker.operationFailed.connect(self._failed)
            worker.finished.connect(self._on_worker_finished)

    def _require(self, feature):
        if self.feature_gate is None:
            return True
        if self.feature_gate.has_feature(feature):
            return True
        self.featureLocked.emit(str(feature), str(self.feature_gate.get_required_plan(feature) or "PRO"))
        return False

    def campaigns(self):
        return self.refresh(emit=False)

    def refresh(self, emit=True):
        try:
            items, total = self.service.get_page(
                self.pagination.page,
                self.pagination.page_size,
                self.search_text,
                self.status_filter,
                self.type_filter,
                self.schedule_filter,
                self.group_filter,
                self.account_filter,
            )
            self.pagination.total_items = total
            self.pagination.clamp()
            self.current_items = items
            if emit:
                self.campaignsChanged.emit(items)
            return items
        except Exception as exc:
            self._error(exc)
            return []

    def set_search(self, text):
        self.search_text = text
        self.pagination.page = 1
        return self.refresh()

    def set_filter(self, name, value):
        val = None if value in {None, "All", ""} else value
        if name == "Status":
            self.status_filter = val
        elif name == "Type":
            self.type_filter = None if val is None else {
                "Multiple Messages": "MULTI_MESSAGE",
                "Multi Message": "MULTI_MESSAGE",
            }.get(val, val)
        elif name == "Schedule":
            self.schedule_filter = val
        elif name == "Group":
            raw = str(val).split(":", 1)[0].strip() if val else ""
            self.group_filter = int(raw) if raw.isdigit() else None
        elif name == "Account":
            raw = str(val).split(":", 1)[0].strip() if val else ""
            self.account_filter = int(raw) if raw.isdigit() else None
        self.pagination.page = 1
        return self.refresh()

    def all_campaigns(self):
        try:
            return self.service.get_campaigns()
        except Exception as exc:
            self._error(exc)
            return []

    def create(self, data):
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.CAMPAIGNS):
            return None
        try:
            item = self.service.create(data)
            self.campaign_created.emit(item)
            status = str(getattr(item, "status", "") or "DRAFT").upper()
            if status == "DRAFT":
                message = "Campaign draft saved."
            elif status == "SCHEDULED":
                message = "Campaign scheduled."
            else:
                message = "Campaign created and ready."
            self.toast_requested.emit(message, "Success")
            self.refresh()
            return item
        except Exception as exc:
            self._error(exc)
            return None

    create_campaign = create

    def update(self, id, data):
        try:
            item = self.service.update(id, data)
            self.campaign_updated.emit(item)
            self.toast_requested.emit("Campaign updated.", "Success")
            self.refresh()
            return item
        except Exception as exc:
            self._error(exc)
            return None

    edit_campaign = update

    def duplicate(self, id):
        try:
            item = self.service.duplicate(id)
            self.toast_requested.emit("Campaign duplicated as a draft.", "Success")
            self.refresh()
            return item
        except Exception as exc:
            self._error(exc)
            return None

    duplicate_campaign = duplicate

    def delete(self, id):
        try:
            self.service.delete(id)
            self.campaignRemoved.emit(id)
            self.toast_requested.emit("Campaign removed or cancelled safely.", "Success")
            self.refresh()
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def delete_draft(self, id):
        try:
            r = self.service.delete_draft(id)
            self.refresh()
            return r
        except Exception as exc:
            self._error(exc)
            return False

    def archive(self, id):
        try:
            r = self.service.archive(id)
            self.refresh()
            self.toast_requested.emit("Campaign archived.", "Success")
            return r
        except Exception as exc:
            self._error(exc)
            return None

    archive_campaign = archive

    def unarchive(self, id):
        try:
            r = self.service.unarchive(id)
            self.refresh()
            self.toast_requested.emit("Campaign restored from archive.", "Success")
            return r
        except Exception as exc:
            self._error(exc)
            return None

    unarchive_campaign = unarchive

    def details(self, id):
        return self.service.get_details(id)

    get_campaign_details = details

    def preview_campaign(self, id):
        return self.details(id)

    def validate_campaign(self, id):
        try:
            r = self.service.build_preflight(id)
            self.campaign_updated.emit(self.service.repository.get_by_id(id))
            self.refresh()
            return r
        except Exception as exc:
            self._error(exc)
            return None

    def run_campaign(self, id):
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SEND_NOW):
            return None
        self.campaignStarted.emit(id)
        return self._submit(
            self.service.run(id, progress_callback=self._progress),
            "campaign_send",
            0,
            lambda r: self._run_done(id, r),
            lambda _a, m: self._run_failed(id, m),
        )

    def _progress(self, payload):
        self.campaignProgress.emit(payload)
        event = payload.get("event") if isinstance(payload, dict) else None
        cid = int(payload.get("campaign_id") or 0) if isinstance(payload, dict) else 0
        gid = (
            int(payload.get("group_id") or 0)
            if isinstance(payload, dict) and payload.get("group_id")
            else 0
        )
        if event == "target_started" and cid and gid:
            self.campaignTargetStarted.emit(cid, gid)
        elif event == "target_completed" and cid and gid:
            self.campaignTargetCompleted.emit(cid, gid)
        elif event == "target_failed" and cid and gid:
            self.campaignTargetFailed.emit(cid, gid, str(payload.get("error") or "Target failed."))

    def _run_done(self, id, result):
        self.campaignCompleted.emit(id)
        self.campaign_updated.emit(result)
        self.toast_requested.emit(
            f"Campaign finished with status {result.status}.",
            "Success" if result.status == "COMPLETED" else "Warning",
        )
        self.refresh()

    def _run_failed(self, id, message):
        self.campaignFailed.emit(id, message)
        self.toast_requested.emit(message, "Error")
        self.refresh()

    def pause_campaign(self, id):
        try:
            self.service.pause(id)
            self.refresh()
            self.toast_requested.emit(
                "Campaign paused. Completed deliveries are preserved.", "Warning"
            )
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def resume_campaign(self, id):
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SEND_NOW):
            return None
        self.campaignStarted.emit(id)
        return self._submit(
            self.service.resume(id, progress_callback=self._progress),
            "campaign_resume",
            0,
            lambda r: self._run_done(id, r),
            lambda _a, m: self._run_failed(id, m),
        )

    def cancel_campaign(self, id):
        try:
            self.service.cancel(id)
            self.refresh()
            self.toast_requested.emit(
                "Campaign cancelled. Already published messages remain.", "Warning"
            )
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def set_operations_paused(self, paused):
        self.service.set_operations_paused(paused)

    def managed_targets(self):
        try:
            return self.service.get_managed_targets()
        except Exception as exc:
            self._error(exc)
            return []

    def plan_smart_targets(self, group_ids, messages_per_target=1):
        try:
            return self.service.plan_smart_targets(group_ids, messages_per_target=messages_per_target)
        except Exception as exc:
            self._error(exc)
            return {
                "assignments": [],
                "blockers": [str(exc)],
                "account_plan": [],
                "fixed": True,
                "no_runtime_fallback": True,
            }

    def export_results(self, id, path):
        try:
            import csv

            details = self.service.get_details(id)
            campaign = details["campaign"]
            targets = {t.id: t for t in details["targets"]}
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(
                    [
                        "campaign",
                        "group",
                        "account",
                        "status",
                        "scheduled_at",
                        "sent_at",
                        "telegram_message_id",
                        "error_code",
                    ]
                )
                for d in details["deliveries"]:
                    t = targets.get(d.campaign_target_id)
                    w.writerow(
                        [
                            campaign.name,
                            t.group_title if t else "",
                            t.account_name if t else "",
                            d.status,
                            d.scheduled_for,
                            d.sent_at,
                            d.telegram_message_id,
                            "",
                        ]
                    )
            self.toast_requested.emit("Campaign results exported.", "Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def _submit(self, coro, operation, account_id, success, failure=None):
        if not self.worker:
            self._error(RuntimeError("Telegram runtime is unavailable."))
            return None
        try:
            token = self.worker.submit_coroutine(coro, operation=operation, account_id=account_id)
            self._handlers[token] = (success, failure)
            return token
        except Exception as exc:
            self._error(exc)
            return None

    def _done(self, token, result):
        h = self._handlers.pop(token, None)
        if h and h[0]:
            h[0](result)

    def _failed(self, token, account_id, message):
        h = self._handlers.pop(token, None)
        if not h:
            return
        if h[1]:
            h[1](account_id, message)
        else:
            self._error(RuntimeError(message))

    def _on_worker_finished(self):
        pending = dict(self._handlers)
        self._handlers.clear()
        for _token, (success, failure) in pending.items():
            if failure:
                try:
                    failure(0, "The Telegram worker stopped unexpectedly.")
                except Exception:
                    pass
        if pending:
            self.toast_requested.emit(
                "The Telegram worker stopped. Pending operations were cancelled.", "Warning"
            )
            self.refresh()

    def _error(self, exc):
        message = str(exc) or "Cannot complete the campaign operation."
        self.errorOccurred.emit(message)
        self.toast_requested.emit(message, "Error")
