from __future__ import annotations


class GroupMonitor:
    """Monitors persisted managed-group access/permission state without enumerating members."""

    def __init__(self, group_repository, mapping_repository, alert_manager=None) -> None:
        self.groups = group_repository
        self.mappings = mapping_repository
        self.alerts = alert_manager

    def snapshot(self) -> dict:
        managed = self.groups.get_managed()
        issues = []
        for group in managed:
            primary = self.mappings.get_primary_account(group.id) if group.id else None
            if not primary:
                issues.append((group.id, "PRIMARY_ACCOUNT_UNAVAILABLE"))
                if self.alerts:
                    self.alerts.raise_alert(
                        "WARNING", "PRIMARY_ACCOUNT", f"{group.title} has no usable primary account",
                        "A managed group should have an explicitly selected primary account for later authorized operations.",
                        dedupe_key=f"group-primary:{group.id}", source_type="GROUP", source_id=group.id,
                        group_id=group.id, requires_action=True, action_type="SET_PRIMARY_ACCOUNT",
                    )
                continue
            if str(primary.access_state) in {"ACCESS_DENIED", "NOT_JOINED", "UNAVAILABLE"}:
                issues.append((group.id, "ACCESS_LOST"))
            if primary.can_post is False or primary.can_post == 0:
                issues.append((group.id, "POST_PERMISSION_REMOVED"))
        return {"managed": len(managed), "issues": issues}
