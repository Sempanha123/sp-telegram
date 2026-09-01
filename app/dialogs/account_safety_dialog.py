from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QVBoxLayout,
)
from app.dialogs.dialog_compat import *


class AccountSafetyDialog(QDialog):
    """Bulk editor for conservative per-account operation ceilings."""

    def __init__(self, account_count: int, snapshot: dict | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("dlg_account_safety_limits")
        self.setWindowTitle("Account Safety Limits")
        self.resize(560, 560)
        current = dict(snapshot or {})

        root = QVBoxLayout(self); root.setContentsMargins(20, 18, 20, 18); root.setSpacing(12)
        title = QLabel("Smart Account Safety"); title.setProperty("dialogTitle", True); root.addWidget(title)
        scope = QLabel(f"Apply one fixed safety policy to {int(account_count):,} selected account(s).")
        scope.setProperty("secondary", True); root.addWidget(scope)
        note = QLabel(
            "Daily limits count attempts, not only successes. A FloodWait, restriction, or recovery hold stops the selected account. "
            "Unfinished work is never moved to another account automatically."
        )
        note.setWordWrap(True); note.setProperty("warning", True); root.addWidget(note)

        policy = QGroupBox("Policy"); form = QFormLayout(policy); form.setHorizontalSpacing(20); form.setVerticalSpacing(10)
        self.cmb_safety_preset = QComboBox(); self.cmb_safety_preset.setObjectName("cmb_account_safety_preset")
        self.cmb_safety_preset.addItems(["Recommended", "Conservative", "Recovery Hold", "Custom"])
        self.chk_smart_mode = QCheckBox("Enable hard daily limits and spacing")
        self.chk_smart_mode.setObjectName("chk_account_smart_limits"); self.chk_smart_mode.setChecked(bool(current.get("smart_mode", True)))
        self.spin_invite_limit = self._spin("spin_account_invite_daily_limit", 0, 20, int(current.get("invite_limit", 20) or 0), " invitation attempts / day")
        self.spin_post_limit = self._spin("spin_account_post_daily_limit", 0, 100, int(current.get("post_limit", 30) or 0), " post attempts / day")
        self.spin_invite_spacing = self._spin("spin_account_invite_spacing", 0, 3600, int(current.get("invite_spacing_seconds", 60) or 0), " seconds")
        self.spin_post_spacing = self._spin("spin_account_post_spacing", 0, 3600, int(current.get("post_spacing_seconds", 30) or 0), " seconds")
        form.addRow("Preset", self.cmb_safety_preset); form.addRow("", self.chk_smart_mode)
        form.addRow("Invitation daily ceiling", self.spin_invite_limit); form.addRow("Posting daily ceiling", self.spin_post_limit)
        form.addRow("Minimum invitation spacing", self.spin_invite_spacing); form.addRow("Minimum posting spacing", self.spin_post_spacing)
        root.addWidget(policy)

        recovery = QGroupBox("Account State"); recovery_form = QFormLayout(recovery); recovery_form.setHorizontalSpacing(20); recovery_form.setVerticalSpacing(10)
        self.cmb_safety_state = QComboBox(); self.cmb_safety_state.setObjectName("cmb_account_safety_state")
        self.cmb_safety_state.addItems(["Normal", "Watch", "Recovering", "Cooldown", "Restricted", "Disabled"])
        state = str(current.get("state") or "NORMAL").replace("_", " ").title()
        self.cmb_safety_state.setCurrentText(state if state in [self.cmb_safety_state.itemText(i) for i in range(self.cmb_safety_state.count())] else "Normal")
        self.spin_recovery_hours = self._spin("spin_account_recovery_hours", 1, 168, 72, " hours")
        self.le_recovery_reason = QLineEdit(); self.le_recovery_reason.setObjectName("le_account_recovery_reason")
        self.le_recovery_reason.setText(str(current.get("reason") or "")); self.le_recovery_reason.setPlaceholderText("Why this account is paused or watched")
        recovery_form.addRow("Safety state", self.cmb_safety_state); recovery_form.addRow("Hold duration", self.spin_recovery_hours); recovery_form.addRow("Reason", self.le_recovery_reason)
        root.addWidget(recovery)

        self.lbl_effect = QLabel(); self.lbl_effect.setWordWrap(True); self.lbl_effect.setProperty("secondary", True); root.addWidget(self.lbl_effect)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Apply to Selected")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

        self.cmb_safety_preset.currentTextChanged.connect(self._apply_preset)
        self.cmb_safety_state.currentTextChanged.connect(self._update_state_ui)
        for widget in (self.chk_smart_mode, self.spin_invite_limit, self.spin_post_limit, self.spin_invite_spacing, self.spin_post_spacing):
            signal = getattr(widget, "toggled", None) or getattr(widget, "valueChanged", None)
            if signal is not None: signal.connect(self._update_effect)
        self.cmb_safety_preset.setCurrentText("Custom" if snapshot else "Recommended")
        self._update_state_ui(); self._update_effect()

    @staticmethod
    def _spin(name: str, minimum: int, maximum: int, value: int, suffix: str) -> QSpinBox:
        widget = QSpinBox(); widget.setObjectName(name); widget.setRange(minimum, maximum); widget.setValue(max(minimum, min(maximum, value))); widget.setSuffix(suffix)
        return widget

    def _apply_preset(self, name: str) -> None:
        presets = {
            "Recommended": (True, 20, 30, 60, 30, "Normal"),
            "Conservative": (True, 10, 15, 120, 60, "Watch"),
            "Recovery Hold": (True, 5, 10, 300, 120, "Recovering"),
        }
        values = presets.get(str(name))
        if not values:
            return
        smart, invite, post, invite_gap, post_gap, state = values
        self.chk_smart_mode.setChecked(smart); self.spin_invite_limit.setValue(invite); self.spin_post_limit.setValue(post)
        self.spin_invite_spacing.setValue(invite_gap); self.spin_post_spacing.setValue(post_gap); self.cmb_safety_state.setCurrentText(state)
        if state == "Recovering" and not self.le_recovery_reason.text().strip():
            self.le_recovery_reason.setText("Manual recovery hold after spam or restriction warning.")

    def _update_state_ui(self, *_args) -> None:
        held = self.cmb_safety_state.currentText() in {"Recovering", "Cooldown"}
        self.spin_recovery_hours.setEnabled(held)
        self._update_effect()

    def _update_effect(self, *_args) -> None:
        state = self.cmb_safety_state.currentText()
        if state in {"Recovering", "Cooldown", "Restricted", "Disabled"}:
            text = f"{state} blocks new invitation and posting jobs for these accounts."
        elif state == "Watch":
            text = "Watch mode allows work at half of the configured daily ceilings. Three successful operations return the account to Normal."
        elif self.chk_smart_mode.isChecked():
            text = f"Normal mode allows up to {self.spin_invite_limit.value()} invitation and {self.spin_post_limit.value()} posting attempts per local day."
        else:
            text = "Daily quotas are disabled, but Telegram health, permissions, FloodWaits, and manual recovery states still block work."
        self.lbl_effect.setText(text)

    def values(self) -> dict:
        state = self.cmb_safety_state.currentText().upper().replace(" ", "_")
        until = None
        if state in {"RECOVERING", "COOLDOWN"}:
            until = (datetime.now(timezone.utc) + timedelta(hours=self.spin_recovery_hours.value())).isoformat(timespec="seconds")
        return {
            "smart_mode": self.chk_smart_mode.isChecked(),
            "safety_state": state,
            "invite_daily_limit": self.spin_invite_limit.value(),
            "post_daily_limit": self.spin_post_limit.value(),
            "invite_spacing_seconds": self.spin_invite_spacing.value(),
            "post_spacing_seconds": self.spin_post_spacing.value(),
            "cooldown_until": until,
            "recovery_reason": self.le_recovery_reason.text().strip() or None,
        }

# Add compatibility attributes for older PySide6 versions
if not hasattr(AccountSafetyDialog, 'Accepted'):
    AccountSafetyDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AccountSafetyDialog, 'Rejected'):
    AccountSafetyDialog.Rejected = QDialog.DialogCode.Rejected
