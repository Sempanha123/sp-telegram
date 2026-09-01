from __future__ import annotations
from datetime import datetime,timezone
from PySide6.QtCore import QObject,Signal
class SchedulerController(QObject):
    schedule_changed=Signal();missedOccurrenceNeedsDecision=Signal(int);schedulesChanged=Signal(list);scheduleUpdated=Signal(int);scheduledMessageSynced=Signal(int);campaignProgress=Signal(object);errorOccurred=Signal(str);toast_requested=Signal(str,str);featureLocked=Signal(str,str)
    def __init__(self,service,worker=None,parent=None):super().__init__(parent);self.service=service;self.worker=worker;self._handlers={};self._due_inflight=set();self._missed_notified=set();self.feature_gate=None;worker.operationCompleted.connect(self._done) if worker else None;worker.operationFailed.connect(self._failed) if worker else None;worker.finished.connect(self._on_worker_finished) if worker else None

    def _require_schedule(self,data):
        if self.feature_gate is None:return True
        from app.license.feature_keys import FeatureKey
        stype=str(data.get('schedule_type') or 'ONCE').upper();feature=FeatureKey.RECURRING_SCHEDULE if stype in {'REPEAT','RECURRING'} else FeatureKey.SCHEDULE_ONCE
        if self.feature_gate.has_feature(feature):return True
        self.featureLocked.emit(str(feature),str(self.feature_gate.get_required_plan(feature) or 'ULTIMATE'));return False

    def schedules(self):return self.service.get_schedules()
    def refresh(self):
        try:r=self.schedules();self.schedulesChanged.emit(r);return r
        except Exception as exc:self._error(exc);return []
    def save_schedule(self,data,activate_remote=True):
        if not self._require_schedule(data):return None
        try:
            item=self.service.save_schedule(data);self.schedule_changed.emit();self.scheduleUpdated.emit(item.id);self.refresh();self.toast_requested.emit('Schedule saved locally.','Success')
            if activate_remote and self.worker:self._submit(self.service.activate_schedule(item.id,self.campaignProgress.emit),'campaign_schedule',0,lambda r:self._activated(item.id,r),lambda _a,m:self._error(RuntimeError(m)))
            return item
        except Exception as exc:self._error(exc);return None
    create_schedule=save_schedule
    def _activated(self,id,result=None):
        self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Recurring schedule activated locally.' if isinstance(result,dict) and result.get('local_recurrence') else 'Telegram scheduled messages created for the next occurrence.','Success')
    def update(self,id,data):
        if not self._require_schedule(data):return None
        try:r=self.service.update_schedule(id,data);self.schedule_changed.emit();self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Schedule updated.','Success');return r
        except Exception as exc:self._error(exc);return None
    update_schedule=update
    def pause(self,id):
        try:r=self.service.pause_schedule(id);self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Schedule paused. Future local dispatch is disabled.','Warning');return r
        except Exception as exc:self._error(exc);return None
    def resume(self,id):
        current=self.service.repository.get_by_id(id);data={"schedule_type":getattr(current,"schedule_type",None) or "ONCE"}
        if not self._require_schedule(data):return None
        try:r=self.service.resume_schedule(id);self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Schedule resumed.','Success');return r
        except Exception as exc:self._error(exc);return None
    def cancel(self,id,cancel_remote=True):
        try:
            self.service.cancel_schedule(id);self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Schedule cancelled. Already published messages remain.','Warning')
            if cancel_remote and self.worker:self._submit(self.service.cancel_remote(id),'schedule_cancel_remote',0,lambda _r:self.refresh())
            return True
        except Exception as exc:self._error(exc);return False
    cancel_schedule=cancel
    def run_now(self,id):
        from app.license.feature_keys import FeatureKey
        if self.feature_gate is not None and not self.feature_gate.has_feature(FeatureKey.SCHEDULE_ONCE):self.featureLocked.emit(str(FeatureKey.SCHEDULE_ONCE),str(self.feature_gate.get_required_plan(FeatureKey.SCHEDULE_ONCE) or "PRO"));return None
        return self._submit(self.service.run_now(id,self.campaignProgress.emit),'schedule_run_now',0,lambda _r:self.toast_requested.emit('Run-now occurrence completed. Recurrence settings were not changed.','Success'))
    def sync_telegram(self,id):return self._submit(self.service.sync_telegram_schedule(id),'schedule_sync',0,lambda r:self._synced(id,r))
    sync_telegram_schedule=sync_telegram
    def _synced(self,id,result):self.scheduledMessageSynced.emit(id);self.refresh();self.toast_requested.emit(f"Telegram schedule synchronized. {result['missing_local_refs']} missing remote reference(s).",'Warning' if result['missing_local_refs'] else 'Success')
    def recover(self):return self.service.recover()
    def process_due(self):
        try:due=self.service.recover().get('due',[])
        except Exception:return
        now=datetime.now(timezone.utc)
        for schedule in due:
            if schedule.id in self._due_inflight:continue
            if schedule.schedule_type in {'ONCE','SCHEDULE_ONCE'}:continue  # Telegram-native queue owns the one-time execution.
            try:when=datetime.fromisoformat((schedule.next_run_at or schedule.run_at).replace('Z','+00:00')).astimezone(timezone.utc)
            except Exception:continue
            age=(now-when).total_seconds();policy=str(schedule.missed_policy or 'ASK_ME').upper()
            if age>120:
                if policy=='ASK_ME':
                    if schedule.id not in self._missed_notified:self._missed_notified.add(schedule.id);self.missedOccurrenceNeedsDecision.emit(schedule.id)
                    continue
                self.service.advance_missed(schedule.id);self.refresh();continue
            self._due_inflight.add(schedule.id)
            self._submit(self.service.dispatch_occurrence(schedule.id,self.campaignProgress.emit),'schedule_dispatch',0,lambda r,sid=schedule.id:self._due_done(sid,r),lambda _a,m,sid=schedule.id:self._due_failed(sid,m))
    def _due_done(self,id,result):self._due_inflight.discard(id);self._missed_notified.discard(id);self.scheduleUpdated.emit(id);self.refresh();self.toast_requested.emit('Scheduled campaign occurrence completed.','Success' if getattr(result,'status','')=='COMPLETED' else 'Warning')
    def _due_failed(self,id,message):self._due_inflight.discard(id);self._error(RuntimeError(message));self.refresh()
    def _submit(self,coro,operation,account_id,success,failure=None):
        if not self.worker:self._error(RuntimeError('Telegram runtime is unavailable.'));return None
        try:t=self.worker.submit_coroutine(coro,operation=operation,account_id=account_id);self._handlers[t]=(success,failure);return t
        except Exception as exc:self._error(exc);return None
    def _done(self,token,result):
        h=self._handlers.pop(token,None)
        if h and h[0]:h[0](result)
    def _failed(self,token,account_id,message):
        h=self._handlers.pop(token,None)
        if h and h[1]:h[1](account_id,message)
        elif h:self._error(RuntimeError(message))
    def _error(self,exc):m=str(exc) or 'Cannot complete the schedule operation.';self.errorOccurred.emit(m);self.toast_requested.emit(m,'Error')

    def _on_worker_finished(self) -> None:
        """Drain pending handlers when the worker thread stops unexpectedly."""
        pending = dict(self._handlers)
        self._handlers.clear()
        self._due_inflight.clear()
        for _token, (_success, failure) in pending.items():
            if failure:
                try:
                    failure(0, "The Telegram worker stopped unexpectedly.")
                except Exception:
                    pass
        if pending:
            self.toast_requested.emit(
                "The Telegram worker stopped. Pending schedule operations were cancelled.",
                "Warning",
            )
            self.refresh()
