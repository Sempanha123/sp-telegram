from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class AddMemberLiveActivity(QFrame):
    backgroundRequested = Signal()
    jobsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("add_member_live_activity")
        self.setMinimumHeight(150)

        self._frame = 0
        self._running = False
        self._counts = {"successful": 0, "skipped": 0, "failed": 0}
        self._rows = {}
        self._states = {}
        self._events = []

        root = QVBoxLayout(self)
        root.setContentsMargins(13, 10, 13, 10)
        root.setSpacing(7)

        top = QHBoxLayout()
        self.pulse = QLabel("◐")
        self.pulse.setObjectName("lbl_add_live_pulse")
        self.pulse.setFixedWidth(30)
        self.pulse.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.pulse)

        copy = QVBoxLayout()
        self.title = QLabel("Live Add Activity")
        self.title.setObjectName("lbl_add_live_title")
        self.current = QLabel("Waiting to start…")
        self.current.setObjectName("lbl_add_live_current")
        self.current.setWordWrap(True)
        self.via = QLabel("Accounts are prepared automatically")
        self.via.setObjectName("lbl_add_live_via")
        copy.addWidget(self.title)
        copy.addWidget(self.current)
        copy.addWidget(self.via)
        top.addLayout(copy, 1)

        self.btn_background = QPushButton("↘ Hide & Continue")
        self.btn_background.setObjectName("btn_add_live_background")
        self.btn_background.setEnabled(False)
        self.btn_background.setToolTip(
            "Hide this Add Members window. The job keeps running. "
            "Click the Add x/y chip in the top bar to reopen it."
        )
        self.btn_jobs = QPushButton("Open Jobs")
        self.btn_jobs.setObjectName("btn_add_live_jobs")

        buttons = QVBoxLayout()
        buttons.setSpacing(5)
        buttons.addWidget(self.btn_background)
        buttons.addWidget(self.btn_jobs)
        top.addLayout(buttons)
        root.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_add_live")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.summary = QLabel("0 processed • 0 added • 0 skipped • 0 failed")
        self.summary.setObjectName("lbl_add_live_summary")
        root.addWidget(self.summary)

        self.accounts = QFrame()
        self.accounts.setObjectName("add_live_accounts")
        self.accounts_layout = QGridLayout(self.accounts)
        self.accounts_layout.setContentsMargins(8, 7, 8, 7)
        self.accounts_layout.setHorizontalSpacing(10)
        self.accounts_layout.setVerticalSpacing(4)
        root.addWidget(self.accounts)

        self.feed = QLabel("Recent member activity will appear here.")
        self.feed.setObjectName("lbl_add_live_feed")
        self.feed.setWordWrap(True)
        root.addWidget(self.feed)

        self.btn_background.clicked.connect(self.backgroundRequested)
        self.btn_jobs.clicked.connect(self.jobsRequested)

        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._tick)

    def _clear_accounts(self):
        while self.accounts_layout.count():
            item = self.accounts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        self._states.clear()

    def start_job(self, account_plan):
        self._clear_accounts()
        self._frame = 0
        self._running = True
        self._counts = {"successful": 0, "skipped": 0, "failed": 0}
        self._events = []

        total = 0
        for row, item in enumerate(account_plan or []):
            account_id = int(item.get("account_id") or 0)
            name = str(item.get("name") or f"Account {account_id}")
            assigned = int(item.get("assigned") or 0)
            total += assigned

            name_label = QLabel(name)
            name_label.setObjectName("lbl_add_live_account_name")
            status_label = QLabel("● Ready")
            status_label.setObjectName("lbl_add_live_account_status")
            count_label = QLabel(f"0/{assigned}" if assigned else "0")
            count_label.setObjectName("lbl_add_live_account_assigned")
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.accounts_layout.addWidget(name_label, row, 0)
            self.accounts_layout.addWidget(status_label, row, 1)
            self.accounts_layout.addWidget(count_label, row, 2)

            self._rows[account_id] = {
                "name": name_label,
                "status": status_label,
                "count": count_label,
                "planned": assigned,
                "done": 0,
            }
            self._states[account_id] = {"kind": "ready", "member": ""}

        self.pulse.setText("◐")
        self.current.setText("Preparing first member…")
        self.via.setText("Waiting for Telegram worker…")
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(0)
        self.summary.setText("0 processed • 0 added • 0 skipped • 0 failed")
        self.feed.setText(
            "Running now. You can hide this window and reopen it from the Add x/y chip in the top bar."
        )
        self.btn_background.setEnabled(True)
        self.show()
        self.timer.start()

    def update_progress(self, payload):
        payload = dict(payload or {})
        current = str(
            payload.get("current")
            or payload.get("member_name")
            or payload.get("member")
            or payload.get("username")
            or "Working…"
        )
        account_id = int(payload.get("account_id") or 0)
        processed = int(payload.get("processed", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        successful = int(payload.get("successful", 0) or 0)
        skipped = int(payload.get("skipped", 0) or 0)
        failed = int(payload.get("failed", 0) or 0)

        old = dict(self._counts)
        if successful > old["successful"]:
            kind, icon, word = "success", "✓", "Added"
        elif failed > old["failed"]:
            kind, icon, word = "failed", "×", "Failed"
        elif skipped > old["skipped"]:
            kind, icon, word = "skipped", "↷", "Skipped"
        elif str(payload.get("status") or "").upper() == "WAITING":
            kind, icon, word = "waiting", "⏱", "Waiting"
        else:
            kind, icon, word = "adding", "◓", "Adding"

        self._counts = {
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
        }

        self.progress.setRange(0, max(1, total))
        self.progress.setValue(processed)
        self.summary.setText(
            f"{processed:,}/{total:,} processed • {successful:,} added • "
            f"{skipped:,} skipped • {failed:,} failed"
        )

        row = self._rows.get(account_id)
        account_name = f"Account {account_id}" if account_id else "Automatic account"
        if row:
            account_name = row["name"].text()
            if kind in {"success", "failed", "skipped"}:
                row["done"] = min(
                    row["planned"] if row["planned"] else row["done"] + 1,
                    row["done"] + 1,
                )
            row["count"].setText(
                f'{row["done"]}/{row["planned"]}' if row["planned"] else str(row["done"])
            )
            self._states[account_id] = {"kind": kind, "member": current}

        self.current.setText(f"{icon} {word}: {current}")
        self.via.setText(f"via {account_name}")

        event = f"{icon} {current} • {account_name}"
        if not self._events or self._events[-1] != event:
            self._events.append(event)
            self._events = self._events[-5:]
            self.feed.setText("    ".join(self._events))

        self._render_accounts()

    def _render_accounts(self):
        frame = ("◐", "◓", "◑", "◒")[self._frame]
        for account_id, row in self._rows.items():
            state = self._states.get(account_id, {"kind": "ready", "member": ""})
            kind = state.get("kind")
            member = state.get("member") or ""
            if kind == "adding":
                text = f"{frame} Adding {member}"
            elif kind == "waiting":
                text = f"⏱ Waiting {member}"
            elif kind == "success":
                text = f"✓ Added {member}"
            elif kind == "failed":
                text = f"× Failed {member}"
            elif kind == "skipped":
                text = f"↷ Skipped {member}"
            else:
                text = "● Ready"
            row["status"].setText(text)

    def _tick(self):
        if not self._running:
            return
        self._frame = (self._frame + 1) % 4
        self.pulse.setText(("◐", "◓", "◑", "◒")[self._frame])
        self._render_accounts()

    def finish(self, result=None, error_message=""):
        self._running = False
        self.timer.stop()
        self.btn_background.setEnabled(False)

        if error_message:
            self.pulse.setText("×")
            self.current.setText(str(error_message))
            self.via.setText("Open Jobs for details")
            return

        result = dict(result or {})
        successful = int(result.get("successful", 0) or 0)
        skipped = int(result.get("skipped", 0) or 0)
        failed = int(result.get("failed", 0) or 0)

        self.pulse.setText("✓" if not failed else "!")
        self.current.setText(
            f"Completed • {successful:,} added • {skipped:,} skipped • {failed:,} failed"
        )
        self.via.setText("Saved in Jobs")
        self.feed.setText("Finished. View Results or Open Jobs for the full history.")
