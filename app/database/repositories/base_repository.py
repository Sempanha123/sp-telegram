from __future__ import annotations

from typing import Any, Iterable

from app.database.database import DatabaseManager


class BaseRepository:
    table_name: str = ""
    id_column: str = "id"
    columns: tuple[str, ...] = ()

    def __init__(self, database: DatabaseManager) -> None:
        self.db = database

    def insert(self, values: dict[str, Any]) -> int:
        payload = {key: values[key] for key in self.columns if key in values}
        if not payload:
            raise ValueError("No valid fields supplied for insert.")
        names = tuple(payload.keys())
        placeholders = ", ".join("?" for _ in names)
        sql = f"INSERT INTO {self.table_name} ({', '.join(names)}) VALUES ({placeholders})"
        cursor = self.db.execute(sql, tuple(payload[name] for name in names))
        return int(cursor.lastrowid)

    def update_fields(self, record_id: int, values: dict[str, Any]) -> bool:
        payload = {key: values[key] for key in self.columns if key in values and key != self.id_column}
        if not payload:
            return False
        names = tuple(payload.keys())
        assignments = ", ".join(f"{name} = ?" for name in names)
        cursor = self.db.execute(
            f"UPDATE {self.table_name} SET {assignments} WHERE {self.id_column} = ?",
            (*[payload[name] for name in names], record_id),
        )
        return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        cursor = self.db.execute(
            f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?", (record_id,)
        )
        return cursor.rowcount > 0

    def find_by_id(self, record_id: int):
        row = self.db.fetch_one(
            f"SELECT {', '.join(self.columns)} FROM {self.table_name} WHERE {self.id_column} = ?",
            (record_id,),
        )
        return row

    def exists(self, record_id: int) -> bool:
        row = self.db.fetch_one(
            f"SELECT 1 AS found FROM {self.table_name} WHERE {self.id_column} = ? LIMIT 1", (record_id,)
        )
        return row is not None

    def count(self, where: str = "", params: tuple[Any, ...] = ()) -> int:
        # `where` is repository-owned SQL only; caller data remains parameterized.
        suffix = f" WHERE {where}" if where else ""
        row = self.db.fetch_one(f"SELECT COUNT(*) AS count FROM {self.table_name}{suffix}", params)
        return int(row["count"]) if row else 0
