from __future__ import annotations

from dataclasses import dataclass, field


ELIGIBILITY_NOT_APPROVED = "ELIGIBILITY_NOT_APPROVED"
CONSENT_NOT_APPROVED = "CONSENT_NOT_APPROVED"
BLACKLISTED = "BLACKLISTED"
DO_NOT_CONTACT = "DO_NOT_CONTACT"
DELETED = "DELETED"
BOT = "BOT"
ALREADY_MEMBER = "ALREADY_MEMBER"
TARGET_STATUS_UNKNOWN = "TARGET_STATUS_UNKNOWN"
TARGET_STATUS_BLOCKED = "TARGET_STATUS_BLOCKED"


@dataclass(frozen=True)
class MemberInvitationEligibility:
    """Deterministic local policy result for one selected Member Pool record.

    The policy is intentionally conservative.  It only authorizes a direct
    invitation when the application has affirmative local eligibility and
    consent plus a verified NOT_MEMBER target state.  Account/target Telegram
    permissions are evaluated separately by InvitationPreflightService.
    """

    member_id: int
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    target_state: str = "UNKNOWN"

    @property
    def primary_reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None


class InvitationEligibilityPolicy:
    """Single source of truth for direct-member invitation eligibility."""

    MEMBER_STATES = {"MEMBER", "ALREADY_MEMBER", "JOINED"}
    VERIFIED_NOT_MEMBER = {"NOT_MEMBER"}

    def evaluate(self, member, target_state: str, *, blacklisted: bool = False, do_not_contact: bool = False) -> MemberInvitationEligibility:
        state = str(target_state or "UNKNOWN").upper()
        reasons: list[str] = []

        if blacklisted:
            reasons.append(BLACKLISTED)
        if do_not_contact or str(getattr(member, "eligibility_status", "UNKNOWN") or "UNKNOWN").upper() == "DO_NOT_CONTACT":
            reasons.append(DO_NOT_CONTACT)
        if bool(getattr(member, "is_deleted", 0)):
            reasons.append(DELETED)
        if bool(getattr(member, "is_bot", 0)):
            reasons.append(BOT)

        eligibility = str(getattr(member, "eligibility_status", "UNKNOWN") or "UNKNOWN").upper()
        if eligibility != "ELIGIBLE" and eligibility != "DO_NOT_CONTACT":
            reasons.append(ELIGIBILITY_NOT_APPROVED)

        consent = str(getattr(member, "consent_status", "UNKNOWN") or "UNKNOWN").upper()
        if consent != "APPROVED":
            reasons.append(CONSENT_NOT_APPROVED)

        if state in self.MEMBER_STATES:
            reasons.append(ALREADY_MEMBER)
        elif state == "UNKNOWN":
            reasons.append(TARGET_STATUS_UNKNOWN)
        elif state not in self.VERIFIED_NOT_MEMBER:
            reasons.append(TARGET_STATUS_BLOCKED)

        # Preserve deterministic order while removing duplicates.
        unique: list[str] = []
        for reason in reasons:
            if reason not in unique:
                unique.append(reason)
        return MemberInvitationEligibility(
            member_id=int(getattr(member, "id", 0) or 0),
            allowed=not unique,
            reasons=unique,
            target_state=state,
        )

    @staticmethod
    def human_reason(reason: str) -> str:
        return {
            ELIGIBILITY_NOT_APPROVED: "Eligibility is not approved.",
            CONSENT_NOT_APPROVED: "Consent is not approved.",
            BLACKLISTED: "Member is blacklisted.",
            DO_NOT_CONTACT: "Member is marked Do Not Contact.",
            DELETED: "Telegram account is deleted/deactivated.",
            BOT: "Bots are excluded from direct invitation.",
            ALREADY_MEMBER: "Member is already in the target.",
            TARGET_STATUS_UNKNOWN: "Target membership has not been verified.",
            TARGET_STATUS_BLOCKED: "Target membership state is not eligible for direct invitation.",
        }.get(str(reason), str(reason).replace("_", " ").title())
