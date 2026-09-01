from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import Member
from app.utils.formatters import utc_now_iso

COLS = (
    "id", "telegram_user_id", "username", "first_name", "last_name", "display_name",
    "is_deleted", "is_bot", "is_verified", "is_scam", "is_fake", "is_premium",
    "eligibility_status", "consent_status", "global_excluded", "notes", "first_seen_at",
    "last_seen_at", "profile_updated_at", "created_at", "updated_at",
)


class MemberRepository(BaseRepository):
    table_name = "members"
    columns = COLS

    def create(self, item: Member) -> Member:
        if item.telegram_user_id is None:
            raise ValueError("telegram_user_id is required.")
        now = utc_now_iso()
        data = asdict(item)
        data.pop("id", None)
        for key in ("sources", "tags", "is_blacklisted", "existing_target_state", "account_id"):
            data.pop(key, None)
        data["display_name"] = item.display_name or self._display_name(item.first_name, item.last_name, item.username)
        data["created_at"] = item.created_at or now
        data["updated_at"] = now
        data["first_seen_at"] = item.first_seen_at or now
        data["last_seen_at"] = item.last_seen_at or now
        item.id = self.insert(data)
        return self.get_by_id(item.id)

    def update(self, item: Member) -> Member:
        if item.id is None:
            raise ValueError("Member id is required.")
        data = asdict(item)
        for key in ("id", "sources", "tags", "is_blacklisted", "existing_target_state", "account_id"):
            data.pop(key, None)
        data["display_name"] = item.display_name or self._display_name(item.first_name, item.last_name, item.username)
        data["updated_at"] = utc_now_iso()
        self.update_fields(item.id, data)
        return self.get_by_id(item.id)

    def get_by_id(self, member_id: int) -> Member | None:
        return Member.from_row(self.find_by_id(member_id))

    def get_by_telegram_id(self, telegram_user_id: int) -> Member | None:
        row = self.db.fetch_one(
            f"SELECT {', '.join(COLS)} FROM members WHERE telegram_user_id=?",
            (telegram_user_id,),
        )
        return Member.from_row(row)

    def upsert(self, item: Member, *, preserve_local: bool = True) -> tuple[Member, bool, bool]:
        """Return (member, inserted, changed). Telegram sync never overwrites local metadata."""
        if item.telegram_user_id is None:
            raise ValueError("telegram_user_id is required.")
        existing = self.get_by_telegram_id(item.telegram_user_id)
        now = utc_now_iso()
        if existing is None:
            return self.create(item), True, True

        telegram_fields = {
            "username": item.username,
            "first_name": item.first_name,
            "last_name": item.last_name,
            "display_name": item.display_name or self._display_name(item.first_name, item.last_name, item.username),
            "is_deleted": int(bool(item.is_deleted)),
            "is_bot": int(bool(item.is_bot)),
            "is_verified": int(bool(item.is_verified)),
            "is_scam": int(bool(item.is_scam)),
            "is_fake": int(bool(item.is_fake)),
            "is_premium": int(bool(item.is_premium)),
            "last_seen_at": item.last_seen_at or now,
            "profile_updated_at": item.profile_updated_at or now,
            "updated_at": now,
        }
        changed = any(getattr(existing, key) != value for key, value in telegram_fields.items() if key != "updated_at")
        if not preserve_local:
            telegram_fields.update({
                "eligibility_status": item.eligibility_status,
                "consent_status": item.consent_status,
                "notes": item.notes,
                "global_excluded": int(bool(item.global_excluded)),
            })
        self.update_fields(existing.id, telegram_fields)
        return self.get_by_id(existing.id), False, changed

    def upsert_by_telegram_id(self, item: Member):
        if item.telegram_user_id is None:raise ValueError("telegram_user_id is required.")
        existing=self.get_by_telegram_id(item.telegram_user_id)
        if existing is None:return self.create(item),True
        now=utc_now_iso();values={"username":item.username,"first_name":item.first_name,"last_name":item.last_name,"display_name":item.display_name or self._display_name(item.first_name,item.last_name,item.username),"is_deleted":item.is_deleted,"is_bot":item.is_bot,"is_verified":item.is_verified,"is_scam":item.is_scam,"is_fake":item.is_fake,"is_premium":item.is_premium,"last_seen_at":item.last_seen_at or now,"profile_updated_at":item.profile_updated_at or now,"updated_at":now}
        if item.notes:values["notes"]=item.notes
        if item.eligibility_status and item.eligibility_status!="UNKNOWN":values["eligibility_status"]=item.eligibility_status
        if item.consent_status and item.consent_status!="UNKNOWN":values["consent_status"]=item.consent_status
        self.update_fields(existing.id,values);return self.get_by_id(existing.id),False

    def add_source(self,member_id:int,group_id:int):
        now=utc_now_iso();self.db.execute("""INSERT INTO member_sources(member_id,group_id,first_seen_at,last_seen_at,source_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(member_id,group_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,source_status='ACTIVE',updated_at=excluded.updated_at""",(member_id,group_id,now,now,"ACTIVE",now,now))
    def remove_source(self,member_id:int,group_id:int):return self.db.execute("DELETE FROM member_sources WHERE member_id=? AND group_id=?",(member_id,group_id)).rowcount>0

    def bulk_upsert(self, members: Iterable[Member]) -> dict[str, Any]:
        dedup: dict[int, Member] = {}
        duplicates = 0
        invalid = 0
        for member in members:
            if member.telegram_user_id is None:
                invalid += 1
                continue
            if member.telegram_user_id in dedup:
                duplicates += 1
            dedup[member.telegram_user_id] = member
        inserted = updated = unchanged = errors = 0
        member_ids: dict[int, int] = {}
        with self.db.transaction():
            for item in dedup.values():
                try:
                    saved, created, changed = self.upsert(item, preserve_local=True)
                    member_ids[int(item.telegram_user_id)] = int(saved.id)
                    if created:
                        inserted += 1
                    elif changed:
                        updated += 1
                    else:
                        unchanged += 1
                except Exception:
                    errors += 1
        return {
            "inserted": inserted, "updated": updated, "unchanged": unchanged,
            "duplicates": duplicates, "invalid": invalid, "errors": errors,
            "member_ids": member_ids,
        }

    def bulk_upsert_members(self, members: Iterable[Member]):
        return self.bulk_upsert(members)

    def search(self, query: str, limit: int = 100) -> list[Member]:
        term = f"%{query.strip()}%"
        rows = self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM members WHERE CAST(telegram_user_id AS TEXT) LIKE ? "
            "OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR notes LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (term, term, term, term, term, limit),
        )
        return [Member.from_row(row) for row in rows]

    def get_page(self, page: int, page_size: int, search: str | None = None,
                 eligibility: str | None = None, consent: str | None = None,
                 excluded: bool | None = None, only_username: bool = False, **kwargs):
        # Accept both the legacy ``excluded`` argument and the modern explicit
        # ``exclude_blacklist`` filter without ever forwarding the same keyword
        # twice to ``get_filtered_page``.
        explicit_exclude_blacklist = kwargs.pop("exclude_blacklist", None)
        if explicit_exclude_blacklist is None:
            explicit_exclude_blacklist = (excluded is False) if excluded is not None else False
        return self.get_filtered_page(
            page=page, page_size=page_size, search=search, eligibility=eligibility,
            consent=consent, exclude_blacklist=bool(explicit_exclude_blacklist),
            only_username=only_username, **kwargs,
        )

    def get_filtered_page(self, page: int = 1, page_size: int = 100, *, search: str | None = None,
                          eligibility: str | None = None, consent: str | None = None,
                          source_group_id: int | None = None, target_group_id: int | None = None,
                          tag: str | None = None, bot_filter: str | None = None,
                          blacklist_filter: str | None = None, exclude_blacklist: bool = False,
                          exclude_existing: bool = False, only_username: bool = False,
                          only_eligible: bool = False) -> tuple[list[Member], int]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            term = f"%{search.strip()}%"
            where.append("(CAST(m.telegram_user_id AS TEXT) LIKE ? OR m.username LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ? OR m.notes LIKE ?)")
            params.extend([term] * 5)
        if eligibility and eligibility.upper() != "ALL":
            where.append("m.eligibility_status=?")
            params.append(eligibility.upper().replace(" ", "_"))
        if only_eligible:
            where.append("m.eligibility_status='ELIGIBLE'")
        if consent and consent.upper() != "ALL":
            where.append("m.consent_status=?")
            params.append(consent.upper().replace(" ", "_"))
        if source_group_id:
            where.append("EXISTS (SELECT 1 FROM member_sources ms WHERE ms.member_id=m.id AND ms.group_id=? AND ms.source_status!='NO_LONGER_VISIBLE')")
            params.append(source_group_id)
        if tag and tag.upper() != "ALL":
            where.append("EXISTS (SELECT 1 FROM member_tag_links mtl JOIN member_tags mt ON mt.id=mtl.tag_id WHERE mtl.member_id=m.id AND mt.name=?)")
            params.append(tag)
        if bot_filter and bot_filter.upper() != "ALL":
            where.append("m.is_bot=?")
            params.append(1 if bot_filter.upper() in {"BOT", "BOTS", "YES"} else 0)
        if blacklist_filter and blacklist_filter.upper() != "ALL":
            want = blacklist_filter.upper() in {"BLACKLISTED", "EXCLUDED", "YES"}
            where.append(("" if want else "NOT ") + "EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL)")
        if exclude_blacklist:
            where.append("NOT EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL)")
        if only_username:
            where.append("m.username IS NOT NULL AND TRIM(m.username)<>''")
        if target_group_id and exclude_existing:
            where.append("NOT EXISTS (SELECT 1 FROM member_target_states mts WHERE mts.member_id=m.id AND mts.target_group_id=? AND mts.state IN ('MEMBER','ALREADY_MEMBER','JOINED'))")
            params.append(target_group_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        count_row = self.db.fetch_one(f"SELECT COUNT(*) AS count FROM members m{clause}", tuple(params))
        offset = (max(1, page) - 1) * page_size
        target_select = "'UNKNOWN'"
        target_params: list[Any] = []
        if target_group_id:
            target_select = """CASE
                WHEN m.is_deleted=1 THEN 'DELETED'
                WHEN EXISTS(SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL) THEN 'BLACKLISTED'
                WHEN m.eligibility_status='DO_NOT_CONTACT' OR EXISTS(SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='DO_NOT_CONTACT' AND mx.target_group_id IS NULL) THEN 'DO_NOT_CONTACT'
                ELSE COALESCE((SELECT CASE WHEN mts.state='MEMBER' THEN 'ALREADY_MEMBER' ELSE mts.state END FROM member_target_states mts WHERE mts.member_id=m.id AND mts.target_group_id=? LIMIT 1),'UNKNOWN')
            END"""
            target_params.append(target_group_id)
        sql = f"""
            SELECT {', '.join('m.' + c for c in COLS)},
                   COALESCE((SELECT GROUP_CONCAT(g.title, ', ') FROM member_sources ms JOIN groups g ON g.id=ms.group_id WHERE ms.member_id=m.id), '') AS sources,
                   (SELECT ms.last_seen_by_account_id FROM member_sources ms WHERE ms.member_id=m.id AND ms.last_seen_by_account_id IS NOT NULL ORDER BY ms.last_seen_at DESC LIMIT 1) AS account_id,
                   COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM member_tag_links ml JOIN member_tags t ON t.id=ml.tag_id WHERE ml.member_id=m.id), '') AS tags,
                   CASE WHEN EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='GLOBAL_BLACKLIST' AND x.target_group_id IS NULL) THEN 1 ELSE 0 END AS is_blacklisted,
                   {target_select} AS existing_target_state
            FROM members m{clause}
            ORDER BY m.id DESC LIMIT ? OFFSET ?
        """
        rows = self.db.fetch_all(sql, (*target_params, *params, page_size, offset))
        return [Member.from_row(row) for row in rows], int(count_row["count"] if count_row else 0)

    def get_filtered_ids(self, *, search: str | None = None, eligibility: str | None = None, consent: str | None = None,
                         source_group_id: int | None = None, target_group_id: int | None = None, tag: str | None = None,
                         bot_filter: str | None = None, blacklist_filter: str | None = None, exclude_blacklist: bool = False,
                         exclude_existing: bool = False, only_username: bool = False, only_eligible: bool = False) -> list[int]:
        """Return only primary keys for a filtered bulk operation; never materialize Member objects."""
        where=[];params=[]
        if search:
            term=f"%{search.strip()}%";where.append("(CAST(m.telegram_user_id AS TEXT) LIKE ? OR m.username LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ? OR m.notes LIKE ?)");params.extend([term]*5)
        if eligibility and eligibility.upper()!="ALL":where.append("m.eligibility_status=?");params.append(eligibility.upper().replace(" ","_"))
        if only_eligible:where.append("m.eligibility_status='ELIGIBLE'")
        if consent and consent.upper()!="ALL":where.append("m.consent_status=?");params.append(consent.upper().replace(" ","_"))
        if source_group_id:where.append("EXISTS (SELECT 1 FROM member_sources ms WHERE ms.member_id=m.id AND ms.group_id=? AND ms.source_status!='NO_LONGER_VISIBLE')");params.append(int(source_group_id))
        if tag and tag.upper()!="ALL":where.append("EXISTS (SELECT 1 FROM member_tag_links mtl JOIN member_tags mt ON mt.id=mtl.tag_id WHERE mtl.member_id=m.id AND mt.name=?)");params.append(tag)
        if bot_filter and bot_filter.upper()!="ALL":where.append("m.is_bot=?");params.append(1 if bot_filter.upper() in {"BOT","BOTS","YES"} else 0)
        if blacklist_filter and blacklist_filter.upper()!="ALL":
            want=blacklist_filter.upper() in {"BLACKLISTED","EXCLUDED","YES"};where.append(("" if want else "NOT ")+"EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL)")
        if exclude_blacklist:where.append("NOT EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL)")
        if only_username:where.append("m.username IS NOT NULL AND TRIM(m.username)<>''")
        if target_group_id and exclude_existing:where.append("NOT EXISTS (SELECT 1 FROM member_target_states mts WHERE mts.member_id=m.id AND mts.target_group_id=? AND mts.state IN ('MEMBER','ALREADY_MEMBER','JOINED'))");params.append(int(target_group_id))
        clause=" WHERE "+" AND ".join(where) if where else ""
        return [int(row["id"]) for row in self.db.fetch_all(f"SELECT m.id FROM members m{clause} ORDER BY m.id",tuple(params))]

    def count_all(self) -> int:
        return self.count()

    def count_eligible(self) -> int:
        return self.count("eligibility_status='ELIGIBLE'")

    def count_by_eligibility(self) -> dict[str, int]:
        rows = self.db.fetch_all("SELECT eligibility_status, COUNT(*) count FROM members GROUP BY eligibility_status")
        return {str(row["eligibility_status"]): int(row["count"]) for row in rows}

    def count_bots(self) -> int:
        return self.count("is_bot=1")

    def count_deleted(self) -> int:
        return self.count("is_deleted=1")

    def set_eligibility(self, member_id: int, status: str) -> bool:
        return self.update_fields(member_id, {"eligibility_status": status, "updated_at": utc_now_iso()})

    def set_consent(self, member_id: int, status: str) -> bool:
        return self.update_fields(member_id, {"consent_status": status, "updated_at": utc_now_iso()})

    def set_status_many(self, member_ids: Iterable[int], field: str, status: str) -> int:
        """Update one approved local status field with a single database write."""
        if field not in {"eligibility_status", "consent_status"}:
            raise ValueError("Unsupported member status field.")
        ids = sorted({int(value) for value in member_ids if int(value) > 0})
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        cursor = self.db.execute_with_retry(
            f"UPDATE members SET {field}=?, updated_at=? WHERE id IN ({placeholders})",
            (str(status), utc_now_iso(), *ids),
        )
        return int(cursor.rowcount)

    def set_global_excluded(self, member_id: int, value: bool) -> bool:
        return self.update_fields(member_id, {"global_excluded": int(value), "updated_at": utc_now_iso()})

    def update_profile(self, member_id: int, values: dict[str, Any]) -> bool:
        allowed = {"username", "first_name", "last_name", "display_name", "is_deleted", "is_bot", "is_verified", "is_scam", "is_fake", "is_premium", "last_seen_at", "profile_updated_at"}
        payload = {k: v for k, v in values.items() if k in allowed}
        payload["updated_at"] = utc_now_iso()
        return self.update_fields(member_id, payload)

    def update_last_seen(self, member_id: int, seen_at: str | None = None) -> bool:
        return self.update_fields(member_id, {"last_seen_at": seen_at or utc_now_iso(), "updated_at": utc_now_iso()})

    def get_by_source(self, group_id: int, page: int = 1, page_size: int = 100):
        return self.get_filtered_page(page, page_size, source_group_id=group_id)

    def get_by_target_state(self, target_group_id: int, state: str, page: int = 1, page_size: int = 100):
        offset = (max(1, page) - 1) * page_size
        rows = self.db.fetch_all(
            f"SELECT {', '.join('m.' + c for c in COLS)} FROM members m JOIN member_target_states s ON s.member_id=m.id "
            "WHERE s.target_group_id=? AND s.state=? ORDER BY m.id DESC LIMIT ? OFFSET ?",
            (target_group_id, state, page_size, offset),
        )
        return [Member.from_row(row) for row in rows]

    def get_source_names(self, member_id: int) -> list[str]:
        rows = self.db.fetch_all("SELECT g.title FROM member_sources s JOIN groups g ON g.id=s.group_id WHERE s.member_id=? ORDER BY g.title", (member_id,))
        return [str(row["title"]) for row in rows]

    def get_tags(self, member_id: int) -> list[str]:
        rows = self.db.fetch_all("SELECT t.name FROM member_tags t JOIN member_tag_links l ON l.tag_id=t.id WHERE l.member_id=? ORDER BY t.name", (member_id,))
        return [str(row["name"]) for row in rows]

    def list_tags(self) -> list[str]:
        return [str(row["name"]) for row in self.db.fetch_all("SELECT name FROM member_tags ORDER BY name")]

    def create_tag(self, name: str) -> int:
        clean=name.strip()
        if not clean:raise ValueError("Tag name is required.")
        self.db.execute("INSERT OR IGNORE INTO member_tags(name,created_at) VALUES(?,?)",(clean,utc_now_iso()))
        row=self.db.fetch_one("SELECT id FROM member_tags WHERE name=?",(clean,));return int(row["id"])

    def rename_tag(self, old_name: str, new_name: str) -> bool:
        clean=new_name.strip()
        if not clean:raise ValueError("Tag name is required.")
        return self.db.execute("UPDATE member_tags SET name=? WHERE name=?",(clean,old_name)).rowcount>0

    def delete_tag(self, name: str) -> bool:
        return self.db.execute("DELETE FROM member_tags WHERE name=?",(name,)).rowcount>0

    def add_tag(self, member_id: int, tag: str) -> None:
        clean = tag.strip()
        if not clean:
            return
        with self.db.transaction():
            self.db.execute("INSERT OR IGNORE INTO member_tags(name,created_at) VALUES(?,?)", (clean, utc_now_iso()))
            row = self.db.fetch_one("SELECT id FROM member_tags WHERE name=?", (clean,))
            self.db.execute("INSERT OR IGNORE INTO member_tag_links(member_id,tag_id) VALUES(?,?)", (member_id, int(row["id"])))

    def remove_tag(self, member_id: int, tag: str) -> bool:
        cursor = self.db.execute(
            "DELETE FROM member_tag_links WHERE member_id=? AND tag_id IN (SELECT id FROM member_tags WHERE name=?)",
            (member_id, tag),
        )
        return cursor.rowcount > 0

    def _target_preparation_clause(self, target_group_id: int, *, source_group_id: int | None = None,
                                   eligibility: str | None = None, consent: str | None = None,
                                   tag: str | None = None, username_search: str | None = None,
                                   exclude_existing: bool = True, exclude_blacklist: bool = True,
                                   exclude_do_not_contact: bool = True, exclude_deleted: bool = True,
                                   exclude_bots: bool = True, member_ids: list[int] | tuple[int, ...] | None = None) -> tuple[str, list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        if member_ids is not None:
            ids = sorted({int(x) for x in member_ids if int(x) > 0})
            if not ids:
                where.append("1=0")
            else:
                where.append(f"m.id IN ({','.join('?' for _ in ids)})")
                params.extend(ids)
        if source_group_id:
            where.append("EXISTS (SELECT 1 FROM member_sources ms WHERE ms.member_id=m.id AND ms.group_id=? AND ms.source_status!='NO_LONGER_VISIBLE')")
            params.append(int(source_group_id))
        if eligibility and str(eligibility).upper() not in {"ALL", ""}:
            where.append("m.eligibility_status=?")
            params.append(str(eligibility).upper().replace(" ", "_"))
        if consent and str(consent).upper() not in {"ALL", ""}:
            where.append("m.consent_status=?")
            params.append(str(consent).upper().replace(" ", "_"))
        if tag and str(tag).upper() not in {"ALL", ""}:
            where.append("EXISTS (SELECT 1 FROM member_tag_links mtl JOIN member_tags mt ON mt.id=mtl.tag_id WHERE mtl.member_id=m.id AND mt.name=?)")
            params.append(str(tag))
        if username_search:
            where.append("m.username LIKE ?")
            params.append(f"%{str(username_search).strip().lstrip('@')}%")
        if exclude_existing:
            where.append("NOT EXISTS (SELECT 1 FROM member_target_states mts WHERE mts.member_id=m.id AND mts.target_group_id=? AND mts.state IN ('MEMBER','ALREADY_MEMBER','JOINED'))")
            params.append(int(target_group_id))
        if exclude_blacklist:
            where.append("NOT EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='GLOBAL_BLACKLIST' AND mx.target_group_id IS NULL)")
        if exclude_do_not_contact:
            where.append("m.eligibility_status!='DO_NOT_CONTACT'")
            where.append("NOT EXISTS (SELECT 1 FROM member_exclusions mx WHERE mx.member_id=m.id AND mx.exclusion_type='DO_NOT_CONTACT' AND mx.target_group_id IS NULL)")
        if exclude_deleted:
            where.append("m.is_deleted=0")
        if exclude_bots:
            where.append("m.is_bot=0")
        clause = " WHERE " + " AND ".join(where) if where else ""
        return clause, params

    def get_target_preparation_members(self, target_group_id: int, *, source_group_id: int | None = None,
                                       eligibility: str | None = None, consent: str | None = None,
                                       tag: str | None = None, username_search: str | None = None,
                                       exclude_existing: bool = True, exclude_blacklist: bool = True,
                                       exclude_do_not_contact: bool = True, exclude_deleted: bool = True,
                                       exclude_bots: bool = True, member_ids: list[int] | tuple[int, ...] | None = None,
                                       limit: int = 250, offset: int = 0) -> list[Member]:
        clause, params = self._target_preparation_clause(
            target_group_id, source_group_id=source_group_id, eligibility=eligibility, consent=consent, tag=tag,
            username_search=username_search, exclude_existing=exclude_existing, exclude_blacklist=exclude_blacklist,
            exclude_do_not_contact=exclude_do_not_contact, exclude_deleted=exclude_deleted, exclude_bots=exclude_bots,
            member_ids=member_ids,
        )
        target_state = "COALESCE((SELECT CASE WHEN mts.state='MEMBER' THEN 'ALREADY_MEMBER' ELSE mts.state END FROM member_target_states mts WHERE mts.member_id=m.id AND mts.target_group_id=? LIMIT 1),'UNKNOWN')"
        sql = f"""
            SELECT {', '.join('m.' + c for c in COLS)},
                   COALESCE((SELECT GROUP_CONCAT(g.title, ', ') FROM member_sources ms JOIN groups g ON g.id=ms.group_id WHERE ms.member_id=m.id), '') AS sources,
                   COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM member_tag_links ml JOIN member_tags t ON t.id=ml.tag_id WHERE ml.member_id=m.id), '') AS tags,
                   CASE WHEN EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='GLOBAL_BLACKLIST' AND x.target_group_id IS NULL) THEN 1 ELSE 0 END AS is_blacklisted,
                   CASE
                       WHEN m.is_deleted=1 THEN 'DELETED'
                       WHEN m.eligibility_status='DO_NOT_CONTACT' OR EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='DO_NOT_CONTACT' AND x.target_group_id IS NULL) THEN 'DO_NOT_CONTACT'
                       WHEN EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='GLOBAL_BLACKLIST' AND x.target_group_id IS NULL) THEN 'BLACKLISTED'
                       WHEN EXISTS(SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.target_group_id=?) THEN 'EXCLUDED'
                       ELSE {target_state}
                   END AS existing_target_state
            FROM members m{clause}
            ORDER BY m.id DESC LIMIT ? OFFSET ?
        """
        rows = self.db.fetch_all(sql, (int(target_group_id), int(target_group_id), *params, max(1, int(limit)), max(0, int(offset))))
        return [Member.from_row(row) for row in rows]

    def count_target_preparation(self, target_group_id: int, **filters) -> int:
        clause, params = self._target_preparation_clause(target_group_id, **filters)
        row = self.db.fetch_one(f"SELECT COUNT(*) count FROM members m{clause}", tuple(params))
        return int(row["count"] if row else 0)

    def target_preparation_summary(self, target_group_id: int, **filters) -> dict[str, int]:
        member_ids = filters.get("member_ids")
        ids = sorted({int(x) for x in (member_ids or []) if int(x) > 0}) if member_ids is not None else None
        if ids is None:
            scope_sql = ""
            scope_params: list[Any] = []
            total = self.count_all()
        elif not ids:
            scope_sql = " AND 1=0"
            scope_params = []
            total = 0
        else:
            placeholders = ",".join("?" for _ in ids)
            scope_sql = f" AND m.id IN ({placeholders})"
            scope_params = list(ids)
            total = int(self.db.fetch_one(f"SELECT COUNT(*) count FROM members m WHERE m.id IN ({placeholders})", tuple(ids))["count"])

        def scalar(sql: str, params=()):
            row = self.db.fetch_one(sql, tuple(params))
            return int(row["count"] if row else 0)

        existing = scalar(
            "SELECT COUNT(DISTINCT m.id) count FROM members m JOIN member_target_states s ON s.member_id=m.id "
            "WHERE s.target_group_id=? AND s.state IN ('MEMBER','ALREADY_MEMBER','JOINED')" + scope_sql,
            [int(target_group_id), *scope_params],
        )
        blacklist = scalar(
            "SELECT COUNT(DISTINCT m.id) count FROM members m WHERE EXISTS("
            "SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='GLOBAL_BLACKLIST' AND x.target_group_id IS NULL)" + scope_sql,
            scope_params,
        )
        dnc = scalar(
            "SELECT COUNT(DISTINCT m.id) count FROM members m WHERE (m.eligibility_status='DO_NOT_CONTACT' OR EXISTS("
            "SELECT 1 FROM member_exclusions x WHERE x.member_id=m.id AND x.exclusion_type='DO_NOT_CONTACT' AND x.target_group_id IS NULL))" + scope_sql,
            scope_params,
        )
        consent_not_approved = scalar(
            "SELECT COUNT(*) count FROM members m WHERE COALESCE(m.consent_status,'UNKNOWN')!='APPROVED'" + scope_sql, scope_params
        )
        deleted = scalar("SELECT COUNT(*) count FROM members m WHERE m.is_deleted=1" + scope_sql, scope_params)
        bots = scalar("SELECT COUNT(*) count FROM members m WHERE m.is_bot=1" + scope_sql, scope_params)
        unknown = scalar(
            "SELECT COUNT(*) count FROM members m WHERE (NOT EXISTS(SELECT 1 FROM member_target_states s WHERE s.member_id=m.id AND s.target_group_id=?) "
            "OR EXISTS(SELECT 1 FROM member_target_states s WHERE s.member_id=m.id AND s.target_group_id=? AND s.state='UNKNOWN'))" + scope_sql,
            [int(target_group_id), int(target_group_id), *scope_params],
        )
        eligible = self.count_target_preparation(target_group_id, **filters)
        strict_filters = dict(filters)
        strict_filters.update(eligibility="ELIGIBLE", consent="APPROVED", exclude_existing=True, exclude_blacklist=True, exclude_do_not_contact=True, exclude_deleted=True, exclude_bots=True)
        ready_clause, ready_params = self._target_preparation_clause(target_group_id, **strict_filters)
        ready_join = " AND " if ready_clause else " WHERE "
        ready = scalar(
            f"SELECT COUNT(*) count FROM members m{ready_clause}{ready_join}EXISTS("
            "SELECT 1 FROM member_target_states s WHERE s.member_id=m.id AND s.target_group_id=? AND s.state='NOT_MEMBER')",
            [*ready_params, int(target_group_id)],
        )
        return {
            "total": total, "input_selection": len(ids) if ids is not None else 0,
            "existing": existing, "blacklist": blacklist, "do_not_contact": dnc,
            "consent_not_approved": consent_not_approved, "deleted": deleted, "bots": bots,
            "unknown": unknown, "eligible": int(eligible), "ready": int(ready),
        }

    @staticmethod
    def _display_name(first_name: str | None, last_name: str | None, username: str | None) -> str | None:
        name = " ".join(part for part in (first_name, last_name) if part).strip()
        return name or (f"@{username}" if username else None)
