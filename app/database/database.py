from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from app.database.migrations import apply_migrations
from app.utils.formatters import utc_now_iso


class DatabaseError(Exception):
    """User-safe database exception while preserving an internal error category."""

    def __init__(self, message: str, *, kind: str = "database", original: Exception | None = None):
        super().__init__(message)
        self.kind = kind
        self.original = original


class DatabaseManager:
    def __init__(self, db_path: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path) if db_path else project_root / "data" / "tg_control.db"
        self.db_path = self.db_path.resolve()
        self._local = threading.local()
        self._lock = threading.RLock()
        self._connections: list[sqlite3.Connection] = []
        self._tx_guard = threading.RLock()
        self._active_transactions = 0
        self.schema_version = 0
        self._closed = False
        self._restore_lock = threading.Lock()

    def initialize(self) -> int:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.get_connection()
        try:
            self.schema_version = apply_migrations(connection)
            return self.schema_version
        except sqlite3.Error as exc:
            raise self._convert_error(exc) from exc

    def _configure(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")

    def get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise DatabaseError("Database is closed.", kind="closed")
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            # Check if connection is stale (closed by another thread)
            try:
                connection.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                # Connection was closed, clear thread-local state and create new
                connection = None
        if connection is None:
            try:
                connection = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
                self._configure(connection)
            except sqlite3.Error as exc:
                raise self._convert_error(exc) from exc
            self._local.connection = connection
            self._local.tx_depth = 0
            with self._lock:
                self._connections.append(connection)
        return connection

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        try:
            connection = self.get_connection()
            cursor = connection.execute(sql, tuple(params))
            if getattr(self._local, "tx_depth", 0) == 0:
                connection.commit()
            return cursor
        except sqlite3.Error as exc:
            if getattr(self._local, "tx_depth", 0) == 0:
                try:
                    self.get_connection().rollback()
                except Exception as rollback_exc:
                    logging.getLogger(__name__).warning("SQLite rollback after execute failure also failed: %s", rollback_exc)
            raise self._convert_error(exc) from exc

    def execute_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        try:
            connection = self.get_connection()
            cursor = connection.executemany(sql, rows)
            if getattr(self._local, "tx_depth", 0) == 0:
                connection.commit()
            return cursor
        except sqlite3.Error as exc:
            if getattr(self._local, "tx_depth", 0) == 0:
                try:
                    self.get_connection().rollback()
                except Exception as rollback_exc:
                    logging.getLogger(__name__).warning("SQLite rollback after executemany failure also failed: %s", rollback_exc)
            raise self._convert_error(exc) from exc

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        try:
            return self.get_connection().execute(sql, tuple(params)).fetchone()
        except sqlite3.Error as exc:
            raise self._convert_error(exc) from exc

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        try:
            return list(self.get_connection().execute(sql, tuple(params)).fetchall())
        except sqlite3.Error as exc:
            raise self._convert_error(exc) from exc

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.get_connection()
        depth = int(getattr(self._local, "tx_depth", 0))
        savepoint = f"sp_{depth}"
        try:
            if depth == 0:
                connection.execute("BEGIN IMMEDIATE")
            else:
                connection.execute(f"SAVEPOINT {savepoint}")
            self._local.tx_depth = depth + 1
            if depth == 0:
                with self._tx_guard:
                    self._active_transactions += 1
            yield connection
            self._local.tx_depth = depth
            if depth == 0:
                connection.commit()
                with self._tx_guard:
                    self._active_transactions = max(0, self._active_transactions - 1)
            else:
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except sqlite3.Error as exc:
            self._local.tx_depth = depth
            if depth == 0:
                connection.rollback()
                with self._tx_guard:
                    self._active_transactions = max(0, self._active_transactions - 1)
            else:
                try:
                    connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                except Exception:
                    logging.getLogger(__name__).warning("Failed to rollback savepoint %s", savepoint)
            raise self._convert_error(exc) from exc
        except Exception:
            self._local.tx_depth = depth
            if depth == 0:
                connection.rollback()
                with self._tx_guard:
                    self._active_transactions = max(0, self._active_transactions - 1)
            else:
                try:
                    connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                except Exception:
                    logging.getLogger(__name__).warning("Failed to rollback savepoint %s", savepoint)
            raise


    def has_active_transactions(self) -> bool:
        with self._tx_guard:
            return self._active_transactions > 0

    def execute_with_retry(self, sql: str, params: Sequence[Any] = (), *, attempts: int = 3) -> sqlite3.Cursor:
        """Limited retry for transient SQLite locks. PRAGMA busy_timeout supplies the wait/backoff."""
        attempts = max(1, min(5, int(attempts)))
        last_error: DatabaseError | None = None
        for _ in range(attempts):
            try:
                return self.execute(sql, params)
            except DatabaseError as exc:
                last_error = exc
                if exc.kind != "locked":
                    raise
        assert last_error is not None
        raise last_error

    def get_schema_version(self) -> int:
        row = self.fetch_one("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations")
        return int(row["version"]) if row else 0

    def backup_to(self, path: str | Path) -> Path:
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            source = self.get_connection()
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
            return destination
        except sqlite3.Error as exc:
            raise self._convert_error(exc) from exc

    def validate_database_file(self, path: str | Path) -> bool:
        source_path = Path(path)
        if not source_path.is_file():
            return False
        try:
            connection = sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True)
            try:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                return bool(row and str(row[0]).lower() == "ok")
            finally:
                connection.close()
        except sqlite3.Error:
            return False

    def restore_from(self, path: str | Path, *, safety_backup_dir: str | Path | None = None) -> Path | None:
        with self._restore_lock:
            source_path = Path(path).resolve()
            if source_path == self.db_path:
                raise DatabaseError("Select a backup file different from the active database.", kind="invalid_backup")
            if not self.validate_database_file(source_path):
                raise DatabaseError("The selected backup is not a valid SQLite database.", kind="invalid_backup")
            safety_path: Path | None = None
            if self.db_path.exists() and safety_backup_dir is not None:
                folder = Path(safety_backup_dir).resolve()
                folder.mkdir(parents=True, exist_ok=True)
                stamp = utc_now_iso().replace(":", "").replace("+00:00", "Z").replace("T", "_")
                safety_path = folder / f"pre_restore_{stamp}.db"
                self.backup_to(safety_path)
            self.close()
            try:
                source = sqlite3.connect(source_path)
                target = sqlite3.connect(self.db_path)
                try:
                    source.backup(target)
                    target.commit()
                finally:
                    target.close()
                    source.close()
            except sqlite3.Error as exc:
                raise self._convert_error(exc) from exc
            self._closed = False
            self.initialize()
            return safety_path

    def close(self) -> None:
        # Mark as closed first so new get_connection() calls fail fast
        self._closed = True
        with self._lock:
            connections = list(self._connections)
            self._connections.clear()
        for connection in connections:
            try:
                connection.rollback()
                connection.close()
            except sqlite3.Error:
                pass
        # Clear calling thread's local state
        self._local.connection = None
        self._local.tx_depth = 0

    @staticmethod
    def _convert_error(exc: sqlite3.Error) -> DatabaseError:
        logging.getLogger("tg_control_center.database").error("SQLite %s: %s", type(exc).__name__, exc)
        text = str(exc).lower()
        if isinstance(exc, sqlite3.IntegrityError):
            if "unique" in text:
                kind = "unique"
            elif "foreign key" in text:
                kind = "foreign_key"
            else:
                kind = "integrity"
        elif isinstance(exc, sqlite3.OperationalError):
            kind = "locked" if "locked" in text else "operational"
        else:
            kind = "database"
        return DatabaseError("A database operation could not be completed.", kind=kind, original=exc)
