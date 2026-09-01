from __future__ import annotations
class TelegramMemberFilterService:
    @staticmethod
    def include(member,options)->tuple[bool,str|None]:
        if options.skip_bots and bool(member.is_bot):return False,"BOT"
        if options.skip_deleted and bool(member.is_deleted):return False,"DELETED_ACCOUNT"
        if options.only_with_username and not member.username:return False,"NO_USERNAME"
        return True,None
