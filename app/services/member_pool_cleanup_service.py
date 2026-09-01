from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CleanupResult:
    removed_members: int = 0
    removed_sources: int = 0
    preserved_protected: int = 0


class MemberPoolCleanupService:
    """Transactional local Member Pool cleanup.

    Nothing here modifies Telegram.  Large bulk actions log one aggregate audit
    event instead of individual Telegram identifiers.
    """

    def __init__(self, member_repository, audit_repository=None):
        self.members = member_repository
        self.db = member_repository.db
        self.audit = audit_repository

    def _audit(self, action: str, count: int, description: str, *, after=None) -> None:
        if self.audit:
            self.audit.add(action, resource_type="MEMBER_POOL", resource_id="local", description=description, after=after or {"count": int(count)})

    @staticmethod
    def _ids(values: Iterable[int]) -> list[int]:
        return sorted({int(v) for v in values if v is not None})

    def clear_selected(self, member_ids: Iterable[int]) -> CleanupResult:
        ids=self._ids(member_ids)
        if not ids:return CleanupResult()
        placeholders=",".join("?" for _ in ids)
        with self.db.transaction():
            count=int(self.db.fetch_one(f"SELECT COUNT(*) n FROM members WHERE id IN ({placeholders})",ids)["n"])
            self.db.execute(f"DELETE FROM members WHERE id IN ({placeholders})",ids)
        self._audit("MEMBER_REMOVED",count,f"Removed {count} selected member record(s) from the local Member Pool.")
        return CleanupResult(removed_members=count)

    def clear_filtered(self, **filters) -> CleanupResult:
        ids=self.members.get_filtered_ids(**filters)
        if not ids:return CleanupResult()
        # One transaction; chunk only the SQL placeholder count.
        removed=0
        with self.db.transaction():
            for start in range(0,len(ids),500):
                chunk=ids[start:start+500]; ph=",".join("?" for _ in chunk)
                removed+=int(self.db.execute(f"DELETE FROM members WHERE id IN ({ph})",chunk).rowcount)
        self._audit("MEMBER_BULK_REMOVED",removed,f"Removed {removed} filtered member record(s) from the local Member Pool.",after={"count":removed,"filters":{k:v for k,v in filters.items() if v not in {None,"",False}}})
        return CleanupResult(removed_members=removed)

    def clear_by_source(self, group_id:int, *, remove_member_if_only_source:bool=False) -> CleanupResult:
        group_id=int(group_id)
        found=int(self.db.fetch_one("SELECT COUNT(*) n FROM member_sources WHERE group_id=?",(group_id,))["n"])
        removed_members=0
        with self.db.transaction():
            if remove_member_if_only_source:
                rows=self.db.fetch_all(
                    """SELECT ms.member_id FROM member_sources ms WHERE ms.group_id=?
                       AND NOT EXISTS(SELECT 1 FROM member_sources other WHERE other.member_id=ms.member_id AND other.group_id<>?)""",
                    (group_id,group_id),
                )
                only_ids=[int(r["member_id"]) for r in rows]
            else:only_ids=[]
            self.db.execute("DELETE FROM member_sources WHERE group_id=?",(group_id,))
            if only_ids:
                for start in range(0,len(only_ids),500):
                    chunk=only_ids[start:start+500];ph=",".join("?" for _ in chunk)
                    # Preserve records that carry global safety/exclusion state.
                    removed_members+=int(self.db.execute(
                        f"DELETE FROM members WHERE id IN ({ph}) AND NOT EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=members.id)",chunk
                    ).rowcount)
        self._audit("MEMBER_SOURCE_CLEARED",found,f"Cleared {found} member-source relationship(s) for source group {group_id}.",after={"source_group_id":group_id,"relationships":found,"members_removed":removed_members})
        return CleanupResult(removed_members=removed_members,removed_sources=found)

    def orphan_count(self) -> int:
        row=self.db.fetch_one(
            """SELECT COUNT(*) n FROM members m
               WHERE NOT EXISTS(SELECT 1 FROM member_sources ms WHERE ms.member_id=m.id)
               AND NOT EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id)
               AND NOT EXISTS(SELECT 1 FROM member_target_actions a WHERE a.member_id=m.id)"""
        )
        return int(row["n"] if row else 0)

    def clear_orphaned(self) -> CleanupResult:
        with self.db.transaction():
            cursor=self.db.execute(
                """DELETE FROM members WHERE id IN (
                       SELECT m.id FROM members m
                       WHERE NOT EXISTS(SELECT 1 FROM member_sources ms WHERE ms.member_id=m.id)
                       AND NOT EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id)
                       AND NOT EXISTS(SELECT 1 FROM member_target_actions a WHERE a.member_id=m.id)
                   )"""
            )
            removed=int(cursor.rowcount)
        self._audit("MEMBER_BULK_REMOVED",removed,f"Removed {removed} orphaned local member record(s).")
        return CleanupResult(removed_members=removed)

    def clear_entire(self, *, preserve_global_exclusions:bool=True, preserve_audit_history:bool=True) -> CleanupResult:
        total=int(self.db.fetch_one("SELECT COUNT(*) n FROM members")["n"])
        with self.db.transaction():
            protections=[]
            if preserve_global_exclusions:
                protections.append("EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=members.id AND x.target_group_id IS NULL AND x.exclusion_type IN ('GLOBAL_BLACKLIST','DO_NOT_CONTACT'))")
            if preserve_audit_history:
                protections.append("EXISTS(SELECT 1 FROM member_target_actions a WHERE a.member_id=members.id)")
            if protections:
                cursor=self.db.execute("DELETE FROM members WHERE NOT ("+" OR ".join(protections)+")")
            else:
                cursor=self.db.execute("DELETE FROM members")
            removed=int(cursor.rowcount)
        preserved=max(0,total-removed)
        self._audit("MEMBER_POOL_CLEARED",removed,f"Cleared {removed} local Member Pool record(s). Telegram accounts/groups were not modified.",after={"removed":removed,"preserved_protected":preserved,"preserve_global_exclusions":bool(preserve_global_exclusions),"preserve_audit_history":bool(preserve_audit_history)})
        return CleanupResult(removed_members=removed,preserved_protected=preserved)
