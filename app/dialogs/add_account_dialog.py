from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.utils.qr_renderer import render_qr_pixmap


class AddAccountDialog(QDialog):
    """Telegram account login wizard; existing records still use the local metadata editor."""

    openSettingsRequested = Signal()

    METHOD, PHONE, VERIFY, PASSWORD, QR, COMPLETE = range(6)

    def __init__(self, account=None, tags: list[str] | None = None, parent=None, controller=None, existing_login_account=None):
        super().__init__(parent)
        self.account = account
        self.controller = controller
        self.existing_login_account = existing_login_account
        self._login_account_id = 0
        self._profile = None
        self._qr_expires: datetime | None = None
        self._login_in_progress = False
        self._cancel_requested = False
        self._cancelling = False
        self._cancel_timeout = None
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._update_qr_countdown)
        self.setMinimumWidth(560)
        self.resize(620, 560)
        if account is not None:
            self._build_editor(tags or [])
        else:
            self.setWindowTitle("Add Telegram Account")
            self._build_wizard()
            self._wire_controller()
            if self.existing_login_account is not None:
                self.le_login_phone.setText(self.existing_login_account.phone or "")
                self.setWindowTitle("Login / Attach Telegram Session")

    # -------- Existing local metadata editor --------
    def _build_editor(self, tags: list[str]):
        self.setWindowTitle("Edit Local Account")
        root = QVBoxLayout(self)
        note = QLabel("Telegram identity is read-only after successful authorization. Edit local notes/tags here; refresh Telegram profile from the account actions.")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        root.addWidget(note)
        form = QFormLayout()
        self.le_account_name = QLineEdit(self.account.first_name or "")
        self.le_account_name.setObjectName("le_account_name")
        self.le_account_name.setReadOnly(bool(self.account.authorization_status == "AUTHORIZED"))
        self.le_telegram_user_id = QLineEdit(str(self.account.telegram_user_id or ""))
        self.le_telegram_user_id.setObjectName("le_telegram_user_id")
        self.le_telegram_user_id.setReadOnly(bool(self.account.telegram_user_id))
        self.le_account_username = QLineEdit(self.account.username or "")
        self.le_account_username.setObjectName("le_account_username")
        self.le_account_username.setReadOnly(bool(self.account.authorization_status == "AUTHORIZED"))
        self.le_account_phone = QLineEdit(self.account.phone or "")
        self.le_account_phone.setObjectName("le_account_phone")
        self.le_account_phone.setReadOnly(bool(self.account.authorization_status == "AUTHORIZED"))
        self.le_account_tags = QLineEdit(", ".join(tags))
        self.le_account_tags.setObjectName("le_account_tags")
        self.txt_account_notes = QTextEdit(self.account.notes or "")
        self.txt_account_notes.setObjectName("txt_account_notes")
        self.txt_account_notes.setMaximumHeight(100)
        form.addRow("Display Name", self.le_account_name)
        form.addRow("Telegram ID", self.le_telegram_user_id)
        form.addRow("Username", self.le_account_username)
        form.addRow("Phone", self.le_account_phone)
        form.addRow("Tags", self.le_account_tags)
        form.addRow("Notes", self.txt_account_notes)
        root.addLayout(form)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.btn_add_account = box.button(QDialogButtonBox.StandardButton.Save)
        self.btn_add_account.setObjectName("btn_add_account")
        self.btn_add_account.setText("Save Account")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def data(self):
        if self.account is None:
            return {}
        return {
            "display_name": self.le_account_name.text().strip(),
            "telegram_user_id": self.le_telegram_user_id.text().strip() or None,
            "username": self.le_account_username.text().strip(),
            "phone": self.le_account_phone.text().strip(),
            "tags": [x.strip() for x in self.le_account_tags.text().split(",") if x.strip()],
            "notes": self.txt_account_notes.toPlainText().strip(),
        }

    # -------- Login wizard --------
    def _build_wizard(self):
        root = QVBoxLayout(self)
        self.lbl_login_progress = QLabel("1 Account   •   2 Verify   •   3 Security   •   4 Complete")
        self.lbl_login_progress.setObjectName("lbl_login_progress")
        self.lbl_login_progress.setProperty("emphasis", True)
        root.addWidget(self.lbl_login_progress)
        self.lbl_login_error = QLabel("")
        self.lbl_login_error.setWordWrap(True)
        self.lbl_login_error.setProperty("tone", "danger")
        root.addWidget(self.lbl_login_error)
        self.stack_login = QStackedWidget()
        self.stack_login.setObjectName("stack_login")
        root.addWidget(self.stack_login, 1)
        self._build_method_page()
        self._build_phone_page()
        self._build_verify_page()
        self._build_password_page()
        self._build_qr_page()
        self._build_complete_page()
        self.stack_login.setCurrentIndex(self.METHOD)

    def _page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(12)
        self.stack_login.addWidget(page)
        return page, layout

    def _title(self, layout, title, text):
        label = QLabel(title)
        label.setProperty("dialogTitleLarge", True)
        layout.addWidget(label)
        note = QLabel(text)
        note.setWordWrap(True)
        note.setProperty("muted", True)
        layout.addWidget(note)

    def _set_login_feedback(self, text: str, tone: str) -> None:
        self.lbl_login_error.setProperty("tone", tone)
        self.lbl_login_error.setText(text)
        self.lbl_login_error.style().unpolish(self.lbl_login_error)
        self.lbl_login_error.style().polish(self.lbl_login_error)

    def _build_method_page(self):
        page, layout = self._page()
        self._title(layout, "Add Telegram Account", "Choose how to authorize this application. Verification codes, 2FA passwords and QR tokens are never stored.")
        self.rb_login_phone = QRadioButton("Phone Login")
        self.rb_login_phone.setObjectName("rb_login_phone")
        self.rb_login_phone.setChecked(True)
        self.rb_login_qr = QRadioButton("QR Login")
        self.rb_login_qr.setObjectName("rb_login_qr")
        group = QButtonGroup(self)
        group.addButton(self.rb_login_phone)
        group.addButton(self.rb_login_qr)
        layout.addWidget(self.rb_login_phone)
        layout.addWidget(self.rb_login_qr)
        layout.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        self.btn_login_cancel = QPushButton("Cancel")
        self.btn_login_cancel.setObjectName("btn_login_cancel")
        self.btn_login_method_next = QPushButton("Next")
        self.btn_login_method_next.setObjectName("btn_login_method_next")
        self.btn_login_method_next.setProperty("primary", True)
        row.addWidget(self.btn_login_cancel)
        row.addWidget(self.btn_login_method_next)
        layout.addLayout(row)
        self.btn_login_cancel.clicked.connect(self.reject)
        self.btn_login_method_next.clicked.connect(self._choose_method)

    def _build_phone_page(self):
        page, layout = self._page()
        self._title(layout, "Phone Login", "Enter the phone number for the Telegram account you are authorized to use.")
        form = QFormLayout()
        self.cmb_phone_country = QComboBox()
        self.cmb_phone_country.setObjectName("cmb_phone_country")
        self.cmb_phone_country.addItems(["Cambodia (+855)", "United States (+1)", "United Kingdom (+44)", "Thailand (+66)", "Vietnam (+84)", "Other / number includes +code"])
        self.le_login_phone = QLineEdit()
        self.le_login_phone.setObjectName("le_login_phone")
        self.le_login_phone.setPlaceholderText("e.g. 12 345 678")
        form.addRow("Country", self.cmb_phone_country)
        form.addRow("Phone Number", self.le_login_phone)
        layout.addLayout(form)
        layout.addStretch()
        row = QHBoxLayout()
        self.btn_login_back = QPushButton("Back")
        self.btn_login_back.setObjectName("btn_login_back")
        self.btn_send_login_code = QPushButton("Send Login Code")
        self.btn_send_login_code.setObjectName("btn_send_login_code")
        self.btn_send_login_code.setProperty("primary", True)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("btn_login_cancel")
        row.addWidget(self.btn_login_back)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.btn_send_login_code)
        layout.addLayout(row)
        self.btn_login_back.clicked.connect(lambda: self.stack_login.setCurrentIndex(self.METHOD))
        cancel.clicked.connect(self.reject)
        self.btn_send_login_code.clicked.connect(self._send_code)

    def _build_verify_page(self):
        page, layout = self._page()
        self._title(layout, "Verification", "Enter the code Telegram sent to your account. The field is cleared immediately after each authentication attempt.")
        form = QFormLayout()
        self.le_login_code = QLineEdit()
        self.le_login_code.setObjectName("le_login_code")
        self.le_login_code.setPlaceholderText("Verification code")
        form.addRow("Code", self.le_login_code)
        layout.addLayout(form)
        layout.addStretch()
        row = QHBoxLayout()
        self.btn_login_code_back = QPushButton("Back")
        self.btn_login_code_back.setObjectName("btn_login_code_back")
        self.btn_resend_login_code = QPushButton("Resend")
        self.btn_resend_login_code.setObjectName("btn_resend_login_code")
        self.btn_verify_login_code = QPushButton("Verify")
        self.btn_verify_login_code.setObjectName("btn_verify_login_code")
        self.btn_verify_login_code.setProperty("primary", True)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("btn_login_cancel")
        row.addWidget(self.btn_login_code_back)
        row.addWidget(self.btn_resend_login_code)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.btn_verify_login_code)
        layout.addLayout(row)
        self.btn_login_code_back.clicked.connect(self._back_to_phone)
        self.btn_resend_login_code.clicked.connect(self._resend_code)
        self.btn_verify_login_code.clicked.connect(self._verify_code)
        cancel.clicked.connect(self.reject)

    def _build_password_page(self):
        page, layout = self._page()
        self._title(layout, "Two-Step Verification", "Telegram requires your account password. SP Telegram does not save or log this password.")
        form = QFormLayout()
        self.le_login_2fa_password = QLineEdit()
        self.le_login_2fa_password.setObjectName("le_login_2fa_password")
        self.le_login_2fa_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password", self.le_login_2fa_password)
        layout.addLayout(form)
        layout.addStretch()
        row = QHBoxLayout()
        self.btn_login_2fa_back = QPushButton("Back")
        self.btn_login_2fa_back.setObjectName("btn_login_2fa_back")
        self.btn_verify_2fa = QPushButton("Verify Password")
        self.btn_verify_2fa.setObjectName("btn_verify_2fa")
        self.btn_verify_2fa.setProperty("primary", True)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("btn_login_cancel")
        row.addWidget(self.btn_login_2fa_back)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.btn_verify_2fa)
        layout.addLayout(row)
        self.btn_login_2fa_back.clicked.connect(lambda: self.stack_login.setCurrentIndex(self.VERIFY))
        self.btn_verify_2fa.clicked.connect(self._verify_password)
        cancel.clicked.connect(self.reject)

    def _build_qr_page(self):
        page, layout = self._page()
        self._title(layout, "QR Login", "Scan this QR code using an already logged-in Telegram application. The QR image exists only in memory.")
        self.lbl_qr_login_image = QLabel("Generating QR…")
        self.lbl_qr_login_image.setObjectName("lbl_qr_login_image")
        self.lbl_qr_login_image.setMinimumSize(280, 280)
        self.lbl_qr_login_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_qr_login_image, 0)
        self.lbl_qr_login_status = QLabel("Waiting for confirmation…")
        self.lbl_qr_login_status.setObjectName("lbl_qr_login_status")
        self.lbl_qr_login_expiry = QLabel("Expires in: --:--")
        self.lbl_qr_login_expiry.setObjectName("lbl_qr_login_expiry")
        layout.addWidget(self.lbl_qr_login_status)
        layout.addWidget(self.lbl_qr_login_expiry)
        row = QHBoxLayout()
        self.btn_refresh_login_qr = QPushButton("Refresh QR")
        self.btn_refresh_login_qr.setObjectName("btn_refresh_login_qr")
        self.btn_cancel_qr_login = QPushButton("Cancel")
        self.btn_cancel_qr_login.setObjectName("btn_cancel_qr_login")
        row.addWidget(self.btn_refresh_login_qr)
        row.addStretch()
        row.addWidget(self.btn_cancel_qr_login)
        layout.addLayout(row)
        self.btn_refresh_login_qr.clicked.connect(lambda: self.controller.refresh_qr_login(self._login_account_id) if self._login_account_id else None)
        self.btn_cancel_qr_login.clicked.connect(self.reject)

    def _build_complete_page(self):
        page, layout = self._page()
        self._title(layout, "Account Connected", "Telegram authorization has been saved in the account-specific local session file.")
        self.lbl_login_profile = QLabel("")
        self.lbl_login_profile.setWordWrap(True)
        layout.addWidget(self.lbl_login_profile)
        layout.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        self.btn_login_open_account = QPushButton("Open Account")
        self.btn_login_open_account.setObjectName("btn_login_open_account")
        self.btn_login_finish = QPushButton("Finish")
        self.btn_login_finish.setObjectName("btn_login_finish")
        self.btn_login_finish.setProperty("primary", True)
        row.addWidget(self.btn_login_open_account)
        row.addWidget(self.btn_login_finish)
        layout.addLayout(row)
        self.btn_login_finish.clicked.connect(self.accept)
        self.btn_login_open_account.clicked.connect(self.accept)

    def _wire_controller(self):
        if not self.controller:
            return
        self.controller.loginCodeRequested.connect(self._code_requested)
        self.controller.loginPasswordRequired.connect(self._password_required)
        self.controller.loginCompleted.connect(self._login_completed)
        self.controller.loginFailed.connect(self._login_failed)
        self.controller.loginCancelled.connect(self._login_cancelled)
        self.controller.qrLoginReady.connect(self._qr_ready)
        self.controller.qrLoginExpired.connect(self._qr_expired)
        self.controller.loginStateChanged.connect(self._state_changed)

    def _choose_method(self):
        self.lbl_login_error.clear()
        if self.rb_login_qr.isChecked():
            self._login_in_progress = True
            self.stack_login.setCurrentIndex(self.QR)
            self.lbl_qr_login_status.setText("Generating QR…")
            self.controller.start_qr_login()
        else:
            self.stack_login.setCurrentIndex(self.PHONE)

    def _normalized_phone(self) -> str:
        raw = self.le_login_phone.text().strip().replace(" ", "").replace("-", "")
        if raw.startswith("+"):
            return raw
        prefixes = {0: "+855", 1: "+1", 2: "+44", 3: "+66", 4: "+84"}
        prefix = prefixes.get(self.cmb_phone_country.currentIndex(), "")
        return prefix + raw.lstrip("0") if prefix else raw

    def _send_code(self):
        self.lbl_login_error.clear()
        self.btn_send_login_code.setEnabled(False)
        self.btn_send_login_code.setText("Sending login code…")
        self._login_in_progress = True
        self.controller.start_phone_login(self._normalized_phone(), getattr(self.existing_login_account, "id", None))

    def _resend_code(self):
        self.lbl_login_error.clear()
        self.btn_resend_login_code.setEnabled(False)
        if self._login_account_id:
            self.controller.resend_login_code(self._login_account_id)

    def _back_to_phone(self):
        if self._login_account_id and self.controller:
            self.controller.cancel_login(self._login_account_id)
            self._login_account_id = 0
        self.stack_login.setCurrentIndex(self.PHONE)

    def _verify_code(self):
        code = self.le_login_code.text()
        self.le_login_code.clear()  # never retain OTP after submission
        self.btn_verify_login_code.setEnabled(False)
        self.controller.submit_login_code(self._login_account_id, code)

    def _verify_password(self):
        password = self.le_login_2fa_password.text()
        self.le_login_2fa_password.clear()  # never retain password after submission
        self.btn_verify_2fa.setEnabled(False)
        self.controller.submit_2fa_password(self._login_account_id, password)

    def _code_requested(self, account_id: int):
        self._login_account_id = account_id
        if self._cancel_requested:
            self._begin_cancel(account_id)
            return
        self.btn_send_login_code.setEnabled(True)
        self.btn_send_login_code.setText("Send Login Code")
        self.btn_verify_login_code.setEnabled(True)
        self.btn_resend_login_code.setEnabled(True)
        self.stack_login.setCurrentIndex(self.VERIFY)
        self._set_login_feedback("Verification code sent.", "success")

    def _password_required(self, account_id: int):
        self._login_account_id = account_id
        self.btn_verify_2fa.setEnabled(True)
        self.stack_login.setCurrentIndex(self.PASSWORD)
        self.lbl_login_error.clear()

    def _login_completed(self, account_id: int, profile):
        self._login_account_id = account_id
        self._profile = profile
        self._login_in_progress = False
        self._cancel_requested = False
        username = f"@{profile.username}" if profile and profile.username else "—"
        self.lbl_login_profile.setText(
            f"Name: {(profile.first_name or '') + ' ' + (profile.last_name or '')}\n"
            f"Username: {username}\nTelegram ID: {profile.telegram_user_id}\n"
            f"Premium: {'Yes' if profile.is_premium else 'No'}\nSession: Saved securely"
        )
        self.lbl_login_error.clear()
        self._countdown.stop()
        self.stack_login.setCurrentIndex(self.COMPLETE)

    def _login_failed(self, account_id: int, message: str):
        if account_id and self._login_account_id and account_id != self._login_account_id:
            return
        self._login_in_progress = False
        if self._cancelling:
            # Cancellation raced with a failure; the temporary account is gone.
            self._finish_cancel()
            return
        self._set_login_feedback(message, "danger")
        self.btn_send_login_code.setEnabled(True)
        self.btn_send_login_code.setText("Send Login Code")
        self.btn_verify_login_code.setEnabled(True)
        self.btn_resend_login_code.setEnabled(True)
        self.btn_verify_2fa.setEnabled(True)

    def _qr_ready(self, account_id: int, info):
        self._login_account_id = account_id
        if self._cancel_requested:
            self._begin_cancel(account_id)
            return
        self.lbl_qr_login_image.setPixmap(render_qr_pixmap(info.url))
        self.lbl_qr_login_status.setText("Waiting for confirmation…")
        try:
            self._qr_expires = datetime.fromisoformat(info.expires_at.replace("Z", "+00:00"))
        except Exception:
            self._qr_expires = None
        self._countdown.start()
        self._update_qr_countdown()

    def _qr_expired(self, account_id: int):
        if account_id != self._login_account_id:
            return
        self._countdown.stop()
        self.lbl_qr_login_status.setText("QR code expired. Generate a new QR code.")
        self.lbl_qr_login_expiry.setText("Expired")
        self.lbl_qr_login_image.clear()

    def _update_qr_countdown(self):
        if not self._qr_expires:
            self.lbl_qr_login_expiry.setText("Expires soon")
            return
        now = datetime.now(timezone.utc)
        expires = self._qr_expires if self._qr_expires.tzinfo else self._qr_expires.replace(tzinfo=timezone.utc)
        seconds = max(0, int((expires - now).total_seconds()))
        self.lbl_qr_login_expiry.setText(f"Expires in: {seconds // 60:02d}:{seconds % 60:02d}")
        if seconds <= 0:
            self._countdown.stop()

    def _state_changed(self, account_id: int, state: str):
        if account_id and not self._login_account_id:
            self._login_account_id = account_id
        if self._cancel_requested and account_id and not self._cancelling:
            self._begin_cancel(account_id)
            return
        if state in {"CONNECTING", "VERIFYING_CODE", "VERIFYING_PASSWORD", "QR_GENERATING"}:
            self._set_login_feedback(state.replace("_", " ").title() + "…", "info")

    def _login_cancelled(self, account_id: int):
        if self._cancelling:
            self._finish_cancel()

    def _show_cancelling(self):
        self._cancelling = True
        self._set_login_feedback("Cancelling login…", "warning")
        for button in self.findChildren(QPushButton):
            button.setEnabled(False)

    def _begin_cancel(self, account_id: int):
        if self._cancelling:
            return
        self._show_cancelling()
        if self.controller:
            self.controller.cancel_login(account_id)
        # Safety net: never leave the user trapped in a stuck cancellation.
        self._cancel_timeout = QTimer(self)
        self._cancel_timeout.setSingleShot(True)
        self._cancel_timeout.setInterval(8000)
        self._cancel_timeout.timeout.connect(self._finish_cancel)
        self._cancel_timeout.start()

    def _finish_cancel(self):
        if self._cancel_timeout is not None:
            self._cancel_timeout.stop()
            self._cancel_timeout = None
        self._cancelling = False
        self._cancel_requested = False
        self._login_in_progress = False
        super().reject()

    def reject(self):
        self._countdown.stop()
        if self.account is not None:
            super().reject()
            return
        if self._cancelling:
            return
        if self._login_account_id:
            self._begin_cancel(self._login_account_id)
        elif self._login_in_progress:
            # The worker has not created the temporary account yet.  Wait for
            # the account id to arrive, then cancel it immediately.
            self._cancel_requested = True
            self._show_cancelling()
            self._cancel_timeout = QTimer(self)
            self._cancel_timeout.setSingleShot(True)
            self._cancel_timeout.setInterval(8000)
            self._cancel_timeout.timeout.connect(self._finish_cancel)
            self._cancel_timeout.start()
        else:
            super().reject()

# Add compatibility attributes for older PySide6 versions
if not hasattr(AddAccountDialog, 'Accepted'):
    AddAccountDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AddAccountDialog, 'Rejected'):
    AddAccountDialog.Rejected = QDialog.DialogCode.Rejected
