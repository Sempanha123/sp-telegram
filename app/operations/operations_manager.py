from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.constants import OperationalState, WorkerState


class OperationsManager(QObject):
    systemStateChanged = Signal(str)
    workerStateChanged = Signal(str, str)
    performanceUpdated = Signal(object)
    networkStateChanged = Signal(str)
    databaseStateChanged = Signal(str)
    operationsPaused = Signal()
    operationsResumed = Signal()
    criticalAlertRaised = Signal(object)

    def __init__(self, system_monitor, worker_registry, recovery_manager, restriction_manager,
                 network_monitor, resource_locks, settings_service, logger=None, parent=None) -> None:
        super().__init__(parent)
        self.system_monitor = system_monitor
        self.workers = worker_registry
        self.recovery = recovery_manager
        self.feature_gate = None
        self.restrictions = restriction_manager
        self.network = network_monitor
        self.resource_locks = resource_locks
        self.settings = settings_service
        self.logger = logger
        self.state = OperationalState.STARTING
        self._pause_handlers: dict[str, tuple[callable | None, callable | None]] = {}
        self._accepting_operations = True
        self._state_before_maintenance: OperationalState | None = None
        self.network.stateChanged.connect(self._network_changed)

    def register_component(self, name: str, pause=None, resume=None) -> None:
        self._pause_handlers[name] = (pause, resume)

    def set_state(self, state: str) -> None:
        state = OperationalState(state)
        if state != self.state:
            self.state = state
            self.systemStateChanged.emit(str(state))
            if self.logger:
                self.logger.info("SYSTEM", f"Operational state changed to {state}.", action="OPERATIONAL_STATE")

    def mark_ready(self) -> None:
        if self.state == OperationalState.STARTING:
            self.set_state(OperationalState.READY)

    def pause_all(self) -> None:
        if self.state in {OperationalState.PAUSED, OperationalState.SHUTTING_DOWN}:
            return
        self._accepting_operations = False
        for pause, _resume in self._pause_handlers.values():
            if pause:
                try: pause()
                except Exception as exc:
                    if self.logger: self.logger.error("SYSTEM", f"Pause handler failed: {exc}", action="PAUSE_HANDLER")
        self.set_state(OperationalState.PAUSED)
        self.operationsPaused.emit()

    def resume_all(self) -> None:
        if self.state != OperationalState.PAUSED:
            return
        # Ambiguous outgoing jobs are intentionally not auto-resumed here.
        if self.system_monitor.jobs.count_by_status("RECONCILE_REQUIRED") > 0:
            self.set_state(OperationalState.DEGRADED)
            return
        self.restrictions.refresh_expiries()
        for _pause, resume in self._pause_handlers.values():
            if resume:
                try: resume()
                except Exception as exc:
                    if self.logger: self.logger.error("SYSTEM", f"Resume handler failed: {exc}", action="RESUME_HANDLER")
        self._accepting_operations = True
        self.set_state(OperationalState.READY)
        self.operationsResumed.emit()

    def enter_maintenance(self) -> None:
        if self.state == OperationalState.MAINTENANCE:
            return
        self._state_before_maintenance = self.state
        # Maintenance must quiesce outgoing components first.  Reuse the same
        # cooperative pause handlers as Emergency Pause rather than force-killing
        # threads or allowing new Telegram writes during restore/VACUUM work.
        if self.state not in {OperationalState.PAUSED, OperationalState.SHUTTING_DOWN}:
            self.pause_all()
        self._accepting_operations = False
        self.set_state(OperationalState.MAINTENANCE)

    def leave_maintenance(self) -> None:
        previous = self._state_before_maintenance
        self._state_before_maintenance = None
        if previous == OperationalState.PAUSED:
            self._accepting_operations = False
            self.set_state(OperationalState.PAUSED)
            return
        # resume_all owns the reconciliation guard and invokes all registered
        # component resume callbacks.
        self.set_state(OperationalState.PAUSED)
        self.resume_all()

    def begin_shutdown(self) -> None:
        if self.state not in {OperationalState.PAUSED, OperationalState.SHUTTING_DOWN}:
            self.pause_all()
        self._accepting_operations = False
        self.set_state(OperationalState.SHUTTING_DOWN)

    def can_start_network_operation(self) -> bool:
        return (
            self._accepting_operations
            and self.state in {OperationalState.READY, OperationalState.DEGRADED}
            and str(self.network.state).upper() != "OFFLINE"
        )

    def refresh(self) -> dict:
        stale_threshold = int(self.settings.get("worker_heartbeat_stale_seconds", 60))
        for name in self.workers.mark_stale(stale_threshold):
            self.workerStateChanged.emit(name, WorkerState.UNRESPONSIVE)
        auto_recovery_allowed=True
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            auto_recovery_allowed=self.feature_gate.has_feature(FeatureKey.SAFE_RECOVERY)
        if auto_recovery_allowed and bool(self.settings.get("auto_restart_failed_workers", True)):
            self.restart_failed_workers(automatic=True)
        self.restrictions.refresh_expiries()
        snapshot = self.system_monitor.snapshot()
        self.performanceUpdated.emit(snapshot.get("performance", {}))
        self.databaseStateChanged.emit(snapshot["database"]["state"])
        return snapshot

    def restart_failed_workers(self, automatic: bool = False) -> dict[str, bool]:
        results = {}
        for worker in self.workers.all():
            if worker.state in {WorkerState.FAILED, WorkerState.UNRESPONSIVE, WorkerState.STOPPED}:
                results[worker.name] = self.recovery.restart_worker(worker.name, automatic=automatic)
                current = self.workers.get(worker.name)
                if current: self.workerStateChanged.emit(worker.name, current.state)
        return results

    def _network_changed(self, state: str) -> None:
        self.networkStateChanged.emit(state)
        if state == "OFFLINE" and self.state in {OperationalState.READY, OperationalState.DEGRADED}:
            # Degraded is deliberately different from a global operator pause:
            # local UI/DB work remains available, but new network operations are gated.
            self._accepting_operations = False
            self.set_state(OperationalState.DEGRADED)
        elif state == "ONLINE" and self.state == OperationalState.DEGRADED:
            if self.system_monitor.jobs.count_by_status("RECONCILE_REQUIRED") == 0:
                self._accepting_operations = True
                self.set_state(OperationalState.READY)
