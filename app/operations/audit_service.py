from __future__ import annotations

import logging


_LOG = logging.getLogger(__name__)


class AuditService:
    """Safe local operator audit trail. It records identifiers/actions, not credentials."""

    def __init__(self, repository, audit_security, logger=None) -> None:
        self.repository = repository; self.security = audit_security; self.logger = logger

    def record(self, action: str, *, resource_type: str | None = None, resource_id=None, description: str = "", before=None, after=None):
        event = self.repository.add(
            action, resource_type=resource_type, resource_id=resource_id, description=description,
            before=self.security.sanitize(before) if before is not None else None,
            after=self.security.sanitize(after) if after is not None else None,
        )
        if self.logger:
            self.logger.info("AUDIT", description or action.replace("_", " ").title(), important=True, action=action)
        return event

    def record_safely(self, action: str, **kwargs):
        """Best-effort UI audit hook.

        The business operation has already committed when a controller signal
        reaches this service.  A damaged/locked audit table must therefore not
        turn a successful member update into an unhandled Qt exception.
        """
        try:
            return self.record(action, **kwargs)
        except Exception as exc:
            try:
                if self.logger:
                    self.logger.warning(
                        "AUDIT",
                        f"Could not persist the {action} audit event: {exc}",
                        action="AUDIT_WRITE_SKIPPED",
                    )
                else:
                    _LOG.warning("Could not persist audit event %s: %s", action, exc)
            except Exception:
                _LOG.exception("Audit fallback logging failed for %s", action)
            return None

    def wire_controllers(self, *, account=None, group=None, member=None, campaign=None, scheduler=None, settings=None) -> None:
        if account:
            account.accountCreated.connect(lambda item: self.record_safely("ACCOUNT_ADDED", resource_type="ACCOUNT", resource_id=getattr(item, "id", None), description="Account added to the local tool."))
            account.accountRemoved.connect(lambda rid: self.record_safely("ACCOUNT_REMOVED", resource_type="ACCOUNT", resource_id=rid, description="Account removed or disabled from the local tool."))
            account.accountUpdated.connect(lambda item: self.record_safely("ACCOUNT_UPDATED", resource_type="ACCOUNT", resource_id=getattr(item, "id", None), description="Account local metadata updated."))
        if group:
            signal = getattr(group, "groupCreated", None)
            if signal: signal.connect(lambda item: self.record_safely("GROUP_ADDED", resource_type="GROUP", resource_id=getattr(item, "id", None), description="Group added to the local tool."))
            signal = getattr(group, "groupRemoved", None)
            if signal: signal.connect(lambda rid: self.record_safely("GROUP_REMOVED", resource_type="GROUP", resource_id=rid, description="Group removed from the local tool."))
        if member:
            member.memberBlacklistChanged.connect(lambda rid: self.record_safely("MEMBER_EXCLUSION_CHANGED", resource_type="MEMBER", resource_id=rid, description="Member blacklist/Do Not Contact state changed."))
            member.memberEligibilityChanged.connect(lambda rid: self.record_safely("MEMBER_ELIGIBILITY_CHANGED", resource_type="MEMBER", resource_id=rid, description="Member eligibility/consent state changed."))
            batch_signal = getattr(member, "memberEligibilityBatchChanged", None)
            if batch_signal:
                batch_signal.connect(lambda ids: self.record_safely(
                    "MEMBER_ELIGIBILITY_BATCH_CHANGED", resource_type="MEMBER_BATCH",
                    resource_id=",".join(str(x) for x in list(ids or [])[:100]),
                    description=f"Eligibility/consent state changed for {len(list(ids or []))} member(s).",
                ))
        if campaign:
            signal = getattr(campaign, "campaign_created", None)
            if signal: signal.connect(lambda item: self.record_safely("CAMPAIGN_CREATED", resource_type="CAMPAIGN", resource_id=getattr(item, "id", None), description="Campaign created."))
            signal = getattr(campaign, "campaign_updated", None)
            if signal: signal.connect(lambda item: self.record_safely("CAMPAIGN_UPDATED", resource_type="CAMPAIGN", resource_id=getattr(item, "id", None), description="Campaign updated."))
            signal = getattr(campaign, "campaignCompleted", None)
            if signal: signal.connect(lambda rid: self.record_safely("CAMPAIGN_COMPLETED", resource_type="CAMPAIGN", resource_id=rid, description="Campaign completed."))
        if scheduler:
            signal = getattr(scheduler, "schedule_changed", None)
            if signal: signal.connect(lambda: self.record_safely("SCHEDULE_CHANGED", resource_type="SCHEDULE", description="Campaign schedule configuration changed."))
        if settings:
            settings.settingsChanged.connect(lambda: self.record_safely("SETTINGS_CHANGED", resource_type="SETTINGS", resource_id="application", description="Application settings changed."))
