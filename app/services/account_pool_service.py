from __future__ import annotations

import csv
from pathlib import Path

from app.models.entities import GroupAccount
from app.utils.formatters import utc_now_iso


class AccountPoolService:
    def __init__(self, account_repository, group_account_repository, job_repository, restriction_repository, *, safety_service=None):
        self.accounts=account_repository; self.group_accounts=group_account_repository
        self.jobs=job_repository; self.restrictions=restriction_repository; self.safety=safety_service

    def get_page(self,page=1,page_size=100,search=None,enabled=None,health=None,restriction=None,safety=None):
        rows,total=self.accounts.get_pool_page(page,page_size,search,enabled=enabled,health=health,restriction=restriction,safety=safety)
        normalized=[]
        for row in rows:
            first=str(row.get("first_name") or "").strip();last=str(row.get("last_name") or "").strip();username=str(row.get("username") or "").strip()
            name=" ".join(x for x in (first,last) if x) or username or f"Account {row.get('id','')}"
            safety=self.safety.get_snapshot(int(row.get("id"))) if self.safety else {}
            normalized.append({**row,
                "account":name,
                "enabled":int(row.get("enabled_for_operations",1) or 0),
                "authorization":row.get("authorization_status") or "UNKNOWN",
                "connection":row.get("connection_status") or "OFFLINE",
                "health":row.get("health_status") or "UNKNOWN",
                "restriction":row.get("restriction_type") or "NONE",
                "invite_capability":int(row.get("mapped_can_invite",0) or 0),
                "post_capability":int(row.get("mapped_can_post",0) or 0),
                "groups":int(row.get("groups_count",0) or 0),
                "last_use":row.get("last_active_at") or row.get("last_success_at"),
                "cooldown_until":safety.get("cooldown_until") or row.get("restriction_until"),
                "smart_mode":safety.get("smart_mode",False),
                "safety_state":safety.get("state") or "NORMAL",
                "safety_reason":safety.get("reason"),
                "safety_next":safety.get("next_available_at"),
                "invite_used":safety.get("invite_used",0),
                "invite_limit":safety.get("invite_limit",0),
                "invite_remaining":safety.get("invite_remaining",0),
                "post_used":safety.get("post_used",0),
                "post_limit":safety.get("post_limit",0),
                "post_remaining":safety.get("post_remaining",0),
                "invite_spacing_seconds":safety.get("invite_spacing_seconds",0),
                "post_spacing_seconds":safety.get("post_spacing_seconds",0),
            })
        return normalized,total

    def set_operations_enabled(self, account_ids, enabled: bool):
        return self.accounts.set_operations_enabled_many(list(account_ids), enabled)

    def assign_tags(self, account_ids, tags):
        ids=sorted({int(x) for x in account_ids if x})
        for account_id in ids:self.accounts.replace_tags(account_id,list(tags))
        return len(ids)

    def clear_assignments(self, account_ids):
        ids=sorted({int(x) for x in account_ids if x});removed=0
        with self.accounts.db.transaction():
            for aid in ids:
                affected=[int(row["group_id"]) for row in self.accounts.db.fetch_all("SELECT group_id FROM group_accounts WHERE account_id=?",(aid,))]
                cur=self.accounts.db.execute("DELETE FROM group_accounts WHERE account_id=?",(aid,));removed+=int(cur.rowcount or 0)
                for group_id in affected:self._repair_primary(group_id)
        return removed

    def replace_group_assignments(self, account_id, group_ids):
        """Atomically replace one account's saved group mappings.

        New mappings are deliberately saved as unavailable until the Telegram
        permission service verifies them.  This keeps Collector, posting, and
        invitation operations fail-closed while still making the local mapping
        visible and recoverable after a verification error.
        """
        account_id=int(account_id)
        if not self.accounts.get_by_id(account_id):
            raise ValueError("The selected account no longer exists. Refresh Account Pool and try again.")
        selected=sorted({int(value) for value in (group_ids or []) if int(value)>0})
        if selected:
            placeholders=",".join("?" for _ in selected)
            existing_groups={int(row["id"]) for row in self.accounts.db.fetch_all(f"SELECT id FROM groups WHERE id IN ({placeholders})",tuple(selected))}
            missing=sorted(set(selected)-existing_groups)
            if missing:
                raise ValueError("One or more selected groups no longer exist. Refresh the group list and try again.")

        current_rows=self.accounts.db.fetch_all(
            "SELECT group_id,access_state,last_permission_check_at,last_error_code FROM group_accounts WHERE account_id=?",
            (account_id,),
        )
        current={int(row["group_id"]):dict(row) for row in current_rows}
        current_ids=set(current)
        selected_ids=set(selected)
        added=sorted(selected_ids-current_ids)
        removed=sorted(current_ids-selected_ids)
        kept=sorted(current_ids&selected_ids)
        retry_states={"UNKNOWN","UNAVAILABLE"}
        retry_errors={"PENDING_VERIFICATION","VERIFY_FAILED"}
        verify=sorted(
            group_id for group_id in selected
            if group_id in added
            or str(current.get(group_id,{}).get("access_state") or "UNKNOWN").upper() in retry_states
            or str(current.get(group_id,{}).get("last_error_code") or "").upper() in retry_errors
            or not current.get(group_id,{}).get("last_permission_check_at")
        )

        with self.accounts.db.transaction():
            for group_id in removed:
                self.accounts.db.execute("DELETE FROM group_accounts WHERE group_id=? AND account_id=?",(group_id,account_id))
                self._repair_primary(group_id)
            for group_id in added:
                self.group_accounts.upsert_mapping(GroupAccount(
                    group_id=group_id,
                    account_id=account_id,
                    role="UNKNOWN",
                    access_state="UNAVAILABLE",
                    is_primary=0,
                    last_error_code="PENDING_VERIFICATION",
                    last_error_message="Telegram permission verification is queued.",
                ))
                self._repair_primary(group_id)
            for group_id in set(verify)-set(added):
                self.group_accounts.mark_verification_unavailable(
                    group_id,account_id,"PENDING_VERIFICATION","Telegram permission verification is queued.",
                )
        return {"account_id":account_id,"selected":selected,"added":added,"removed":removed,"kept":kept,"verify":verify}

    def _repair_primary(self, group_id):
        """Promote one remaining mapping when a group's primary was removed."""
        group_id=int(group_id)
        primary=self.accounts.db.fetch_one("SELECT id FROM group_accounts WHERE group_id=? AND is_primary=1 ORDER BY id LIMIT 1",(group_id,))
        if primary:return False
        replacement=self.accounts.db.fetch_one("SELECT id FROM group_accounts WHERE group_id=? ORDER BY id LIMIT 1",(group_id,))
        if not replacement:return False
        self.accounts.db.execute("UPDATE group_accounts SET is_primary=1,updated_at=? WHERE id=?",(utc_now_iso(),int(replacement["id"])))
        return True

    def configure_safety(self, account_ids, values):
        if self.safety is None:
            raise RuntimeError("Account safety service is unavailable.")
        return self.safety.update_profiles(list(account_ids), dict(values or {}))

    def summary(self):
        row=self.accounts.db.fetch_one("""SELECT COUNT(*) total,
            SUM(CASE WHEN enabled_for_operations=1 AND is_enabled=1 THEN 1 ELSE 0 END) enabled,
            SUM(CASE WHEN health_status='HEALTHY' THEN 1 ELSE 0 END) healthy,
            SUM(CASE WHEN connection_status!='CONNECTED' THEN 1 ELSE 0 END) offline,
            SUM(CASE WHEN authorization_status!='AUTHORIZED' THEN 1 ELSE 0 END) login_required,
            SUM(CASE WHEN health_status='RESTRICTED' OR COALESCE(restriction_type,'') NOT IN ('','NONE','NONE_KNOWN','UNKNOWN') THEN 1 ELSE 0 END) restricted,
            SUM(CASE WHEN health_status='COOLDOWN' THEN 1 ELSE 0 END) cooldown
            FROM telegram_accounts""")
        busy=self.accounts.db.fetch_one("SELECT COUNT(DISTINCT account_id) n FROM jobs WHERE account_id IS NOT NULL AND status IN ('RUNNING','QUEUED','PAUSED')")
        caps=self.accounts.db.fetch_one("""SELECT
            COUNT(DISTINCT CASE WHEN ga.can_post=1 THEN ga.account_id END) posting,
            COUNT(DISTINCT CASE WHEN ga.can_invite=1 THEN ga.account_id END) inviting
            FROM group_accounts ga""")
        data=dict(row or {});data['busy']=int((busy or {'n':0})['n']);data['posting_available']=int((caps or {'posting':0})['posting'] or 0);data['invite_available']=int((caps or {'inviting':0})['inviting'] or 0)
        if self.safety:
            safety=self.safety.summary()
            data['watch']=int(safety.get('watch',0));data['recovering']=int(safety.get('recovering',0));data['daily_limited']=int(safety.get('daily_limited',0))
        return {k:int(v or 0) for k,v in data.items()}

    def export_csv(self,path,rows):
        fields=['id','account','username','enabled','authorization','connection','health','restriction','safety_state','invite_used','invite_limit','post_used','post_limit','invite_capability','post_capability','groups','current_job','last_use','cooldown_until','tags']
        with Path(path).open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
            for row in rows:writer.writerow({k:row.get(k,'') for k in fields})
