from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.utils.formatters import utc_now_iso


class LoginState(str, Enum):
    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    CODE_REQUESTED = "CODE_REQUESTED"
    WAITING_CODE = "WAITING_CODE"
    VERIFYING_CODE = "VERIFYING_CODE"
    PASSWORD_REQUIRED = "PASSWORD_REQUIRED"
    VERIFYING_PASSWORD = "VERIFYING_PASSWORD"
    AUTHORIZED = "AUTHORIZED"
    FETCH_PROFILE = "FETCH_PROFILE"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class QRLoginState(str, Enum):
    QR_GENERATING = "QR_GENERATING"
    QR_WAITING = "QR_WAITING"
    QR_ACCEPTED = "QR_ACCEPTED"
    QR_EXPIRED = "QR_EXPIRED"
    QR_FAILED = "QR_FAILED"
    QR_CANCELLED = "QR_CANCELLED"


class TelegramErrorCategory(str, Enum):
    AUTH = "AUTH"
    SESSION = "SESSION"
    NETWORK = "NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    PERMISSION = "PERMISSION"
    CONFIGURATION = "CONFIGURATION"
    SERVER = "SERVER"
    MEDIA = "MEDIA"
    SCHEDULE = "SCHEDULE"
    CONTENT = "CONTENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class AccountRuntimeState:
    account_id: int
    connected: bool = False
    authorized: bool = False
    connecting: bool = False
    login_in_progress: bool = False
    last_connect_attempt: str | None = None
    last_ping_at: str | None = None
    last_runtime_error: str | None = None


@dataclass
class LoginContext:
    temporary_account_id: int
    phone: str | None
    session_path: str
    state: LoginState = LoginState.IDLE
    phone_code_hash: str | None = None
    created_at: str = ""
    temporary_account: bool = True

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now_iso()


@dataclass
class TelegramProfile:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    phone: str | None
    is_premium: bool


@dataclass
class AccountHealthResult:
    account_id: int
    connection_ok: bool
    session_exists: bool
    authorized: bool
    profile_ok: bool
    health_status: str
    error_code: str | None = None
    error_message: str | None = None
    checked_at: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = utc_now_iso()


@dataclass
class TelegramErrorResult:
    code: str
    category: TelegramErrorCategory
    message: str
    retryable: bool = False
    wait_seconds: int | None = None
    requires_login: bool = False
    requires_user_action: bool = False


@dataclass
class TelegramSessionInfo:
    authorization_hash: str
    device_model: str
    platform: str
    system_version: str
    app_name: str
    app_version: str
    location: str
    last_active_at: str | None
    created_at: str | None
    is_current: bool
    status: str = "Active"


@dataclass
class QRLoginInfo:
    account_id: int
    url: str
    expires_at: str
    state: QRLoginState = QRLoginState.QR_WAITING


@dataclass
class LoginResult:
    account_id: int
    state: LoginState
    profile: TelegramProfile | None = None
    existing_account_id: int | None = None
    message: str = ""
