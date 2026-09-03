from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QProgressBar, QPushButton, QVBoxLayout


class LiveJobChip(QFrame):
    openRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("live_job_chip")
        self.setProperty("state", "running")
        self.setFixedHeight(42)
        self.setMinimumWidth(138)
        self.setMaximumWidth(250)
        self._job_id = 0
        self._processed = 0
        self._total = 0
        self._mode = "running"
        self._frame = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(7, 3, 7, 3)
        root.setSpacing(2)

        self.button = QPushButton("◐  Add 0/0")
        self.button.setObjectName("btn_live_job_chip")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.button.clicked.connect(self._open)
        root.addWidget(self.button)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_live_job_chip")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self._pulse = QTimer(self)
        self._pulse.setInterval(170)
        self._pulse.timeout.connect(self._animate)
        self._pulse.start()
        self.hide()

    def _open(self):
        self.openRequested.emit(int(self._job_id or 0))

    def _repolish(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)

    def _animate(self):
        if self._mode != "running" or not self.isVisible():
            return
        self._frame = (self._frame + 1) % 4
        self._render()

    def _render(self):
        if self._mode == "running":
            glyph = ("◐", "◓", "◑", "◒")[self._frame]
            text = f"{glyph}  Add {self._processed:,}/{self._total:,}" if self._total else f"{glyph}  Preparing"
        elif self._mode == "success":
            text = "✓  Add complete"
        elif self._mode == "warning":
            text = "!  Add paused"
        else:
            text = "×  Add failed"
        self.button.setText(text)

    def set_running(self, *, job_id=0, processed=0, total=0, tooltip=""):
        self._job_id = int(job_id or self._job_id or 0)
        self._processed = max(0, int(processed or 0))
        self._total = max(0, int(total or 0))
        self._mode = "running"
        self.setProperty("state", "running")
        self.progress.setRange(0, max(1, self._total))
        self.progress.setValue(min(self._processed, max(1, self._total)))
        self.button.setToolTip(tooltip or "Add Members is running. Click to reopen the Add Members window.")
        self.setToolTip(self.button.toolTip())
        self._render()
        self._repolish()
        self.show()

    def finish(self, state="success", tooltip=""):
        self._mode = state if state in {"success", "warning", "error"} else "success"
        self.setProperty("state", self._mode)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if self._mode == "success" else self.progress.value())
        self.button.setToolTip(tooltip or "Click to open Jobs.")
        self.setToolTip(self.button.toolTip())
        self._render()
        self._repolish()
        self.show()


class LiveJobUX(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.context = window.context
        self._active_job_id = 0
        self._dialogs = []
        self._clear_generation = 0

        self.chip = LiveJobChip(window.topbar)
        top_layout = window.topbar.layout()
        try:
            insert_at = top_layout.indexOf(window.topbar.btn_notifications)
        except Exception:
            insert_at = -1
        if insert_at < 0:
            insert_at = max(0, top_layout.count() - 3)
        top_layout.insertWidget(insert_at, self.chip)
        self.chip.openRequested.connect(self.open_from_chip)

        member = self.context.member_controller
        member.targetInvitationProgress.connect(self.on_progress)
        member.targetInvitationCompleted.connect(self.on_completed)
        member.targetInvitationFailed.connect(self.on_failed)

    def register_dialog(self, dialog):
        if dialog not in self._dialogs:
            self._dialogs.append(dialog)

        def cleanup(*_args):
            try:
                if dialog in self._dialogs:
                    self._dialogs.remove(dialog)
            except Exception:
                pass

        try:
            dialog.destroyed.connect(cleanup)
        except Exception:
            pass

    def active_dialog(self):
        alive = []
        running = None
        latest = None
        for dialog in list(self._dialogs):
            try:
                dialog.objectName()
            except RuntimeError:
                continue
            alive.append(dialog)
            latest = dialog
            if getattr(dialog, "_running", False):
                running = dialog
        self._dialogs = alive
        return running or latest

    def restore_dialog(self) -> bool:
        dialog = self.active_dialog()
        if dialog is None:
            return False
        try:
            dialog.showNormal()
        except Exception:
            try:
                dialog.show()
            except Exception:
                return False
        try:
            dialog.raise_()
            dialog.activateWindow()
        except Exception:
            pass
        return True

    def open_from_chip(self, job_id=0):
        if self.restore_dialog():
            return
        self.open_jobs(job_id)

    def _account_name(self, account_id):
        if not account_id:
            return "Automatic account"
        try:
            account = self.context.account_repository.get_by_id(int(account_id))
        except Exception:
            account = None
        if account is not None:
            return (
                getattr(account, "first_name", None)
                or getattr(account, "username", None)
                or f"Account {int(account_id)}"
            )
        return f"Account {int(account_id)}"

    def _tooltip(self, payload):
        current = str(payload.get("current") or payload.get("member_name") or payload.get("member") or "Preparing")
        account = self._account_name(payload.get("account_id"))
        processed = int(payload.get("processed", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        job_id = int(payload.get("job_id") or self._active_job_id or 0)
        lines = ["Add Members is running", f"Member: {current}", f"Account: {account}"]
        if total:
            lines.append(f"Progress: {processed:,}/{total:,}")
        if job_id:
            lines.append(f"Job #{job_id}")
        lines.append("Click to reopen Add Members")
        return "\n".join(lines)

    def on_progress(self, payload):
        payload = dict(payload or {})
        job_id = int(payload.get("job_id") or 0)
        if job_id:
            self._active_job_id = job_id
        self._clear_generation += 1
        self.chip.set_running(
            job_id=self._active_job_id,
            processed=payload.get("processed", 0),
            total=payload.get("total", 0),
            tooltip=self._tooltip(payload),
        )

    def on_completed(self, result):
        result = dict(result or {})
        successful = int(result.get("successful", 0) or 0)
        skipped = int(result.get("skipped", 0) or 0)
        failed = int(result.get("failed", 0) or 0)
        status = str(result.get("status") or "COMPLETED").upper()
        if status in {"PAUSED", "BLOCKED", "PARTIAL_SUCCESS"}:
            state = "warning"
        elif failed and not successful:
            state = "error"
        else:
            state = "success"
        self.chip.finish(
            state,
            f"{successful:,} added • {skipped:,} skipped • {failed:,} failed\nClick to reopen Add Members or open Jobs",
        )
        self._schedule_clear(7000)
        try:
            self.context.job_controller.refresh()
        except Exception:
            pass

    def on_failed(self, message):
        self.chip.finish(
            "error",
            f"{message or 'Add Members could not continue.'}\nClick to open Jobs",
        )
        self._schedule_clear(9000)
        try:
            self.context.job_controller.refresh()
        except Exception:
            pass

    def _schedule_clear(self, delay_ms):
        self._clear_generation += 1
        generation = self._clear_generation

        def clear_if_still():
            if generation == self._clear_generation:
                self.chip.hide()

        QTimer.singleShot(int(delay_ms), clear_if_still)

    def open_jobs(self, job_id=0):
        try:
            self.window.navigate("jobs", "Jobs")
        except Exception:
            return
        page = self.window.pages.get("jobs")
        if page is None:
            return
        try:
            page.controller.refresh()
        except Exception:
            pass


def install_live_job_ux(window):
    existing = getattr(window, "_live_job_ux", None)
    if existing is not None:
        return existing
    manager = LiveJobUX(window)
    window._live_job_ux = manager
    return manager
