from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from math import ceil
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.utils.formatters import utc_now_iso


BLOCKING_STATES = {"COOLDOWN", "RECOVERING", "RESTRICTED", "DISABLED"}
BLOCKING_HEALTH = {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}
RISK_CODES = {"FLOOD_WAIT", "PEER_FLOOD", "SPAM_LIMITED", "ACCOUNT_RESTRICTED", "USER_RESTRICTED"}


@dataclass(frozen=True)
class AccountSafetyDecision:
    account_id: int
    operation: str
    allowed: bool
    code: str
    message: str
    state: str
    smart_mode: bool
    daily_limit: int
    used_today: int
    remaining_today: int
    requested: int = 1
    wait_seconds: int = 0
    next_available_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccountSafetyService:
    """Conservative local account quotas and recovery holds.

    Limits are hard ceilings for the selected account.  The service never
    chooses a fallback account and never clears a Telegram restriction.
    """

    DEFAULTS = {
        "smart_mode": 1,
        "safety_state": "NORMAL",
        "invite_daily_limit": 20,
        "post_daily_limit": 30,
        "invite_spacing_seconds": 60,
        "post_spacing_seconds": 30,
    }
    VALID_STATES = {"NORMAL", "WATCH", "COOLDOWN", "RECOVERING", "RESTRICTED", "DISABLED"}

    def __init__(self, database, timezone_name: str = "Asia/Phnom_Penh") -> None:
        self.db = database
        try:
            self.timezone = ZoneInfo(str(timezone_name or "Asia/Phnom_Penh"))
        except ZoneInfoNotFoundError:
            self.timezone = timezone.utc

    @staticmethod
    def _operation(value: str) -> str:
        operation = str(value or "").strip().upper()
        if operation not in {"INVITE", "POST"}:
            raise ValueError("Safety operation must be INVITE or POST.")
        return operation

    def _local_now(self, at: datetime | None = None) -> datetime:
        value = at or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.timezone)

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def _ensure_profile(self, account_id: int) -> dict[str, Any]:
        account_id = int(account_id)
        row = self.db.fetch_one("SELECT id FROM telegram_accounts WHERE id=?", (account_id,))
        if not row:
            raise ValueError("Account not found.")
        now = utc_now_iso()
        self.db.execute(
            """INSERT OR IGNORE INTO account_safety_profiles(
                account_id, smart_mode, safety_state, invite_daily_limit, post_daily_limit,
                invite_spacing_seconds, post_spacing_seconds, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (account_id, 1, "NORMAL", 20, 30, 60, 30, now, now),
        )
        profile = self.db.fetch_one("SELECT * FROM account_safety_profiles WHERE account_id=?", (account_id,))
        return dict(profile or {})

    def _refresh_elapsed_state(self, profile: dict[str, Any], now: datetime) -> dict[str, Any]:
        state = str(profile.get("safety_state") or "NORMAL").upper()
        until = self._parse(profile.get("cooldown_until"))
        if state in {"COOLDOWN", "RECOVERING"} and until and until <= now.astimezone(timezone.utc):
            self.db.execute(
                "UPDATE account_safety_profiles SET safety_state='WATCH',cooldown_until=NULL,recovery_reason=?,updated_at=? WHERE account_id=?",
                ("Recovery window elapsed; account remains in Watch until successful checks confirm stability.", utc_now_iso(), int(profile["account_id"])),
            )
            profile = self._ensure_profile(int(profile["account_id"]))
        return profile

    def _usage(self, account_id: int, day: str) -> dict[str, Any]:
        row = self.db.fetch_one(
            "SELECT * FROM account_operation_usage WHERE account_id=? AND operation_date=?",
            (int(account_id), str(day)),
        )
        return dict(row or {})

    def preview(
        self,
        account_id: int,
        operation: str,
        *,
        requested: int = 1,
        at: datetime | None = None,
        enforce_interval: bool = False,
    ) -> AccountSafetyDecision:
        operation = self._operation(operation)
        requested = max(1, int(requested))
        now = self._local_now(at)
        profile = self._refresh_elapsed_state(self._ensure_profile(account_id), now)
        usage = self._usage(account_id, now.date().isoformat())
        state = str(profile.get("safety_state") or "NORMAL").upper()
        smart_mode = bool(int(profile.get("smart_mode", 1) or 0))
        prefix = "invite" if operation == "INVITE" else "post"
        configured_limit = max(0, int(profile.get(f"{prefix}_daily_limit", 0) or 0))
        effective_limit = ceil(configured_limit / 2) if state == "WATCH" and configured_limit else configured_limit
        used = max(0, int(usage.get(f"{prefix}_attempts", 0) or 0))
        remaining = max(0, effective_limit - used) if smart_mode else 2_147_483_647
        until = self._parse(profile.get("cooldown_until"))
        until_utc = until.astimezone(timezone.utc) if until else None
        wait_seconds = max(0, int((until_utc - now.astimezone(timezone.utc)).total_seconds())) if until_utc else 0

        account_row = self.db.fetch_one(
            "SELECT is_enabled,enabled_for_operations,health_status,authorization_status FROM telegram_accounts WHERE id=?",
            (int(account_id),),
        )
        account = dict(account_row or {})
        health = str(account.get("health_status") or "UNKNOWN").upper() if account else "DISABLED"
        if not account or not int(account["is_enabled"] or 0) or not int(account["enabled_for_operations"] or 0):
            return AccountSafetyDecision(int(account_id), operation, False, "ACCOUNT_DISABLED", "Account is disabled for new operations.", "DISABLED", smart_mode, effective_limit, used, remaining, requested)
        if health in BLOCKING_HEALTH:
            return AccountSafetyDecision(int(account_id), operation, False, "ACCOUNT_HEALTH_BLOCKED", f"Account health is {health.replace('_', ' ').title()}.", state, smart_mode, effective_limit, used, remaining, requested, wait_seconds, profile.get("cooldown_until"))
        if state in BLOCKING_STATES or (until_utc and until_utc > now.astimezone(timezone.utc)):
            reason = str(profile.get("recovery_reason") or "Account is held by the safety policy.")
            return AccountSafetyDecision(int(account_id), operation, False, f"SAFETY_{state}", reason, state, smart_mode, effective_limit, used, remaining, requested, wait_seconds, profile.get("cooldown_until"))
        if smart_mode and (effective_limit <= 0 or requested > remaining):
            next_day = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=self.timezone).astimezone(timezone.utc)
            return AccountSafetyDecision(
                int(account_id), operation, False, "DAILY_LIMIT",
                f"{operation.title()} daily limit reached ({used}/{effective_limit}).",
                state, smart_mode, effective_limit, used, remaining, requested,
                max(0, int((next_day - now.astimezone(timezone.utc)).total_seconds())), next_day.isoformat(timespec="seconds"),
            )
        if smart_mode and enforce_interval:
            last = self._parse(usage.get(f"last_{prefix}_at"))
            spacing = max(0, int(profile.get(f"{prefix}_spacing_seconds", 0) or 0))
            if last and spacing:
                ready_at = last.astimezone(timezone.utc) + timedelta(seconds=spacing)
                if ready_at > now.astimezone(timezone.utc):
                    seconds = max(1, int(ceil((ready_at - now.astimezone(timezone.utc)).total_seconds())))
                    return AccountSafetyDecision(
                        int(account_id), operation, False, "MIN_INTERVAL",
                        f"Smart spacing is active. Wait {seconds} second(s) before the next {operation.lower()} operation.",
                        state, smart_mode, effective_limit, used, remaining, requested, seconds, ready_at.isoformat(timespec="seconds"),
                    )
        return AccountSafetyDecision(int(account_id), operation, True, "READY", "Account is within its safety limits.", state, smart_mode, effective_limit, used, remaining, requested)

    def reserve(self, account_id: int, operation: str, *, at: datetime | None = None) -> AccountSafetyDecision:
        operation = self._operation(operation)
        now = self._local_now(at)
        with self.db.transaction():
            decision = self.preview(account_id, operation, at=now, enforce_interval=True)
            if not decision.allowed:
                return decision
            prefix = "invite" if operation == "INVITE" else "post"
            day = now.date().isoformat()
            stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
            self.db.execute(
                """INSERT INTO account_operation_usage(account_id,operation_date,updated_at)
                   VALUES(?,?,?) ON CONFLICT(account_id,operation_date) DO NOTHING""",
                (int(account_id), day, stamp),
            )
            self.db.execute(
                f"UPDATE account_operation_usage SET {prefix}_attempts={prefix}_attempts+1,last_{prefix}_at=?,updated_at=? WHERE account_id=? AND operation_date=?",
                (stamp, stamp, int(account_id), day),
            )
        return AccountSafetyDecision(
            decision.account_id, decision.operation, True, "READY", decision.message,
            decision.state, decision.smart_mode, decision.daily_limit,
            decision.used_today + 1, max(0, decision.remaining_today - 1), 1,
        )

    def record_success(self, account_id: int, operation: str, *, at: datetime | None = None) -> None:
        operation = self._operation(operation)
        now = self._local_now(at); day = now.date().isoformat(); stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        prefix = "invite" if operation == "INVITE" else "post"
        with self.db.transaction():
            self._ensure_profile(account_id)
            self.db.execute(
                "INSERT INTO account_operation_usage(account_id,operation_date,updated_at) VALUES(?,?,?) ON CONFLICT(account_id,operation_date) DO NOTHING",
                (int(account_id), day, stamp),
            )
            self.db.execute(
                f"UPDATE account_operation_usage SET {prefix}_successes={prefix}_successes+1,updated_at=? WHERE account_id=? AND operation_date=?",
                (stamp, int(account_id), day),
            )
            profile = self._ensure_profile(account_id)
            streak = int(profile.get("success_streak", 0) or 0) + 1
            state = "NORMAL" if str(profile.get("safety_state") or "NORMAL").upper() == "WATCH" and streak >= 3 else str(profile.get("safety_state") or "NORMAL").upper()
            self.db.execute(
                "UPDATE account_safety_profiles SET safety_state=?,consecutive_failures=0,success_streak=?,recovery_reason=CASE WHEN ?='NORMAL' THEN NULL ELSE recovery_reason END,updated_at=? WHERE account_id=?",
                (state, streak, state, stamp, int(account_id)),
            )

    def record_failure(
        self,
        account_id: int,
        operation: str,
        code: str | None,
        message: str | None = None,
        *,
        wait_seconds: int | None = None,
        at: datetime | None = None,
    ) -> None:
        self._operation(operation)
        now = self._local_now(at); stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds"); day = now.date().isoformat()
        code = str(code or "UNKNOWN").upper()
        with self.db.transaction():
            profile = self._ensure_profile(account_id)
            self.db.execute(
                "INSERT INTO account_operation_usage(account_id,operation_date,updated_at) VALUES(?,?,?) ON CONFLICT(account_id,operation_date) DO NOTHING",
                (int(account_id), day, stamp),
            )
            self.db.execute(
                "UPDATE account_operation_usage SET failure_count=failure_count+1,updated_at=? WHERE account_id=? AND operation_date=?",
                (stamp, int(account_id), day),
            )
            if code not in RISK_CODES:
                return
            failures = int(profile.get("consecutive_failures", 0) or 0) + 1
            state = "WATCH" if failures >= 3 else str(profile.get("safety_state") or "NORMAL").upper()
            until = None
            if code == "FLOOD_WAIT":
                state = "COOLDOWN"
                seconds = max(1, int(wait_seconds or 86400))
                until = (now.astimezone(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")
            elif code in {"PEER_FLOOD", "SPAM_LIMITED", "ACCOUNT_RESTRICTED", "USER_RESTRICTED"}:
                state = "RECOVERING"
                until = (now.astimezone(timezone.utc) + timedelta(hours=72)).isoformat(timespec="seconds")
            self.db.execute(
                "UPDATE account_safety_profiles SET safety_state=?,cooldown_until=?,recovery_reason=?,consecutive_failures=?,success_streak=0,updated_at=? WHERE account_id=?",
                (state, until, message or code.replace("_", " ").title(), failures, stamp, int(account_id)),
            )

    def get_snapshot(self, account_id: int, *, at: datetime | None = None) -> dict[str, Any]:
        invite = self.preview(account_id, "INVITE", at=at, enforce_interval=False)
        post = self.preview(account_id, "POST", at=at, enforce_interval=False)
        profile = self._ensure_profile(account_id)
        return {
            "account_id": int(account_id),
            "smart_mode": bool(int(profile.get("smart_mode", 1) or 0)),
            "state": invite.state,
            "cooldown_until": profile.get("cooldown_until"),
            "reason": profile.get("recovery_reason"),
            "invite_limit": invite.daily_limit,
            "invite_used": invite.used_today,
            "invite_remaining": invite.remaining_today,
            "invite_allowed": invite.allowed,
            "post_limit": post.daily_limit,
            "post_used": post.used_today,
            "post_remaining": post.remaining_today,
            "post_allowed": post.allowed,
            "invite_spacing_seconds": int(profile.get("invite_spacing_seconds", 0) or 0),
            "post_spacing_seconds": int(profile.get("post_spacing_seconds", 0) or 0),
            "next_available_at": invite.next_available_at or post.next_available_at or profile.get("cooldown_until"),
        }

    def update_profiles(self, account_ids: list[int], values: dict[str, Any]) -> int:
        ids = sorted({int(value) for value in account_ids if int(value) > 0})
        if not ids:
            return 0
        allowed = {
            "smart_mode", "safety_state", "invite_daily_limit", "post_daily_limit",
            "invite_spacing_seconds", "post_spacing_seconds", "cooldown_until", "recovery_reason",
        }
        payload = {key: values[key] for key in allowed if key in values}
        if "safety_state" in payload:
            payload["safety_state"] = str(payload["safety_state"] or "NORMAL").upper()
            if payload["safety_state"] not in self.VALID_STATES:
                raise ValueError("Invalid account safety state.")
        if "smart_mode" in payload:
            payload["smart_mode"] = int(bool(payload["smart_mode"]))
        ranges = {
            "invite_daily_limit": (0, 20), "post_daily_limit": (0, 100),
            "invite_spacing_seconds": (0, 3600), "post_spacing_seconds": (0, 3600),
        }
        for key, (minimum, maximum) in ranges.items():
            if key in payload:
                payload[key] = int(payload[key])
                if not minimum <= payload[key] <= maximum:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be between {minimum} and {maximum}.")
        state = str(payload.get("safety_state") or "").upper()
        if state in {"NORMAL", "WATCH"}:
            payload["cooldown_until"] = None
            if state == "NORMAL":
                payload.setdefault("recovery_reason", None)
        payload["updated_at"] = utc_now_iso()
        with self.db.transaction():
            for account_id in ids:
                self._ensure_profile(account_id)
                names = tuple(payload.keys())
                self.db.execute(
                    f"UPDATE account_safety_profiles SET {', '.join(f'{name}=?' for name in names)} WHERE account_id=?",
                    (*[payload[name] for name in names], account_id),
                )
        return len(ids)

    def summary(self, *, at: datetime | None = None) -> dict[str, int]:
        now = self._local_now(at); day = now.date().isoformat()
        rows = self.db.fetch_all("SELECT safety_state,COUNT(*) count FROM account_safety_profiles GROUP BY safety_state")
        data = {str(row["safety_state"] or "NORMAL").lower(): int(row["count"] or 0) for row in rows}
        limited = self.db.fetch_one(
            """SELECT COUNT(*) count FROM account_safety_profiles p
               LEFT JOIN account_operation_usage u ON u.account_id=p.account_id AND u.operation_date=?
               WHERE p.smart_mode=1 AND (
                 COALESCE(u.invite_attempts,0) >= CASE WHEN p.safety_state='WATCH' THEN (p.invite_daily_limit+1)/2 ELSE p.invite_daily_limit END
                 OR COALESCE(u.post_attempts,0) >= CASE WHEN p.safety_state='WATCH' THEN (p.post_daily_limit+1)/2 ELSE p.post_daily_limit END
               )""",
            (day,),
        )
        data["daily_limited"] = int(limited["count"] if limited else 0)
        return data
