from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def _pretty_date(value) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d %b %Y")
    except (TypeError, ValueError):
        return str(value)


class LicenseSuccessDialog(QDialog):
    viewLicenseRequested = Signal()

    def __init__(self, summary, *, source: str = "payment", parent=None):
        super().__init__(parent)
        state = summary.state
        source = str(source or "payment").lower()
        plan_name = str(summary.plan_name or state.plan or "SP Telegram")
        plan_code = str(state.plan or "LICENSE").upper()
        days = summary.days_remaining
        expires_text = _pretty_date(state.expires_at)

        self.setObjectName("license_success_dialog")
        self.setWindowTitle("SP Telegram — License Activated")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMaximumWidth(680)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("license_success_hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(7)

        mark = QLabel("✓")
        mark.setProperty("celebrationMark", True)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Congratulations!")
        title.setProperty("celebrationTitle", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_text = (
            "Your promotion was redeemed and your access is ready."
            if source == "promotion"
            else "Your license was activated successfully."
            if source == "activation"
            else "Payment verified. Your SP Telegram plan is now active."
        )
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("celebrationSubtitle", True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        plan = QLabel(plan_name)
        plan.setProperty("celebrationPlan", True)
        plan.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_layout.addWidget(mark)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addSpacing(3)
        hero_layout.addWidget(plan)
        root.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)

        def metric(caption: str, value: str) -> QFrame:
            frame = QFrame()
            frame.setProperty("licenseMetric", True)
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(3)
            value_label = QLabel(value)
            value_label.setProperty("licenseMetricValue", True)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption_label = QLabel(caption)
            caption_label.setProperty("licenseMetricCaption", True)
            caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(value_label)
            lay.addWidget(caption_label)
            return frame

        metrics.addWidget(metric("PLAN", plan_code))
        metrics.addWidget(metric("DAYS REMAINING", "—" if days is None else str(max(0, int(days)))))
        metrics.addWidget(metric("ACTIVE UNTIL", expires_text))
        root.addLayout(metrics)

        note = QLabel(
            "Your licensed automation features are available immediately. "
            "Telegram permissions, account restrictions and safety limits still apply."
        )
        note.setProperty("celebrationNote", True)
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(note)

        actions = QHBoxLayout()
        self.btn_view_license = QPushButton("View License")
        self.btn_view_license.setObjectName("btn_success_view_license")
        self.btn_continue = QPushButton("Start Using SP Telegram")
        self.btn_continue.setObjectName("btn_success_continue")
        self.btn_continue.setProperty("primary", True)
        actions.addWidget(self.btn_view_license)
        actions.addStretch()
        actions.addWidget(self.btn_continue)
        root.addLayout(actions)

        self.btn_view_license.clicked.connect(self._view_license)
        self.btn_continue.clicked.connect(self.accept)

    def _view_license(self):
        self.viewLicenseRequested.emit()
        self.accept()
