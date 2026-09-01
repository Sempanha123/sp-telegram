from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso


class MemberTargetActionRepository(BaseRepository):
    table_name = "member_target_actions"
    columns = (
        "id","member_id","target_group_id","account_id","action_type","status",
        "telegram_error_code","error_message","attempted_at","completed_at","job_id","created_at","updated_at",
    )

    def create_action(self, member_id:int, target_group_id:int, account_id:int|None, action_type:str, *, status="PENDING", job_id:int|None=None):
        now=utc_now_iso()
        action_id=self.insert({
            "member_id":int(member_id),"target_group_id":int(target_group_id),"account_id":account_id,
            "action_type":str(action_type),"status":str(status),"attempted_at":now,"job_id":job_id,
            "created_at":now,"updated_at":now,
        })
        return self.find_by_id(action_id)

    def finish_action(self, action_id:int, status:str, *, error_code:str|None=None, error_message:str|None=None):
        now=utc_now_iso()
        self.update_fields(action_id,{"status":str(status),"telegram_error_code":error_code,"error_message":error_message,"completed_at":now,"updated_at":now})
        return self.find_by_id(action_id)

    def get_for_member(self, member_id:int, limit:int=200):
        return self.db.fetch_all(
            """SELECT a.*,g.title target_title,ta.first_name account_name,ta.username account_username
               FROM member_target_actions a
               LEFT JOIN groups g ON g.id=a.target_group_id
               LEFT JOIN telegram_accounts ta ON ta.id=a.account_id
               WHERE a.member_id=? ORDER BY a.attempted_at DESC LIMIT ?""",
            (int(member_id),max(1,int(limit))),
        )

    def get_for_job(self, job_id:int, limit:int=1000):
        return self.db.fetch_all(
            """SELECT a.*,m.username,m.display_name,m.telegram_user_id,g.title target_title
               FROM member_target_actions a
               JOIN members m ON m.id=a.member_id
               JOIN groups g ON g.id=a.target_group_id
               WHERE a.job_id=? ORDER BY a.id LIMIT ?""",
            (int(job_id),max(1,int(limit))),
        )

    def get_for_target(self, target_group_id:int, limit:int=500):
        return self.db.fetch_all(
            """SELECT a.*,m.username,m.display_name,m.telegram_user_id,ta.first_name account_name,ta.username account_username
               FROM member_target_actions a
               JOIN members m ON m.id=a.member_id
               LEFT JOIN telegram_accounts ta ON ta.id=a.account_id
               WHERE a.target_group_id=? ORDER BY a.attempted_at DESC LIMIT ?""",
            (int(target_group_id),max(1,int(limit))),
        )
