from __future__ import annotations

from dataclasses import replace
import csv
from pathlib import Path

from app.database.database import DatabaseError
from app.database.repositories.account_activity_repository import AccountActivityRepository
from app.database.repositories.account_repository import AccountRepository
from app.models.entities import AccountActivity, TelegramAccount
from app.utils.helpers import json_dumps_safe


class AccountService:
    def __init__(self, repository: AccountRepository, activity_repository: AccountActivityRepository, restriction_repository=None) -> None:
        self.repository = repository
        self.activity_repository = activity_repository
        self.restriction_repository = restriction_repository
        self.license_limit_service = None

    def get_accounts(self):
        return self.repository.get_all()

    def get_account_page(self, page=1, page_size=100, search=None, health=None, status=None):
        return self.repository.get_page(page, page_size, search, health, status)

    def add_account(self, data: dict) -> TelegramAccount:
        if self.license_limit_service is not None:
            check=self.license_limit_service.can_add_account()
            if not check.allowed:raise RuntimeError(check.message or "Account plan limit reached.")
        telegram_user_id = data.get("telegram_user_id")
        try:
            telegram_user_id = int(telegram_user_id) if telegram_user_id not in (None, "") else None
        except (TypeError, ValueError) as exc:
            raise ValueError("Telegram ID must be a number.") from exc
        account = TelegramAccount(
            telegram_user_id=telegram_user_id,
            phone=(data.get("phone") or "").strip() or None,
            username=(data.get("username") or "").strip().lstrip("@") or None,
            first_name=(data.get("display_name") or data.get("first_name") or "").strip() or None,
            last_name=(data.get("last_name") or "").strip() or None,
            notes=(data.get("notes") or "").strip() or None,
            connection_status="OFFLINE",
            health_status="UNKNOWN",
        )
        try:
            with self.repository.db.transaction():
                created = self.repository.create(account)
                tags = data.get("tags") or []
                if isinstance(tags, str):
                    tags = [part.strip() for part in tags.split(",")]
                self.repository.replace_tags(created.id, list(tags))
                self.record_activity(created.id, "CREATED", "SUCCESS", "Local account configuration created.")
            return created
        except DatabaseError as exc:
            if exc.kind == "unique":
                raise ValueError("This Telegram ID already exists.") from exc
            raise

    def update_account(self, account_id: int, data: dict) -> TelegramAccount:
        account = self.repository.get_by_id(account_id)
        if not account:
            raise ValueError("Account not found.")
        authorized = str(getattr(account, "authorization_status", "")).upper() == "AUTHORIZED"
        if not authorized:
            if "telegram_user_id" in data:
                value = data.get("telegram_user_id")
                account.telegram_user_id = int(value) if value not in (None, "") else None
            account.phone = (data.get("phone", account.phone) or "").strip() or None
            account.username = (data.get("username", account.username) or "").strip().lstrip("@") or None
            account.first_name = (data.get("display_name", data.get("first_name", account.first_name)) or "").strip() or None
            account.last_name = (data.get("last_name", account.last_name) or "").strip() or None
        account.notes = (data.get("notes", account.notes) or "").strip() or None
        try:
            with self.repository.db.transaction():
                updated = self.repository.update(account)
                if "tags" in data:
                    tags = data.get("tags") or []
                    if isinstance(tags, str):
                        tags = [part.strip() for part in tags.split(",")]
                    self.repository.replace_tags(account_id, list(tags))
                self.record_activity(account_id, "UPDATED", "SUCCESS", "Local account configuration updated.")
            return updated
        except DatabaseError as exc:
            if exc.kind == "unique":
                raise ValueError("This Telegram ID already exists.") from exc
            raise

    def remove_account(self, account_id: int) -> str:
        account = self.repository.get_by_id(account_id)
        if not account:
            raise ValueError("Account not found.")
        # Pending login placeholders are transient by definition: they only exist
        # while a login wizard is open (or were left behind by an interrupted
        # login). Their history is login-attempt noise, so never block deletion.
        if self._is_pending_login(account):
            return self._force_delete_pending(account_id)
        if self.repository.has_related_history(account_id):
            self.repository.set_enabled(account_id, False)
            self.record_activity(account_id, "DISABLED", "SUCCESS", "Account disabled because related history exists.")
            return "disabled"
        self.repository.delete(account_id)
        return "deleted"

    def _is_pending_login(self, account) -> bool:
        status = str(getattr(account, "authorization_status", "") or "").upper()
        name = str(getattr(account, "first_name", "") or "")
        return status == "PENDING" or name == "Pending Telegram Login"

    def _force_delete_pending(self, account_id: int) -> str:
        """Delete a pending-login placeholder together with its transient history."""
        with self.repository.db.transaction():
            if self.restriction_repository is not None:
                self.restriction_repository.delete_for_account(account_id)
            if self.activity_repository is not None:
                self.activity_repository.delete_for_account(account_id)
            # Clear any other RESTRICT-FK rows a pending row could never
            # legitimately own, so the delete cannot be blocked by a foreign key.
            for table, column in (
                ("group_accounts", "account_id"),
                ("jobs", "account_id"),
                ("campaign_targets", "account_id"),
                ("target_invite_links", "account_id"),
            ):
                self.repository.db.execute(f"DELETE FROM {table} WHERE {column} = ?", (account_id,))
            self.repository.delete(account_id)
        return "deleted"

    def enable_account(self, account_id: int):
        return self.repository.set_enabled(account_id, True)

    def disable_account(self, account_id: int):
        changed = self.repository.set_enabled(account_id, False)
        if changed:
            self.record_activity(account_id, "DISABLED", "SUCCESS", "Account disabled locally.")
        return changed

    def search_accounts(self, query: str):
        return self.repository.search(query)

    def get_account_details(self, account_id: int):
        account = self.repository.get_by_id(account_id)
        if not account:
            return None
        return {
            "account": account,
            "tags": self.repository.get_tags(account_id),
            "activity": self.activity_repository.get_recent(account_id, 100),
        }

    def get_account_statistics(self):
        return {
            "total": self.repository.count_all(),
            "healthy": self.repository.count_by_health("HEALTHY"),
            "cooldown": self.repository.count_by_health("COOLDOWN"),
            "restricted": self.repository.count_by_health("RESTRICTED"),
            "offline": self.repository.count_by_health("OFFLINE"),
        }

    def set_health(self, account_id: int, status: str):
        changed = self.repository.update_health_status(account_id, status.upper().replace(" ", "_"))
        if changed:
            self.record_activity(account_id, "HEALTH_CHECK", "SUCCESS", f"Health set to {status} locally.")
        return changed

    def set_capabilities(self, account_id: int, **capabilities: bool):
        return self.repository.update_capabilities(account_id, **capabilities)

    def record_error(self, account_id: int, code: str | None, message: str | None):
        self.repository.update_last_error(account_id, code, message)
        self.record_activity(account_id, "ERROR", "FAILED", message or "Account error", {"code": code})

    def record_activity(self, account_id: int, action_type: str, status: str, message: str, metadata: dict | None = None):
        return self.activity_repository.create(
            AccountActivity(
                account_id=account_id,
                action_type=action_type,
                status=status,
                message=message,
                metadata_json=json_dumps_safe(metadata or {}),
            )
        )

    def get_tags(self, account_id: int):
        return self.repository.get_tags(account_id)

    def import_csv(self, path: str | Path):
        imported = updated = skipped = errors = 0
        error_rows = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for line, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    raw_id = (row.get("telegram_user_id") or "").strip()
                    telegram_id = int(raw_id) if raw_id else None
                    data = {
                        "telegram_user_id": telegram_id,
                        "display_name": row.get("display_name") or row.get("first_name") or "",
                        "username": row.get("username") or "",
                        "phone": row.get("phone") or "",
                        "notes": row.get("notes") or "",
                        "tags": row.get("tags") or "",
                    }
                    existing = self.repository.get_by_telegram_id(telegram_id) if telegram_id is not None else None
                    if existing:
                        self.update_account(existing.id, data); updated += 1
                    else:
                        self.add_account(data); imported += 1
                except ValueError as exc:
                    skipped += 1; error_rows.append({"line": line, "error": str(exc)})
                except Exception as exc:
                    errors += 1; error_rows.append({"line": line, "error": str(exc)})
        return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors, "error_rows": error_rows}


    def export_csv(self, path: str | Path):
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["telegram_user_id", "username", "phone", "display_name", "health_status", "connection_status", "is_enabled", "notes", "tags"])
            for account in self.get_accounts():
                writer.writerow([account.telegram_user_id or "", account.username or "", account.phone or "", account.first_name or "", account.health_status, account.connection_status, account.is_enabled, account.notes or "", ", ".join(self.repository.get_tags(account.id))])
        return Path(path)

    def get_restrictions(self):
        return self.restriction_repository.get_all_active() if self.restriction_repository is not None else []


    def create_login_pending_account(self, phone: str | None = None) -> TelegramAccount:
        if self.license_limit_service is not None:
            check=self.license_limit_service.can_add_account()
            if not check.allowed:raise RuntimeError(check.message or "Account plan limit reached.")
        account = TelegramAccount(
            phone=phone.strip() if phone else None,
            first_name="Pending Telegram Login",
            connection_status="CONNECTING",
            health_status="LOGIN_REQUIRED",
            authorization_status="PENDING",
        )
        return self.repository.create(account)

    def cleanup_login_pending_account(self, account_id: int) -> bool:
        account = self.repository.get_by_id(account_id)
        if not account or account.authorization_status != "PENDING":
            return False
        # Pending login history is transient by definition. Remove only the
        # pending account's restriction/activity rows so FK protections remain
        # intact for every successfully registered account.
        with self.repository.db.transaction():
            if self.restriction_repository is not None:
                self.restriction_repository.delete_for_account(account_id)
            if self.activity_repository is not None:
                self.activity_repository.delete_for_account(account_id)
            return self.repository.delete(account_id)

    def cleanup_stale_pending_accounts(self) -> int:
        """Remove any leftover 'Pending Telegram Login' rows from interrupted logins.

        A pending account is transient by definition: it only exists while a
        login wizard is open.  If the app closed mid-login (crash, forced quit)
        the row would otherwise linger forever as a fake/partial account.
        Returns the number of rows removed.
        """
        removed = 0
        for account in self.repository.get_all():
            if str(getattr(account, "authorization_status", "")).upper() == "PENDING":
                if self.cleanup_login_pending_account(int(account.id)):
                    removed += 1
        return removed

    def finalize_authenticated_account(self, account_id: int, profile, session_path: str) -> TelegramAccount:
        account = self.repository.get_by_id(account_id)
        if not account:
            raise ValueError("Pending account record no longer exists.")
        if account.telegram_user_id is not None and int(account.telegram_user_id) != int(profile.telegram_user_id):
            raise ValueError("IDENTITY_MISMATCH")
        existing = self.repository.get_by_telegram_id(int(profile.telegram_user_id))
        if existing and existing.id != account_id:
            raise ValueError(f"DUPLICATE_TELEGRAM_ACCOUNT:{existing.id}")
        now = __import__("app.utils.formatters", fromlist=["utc_now_iso"]).utc_now_iso()
        with self.repository.db.transaction():
            updated = self.repository.update_telegram_profile(account_id, profile, session_path)
            self.repository.update_fields(account_id, {
                "connection_status": "CONNECTED",
                "health_status": "HEALTHY",
                "authorization_status": "AUTHORIZED",
                "last_connected_at": now,
                "last_active_at": now,
                "last_success_at": now,
                "last_error_code": None,
                "last_error_message": None,
                "updated_at": now,
            })
            self.record_activity(account_id, "LOGIN_SUCCESS", "SUCCESS", "Telegram authentication completed successfully.")
        return self.repository.get_by_id(account_id)

    def sync_telegram_profile(self, account_id: int, profile) -> TelegramAccount:
        account = self.repository.get_by_id(account_id)
        if not account:
            raise ValueError("Account not found.")
        if account.telegram_user_id is not None and int(account.telegram_user_id) != int(profile.telegram_user_id):
            raise ValueError("The logged-in Telegram account does not match this local record.")
        with self.repository.db.transaction():
            updated = self.repository.update_telegram_profile(account_id, profile)
            self.record_activity(account_id, "PROFILE_REFRESHED", "SUCCESS", "Telegram profile metadata refreshed.")
        return updated

    def set_session_path(self, account_id: int, session_path: str) -> None:
        self.repository.set_session_path(account_id, session_path)

    def set_connection_state(
        self, account_id: int, status: str, *, authorized: bool | None = None,
        health_status: str | None = None,
    ) -> None:
        values = {"connection_status": status, "updated_at": __import__("app.utils.formatters", fromlist=["utc_now_iso"]).utc_now_iso()}
        if status == "CONNECTED":
            values["last_connected_at"] = values["updated_at"]
            values["last_success_at"] = values["updated_at"]
        if authorized is not None:
            values["authorization_status"] = "AUTHORIZED" if authorized else "LOGIN_REQUIRED"
        if health_status is not None:
            values["health_status"] = health_status
        self.repository.update_fields(account_id, values)

    def mark_logged_out(self, account_id: int) -> None:
        self.repository.update_fields(account_id, {
            "connection_status": "DISCONNECTED",
            "authorization_status": "LOGIN_REQUIRED",
            "health_status": "LOGIN_REQUIRED",
            "can_collect": 0,
            "can_invite": 0,
            "can_post": 0,
            "can_schedule": 0,
            "can_manage": 0,
        })

    def mark_login_required(self, account_id: int, message: str, code: str = "LOGIN_REQUIRED") -> None:
        self.repository.update_fields(account_id, {
            "health_status": "LOGIN_REQUIRED",
            "authorization_status": "LOGIN_REQUIRED",
            "last_error_code": code,
            "last_error_message": message,
            "last_error_at": __import__("app.utils.formatters", fromlist=["utc_now_iso"]).utc_now_iso(),
            "can_collect": 0, "can_invite": 0, "can_post": 0, "can_schedule": 0, "can_manage": 0,
        })

    def set_health_result(self, result) -> None:
        values = {
            "health_status": result.health_status,
            "last_health_check_at": result.checked_at,
            "last_error_code": result.error_code,
            "last_error_message": result.error_message,
            "last_error_at": result.checked_at if result.error_code else None,
            "authorization_status": "AUTHORIZED" if result.authorized else ("LOGIN_REQUIRED" if result.session_exists else "LOGIN_REQUIRED"),
        }
        if result.connection_ok:
            values["connection_status"] = "CONNECTED"
        elif result.health_status in {"LOGIN_REQUIRED", "SESSION_INVALID", "DISABLED"}:
            values["connection_status"] = "DISCONNECTED"
        self.repository.update_fields(result.account_id, values)
        self.record_activity(result.account_id, "HEALTH_CHECK", "SUCCESS" if result.health_status == "HEALTHY" else "WARNING", f"Telegram account health: {result.health_status}.")

    def record_confirmed_flood_wait(self, account_id: int, wait_seconds: int | None, reason: str) -> None:
        from datetime import datetime, timedelta, timezone
        from app.models.entities import AccountRestriction
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=int(wait_seconds))).isoformat(timespec="seconds") if wait_seconds else None
        with self.repository.db.transaction():
            self.repository.update_fields(account_id, {
                "health_status": "COOLDOWN",
                "restriction_type": "FLOOD_WAIT",
                "restriction_source": "TELEGRAM_CONFIRMED",
                "restriction_reason": reason,
                "restriction_started_at": now.isoformat(timespec="seconds"),
                "restriction_until": expires,
            })
            if self.restriction_repository is not None:
                self.restriction_repository.create(AccountRestriction(
                    account_id=account_id, restriction_type="FLOOD_WAIT", source="TELEGRAM_CONFIRMED",
                    confidence="CONFIRMED", error_code="FLOOD_WAIT", reason=reason,
                    started_at=now.isoformat(timespec="seconds"), expires_at=expires, is_active=1,
                ))

    def get_by_id(self, account_id: int) -> TelegramAccount | None:
        return self.repository.get_by_id(account_id)

    # TODO PHASE 3:
    # Replace manual account creation with Telegram authorization result.
