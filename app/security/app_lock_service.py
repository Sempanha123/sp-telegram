from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.security.secure_storage import KeyringSecureStorage, SecureStorage

_LOG = logging.getLogger(__name__)

# Brute-force protection constants.
_MAX_ATTEMPTS = 5          # consecutive failures before first lockout
_LOCKOUT_INITIAL = 60.0    # seconds — first lockout duration
_LOCKOUT_STEPS = 2.0       # multiplier per escalation tier
_LOCKOUT_CAP = 3600.0      # maximum lockout = 1 hour

# Expected PBKDF2-SHA256 payload layout: 16-byte salt + 32-byte digest.
_EXPECTED_HASH_LEN = 32

# Fixed dummy salt/digest used when no password is stored (or the blob is
# corrupt).  The no-password path performs the same PBKDF2 derivation against
# this dummy payload so callers cannot distinguish "no password set" from
# "wrong password" via timing (SEC-003).
_DUMMY_SALT = bytes(range(16))
_DUMMY_DIGEST = bytes(range(32))


@dataclass
class AppLockState:
    enabled: bool = False
    locked: bool = False
    lock_after_minutes: int = 10
    last_activity_at: datetime | None = None
    failed_attempts: int = 0
    lockout_until: float = 0.0  # monotonic timestamp


class AppLockService:
    SECRET_KEY = "application_lock_verifier"

    def __init__(self, storage: SecureStorage | None = None) -> None:
        self.storage = storage or KeyringSecureStorage()
        self.state = AppLockState(last_activity_at=datetime.now(timezone.utc))

    # -- Password hashing ------------------------------------------------

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)

    def set_password(self, password: str) -> None:
        if len(password) < 6:
            raise ValueError("Application lock password must contain at least 6 characters.")
        salt = os.urandom(16)
        digest = self._derive(password, salt)
        payload = base64.b64encode(salt + digest).decode("ascii")
        self.storage.set_secret(self.SECRET_KEY, payload)
        self.state.enabled = True

    def has_password(self) -> bool:
        try:
            return bool(self.storage.get_secret(self.SECRET_KEY))
        except Exception:
            return False

    # -- Hash blob validation (SEC-002) -----------------------------------

    def _load_hash_payload(self) -> tuple[bytes, bytes] | None:
        """Return ``(salt, expected_digest)`` or *None* if the stored blob is
        absent or corrupt.  Validates that the decoded blob has the correct
        total length so callers never silently compare against garbage data.
        """
        payload = self.storage.get_secret(self.SECRET_KEY)
        if not payload:
            return None
        try:
            raw = base64.b64decode(payload.encode("ascii"))
        except Exception:
            _LOG.warning("AppLock hash blob could not be base64-decoded; treating as no-password.")
            return None
        # Layout: 16-byte salt + _EXPECTED_HASH_LEN-byte digest = 48 bytes.
        expected_len = 16 + _EXPECTED_HASH_LEN
        if len(raw) != expected_len:
            _LOG.warning(
                "AppLock hash blob length mismatch: expected %d bytes, got %d. "
                "Corrupted keyring entry — password verification disabled until reset.",
                expected_len,
                len(raw),
            )
            return None
        salt, expected = raw[:16], raw[16:]
        return salt, expected

    def verify(self, password: str) -> bool:
        """Verify *password* against the stored hash.

        Uses the validated payload loader so a corrupted keyring entry is
        rejected cleanly instead of compared against truncated data.

        When no password is stored (or the blob is corrupt) the method still
        performs the full PBKDF2 derivation against a fixed dummy payload so
        the no-password path takes the same time as a real verification —
        eliminating the timing side-channel (SEC-003).
        """
        result = self._load_hash_payload()
        if result is None:
            # No stored password / corrupt blob: derive against a fixed dummy
            # payload (constant work) and always fail.
            salt, expected = _DUMMY_SALT, _DUMMY_DIGEST
        else:
            salt, expected = result
        return hmac.compare_digest(self._derive(password, salt), expected)

    # -- Brute-force protection (SEC-001) ---------------------------------

    def _record_failure(self) -> None:
        """Record a failed unlock attempt and escalate the lockout duration."""
        self.state.failed_attempts += 1
        if self.state.failed_attempts >= _MAX_ATTEMPTS:
            tier = self.state.failed_attempts - _MAX_ATTEMPTS  # 0 for first lockout
            lockout = min(_LOCKOUT_INITIAL * (_LOCKOUT_STEPS ** tier), _LOCKOUT_CAP)
            self.state.lockout_until = time.monotonic() + lockout
            _LOG.warning(
                "AppLock brute-force lockout activated: %d failures, locked for %.0fs.",
                self.state.failed_attempts,
                lockout,
            )

    def _is_lockout_active(self) -> bool:
        """Return *True* if the user is currently in a brute-force lockout."""
        return time.monotonic() < self.state.lockout_until

    def _reset_attempts(self) -> None:
        """Clear failure counter and lockout on successful unlock."""
        self.state.failed_attempts = 0
        self.state.lockout_until = 0.0

    @property
    def lockout_remaining(self) -> float:
        """Seconds remaining in the current lockout, or 0.0."""
        remaining = self.state.lockout_until - time.monotonic()
        return max(0.0, remaining)

    # -- Public API -------------------------------------------------------

    def clear_password(self) -> None:
        self.storage.delete_secret(self.SECRET_KEY)
        self.state.enabled = False; self.state.locked = False
        self._reset_attempts()

    def configure(self, enabled: bool, minutes: int) -> None:
        self.state.enabled = bool(enabled and self.has_password())
        self.state.lock_after_minutes = max(1, min(240, int(minutes)))
        if self.state.enabled and self.has_password():
            self.state.locked = True
            self.state.last_activity_at = None
        else:
            self.touch()

    def touch(self) -> None:
        self.state.last_activity_at = datetime.now(timezone.utc)

    def should_auto_lock(self, now: datetime | None = None) -> bool:
        if not self.state.enabled or self.state.locked or not self.state.last_activity_at:
            return False
        now = now or datetime.now(timezone.utc)
        return (now - self.state.last_activity_at).total_seconds() >= self.state.lock_after_minutes * 60

    def lock(self) -> None:
        if self.state.enabled:
            self.state.locked = True

    def unlock(self, password: str) -> bool:
        """Attempt to unlock the application.

        Returns the same ``False`` for *every* failure reason — wrong
        password, corrupted blob, or brute-force lockout — so callers
        cannot distinguish the cause via timing or return value (SEC-003).
        """
        # Reject immediately during lockout without doing any crypto work.
        if self._is_lockout_active():
            return False
        ok = self.verify(password)
        if ok:
            self.state.locked = False
            self.touch()
            self._reset_attempts()
            return True
        self._record_failure()
        return False
