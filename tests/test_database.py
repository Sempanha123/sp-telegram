"""Tests for DatabaseManager - verifying connection lifecycle and thread safety."""

import pytest
import sqlite3
import threading
import tempfile
from pathlib import Path

from app.database.database import DatabaseManager, DatabaseError


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def db_manager(temp_db_path):
    """Create a DatabaseManager instance with temp database."""
    manager = DatabaseManager(temp_db_path)
    manager.initialize()
    yield manager
    manager.close()


class TestDatabaseManager:
    """Tests for DatabaseManager core functionality."""

    def test_get_connection_returns_valid_connection(self, db_manager):
        """get_connection should return a working SQLite connection."""
        conn = db_manager.get_connection()
        assert conn is not None
        # Verify it works
        cursor = conn.execute("SELECT 1 as test")
        row = cursor.fetchone()
        assert row["test"] == 1

    def test_execute_works(self, db_manager):
        """execute should run SQL and commit."""
        db_manager.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
        db_manager.execute("INSERT INTO test_table (value) VALUES (?)", ("test_value",))
        row = db_manager.fetch_one("SELECT value FROM test_table WHERE id = 1")
        assert row["value"] == "test_value"

    def test_transaction_commits(self, db_manager):
        """Transaction context manager should commit on success."""
        db_manager.execute("CREATE TABLE test_tx (id INTEGER PRIMARY KEY, value TEXT)")
        
        with db_manager.transaction() as conn:
            conn.execute("INSERT INTO test_tx (value) VALUES (?)", ("tx_value",))
        
        row = db_manager.fetch_one("SELECT value FROM test_tx WHERE id = 1")
        assert row["value"] == "tx_value"

    def test_transaction_rolls_back_on_error(self, db_manager):
        """Transaction should rollback on exception."""
        db_manager.execute("CREATE TABLE test_tx2 (id INTEGER PRIMARY KEY, value TEXT UNIQUE)")
        db_manager.execute("INSERT INTO test_tx2 (value) VALUES (?)", ("existing",))
        
        with pytest.raises(DatabaseError):
            with db_manager.transaction() as conn:
                conn.execute("INSERT INTO test_tx2 (value) VALUES (?)", ("existing",))  # Duplicate
        
        # Original row should still exist, duplicate should not
        rows = db_manager.fetch_all("SELECT value FROM test_tx2")
        assert len(rows) == 1
        assert rows[0]["value"] == "existing"

    def test_close_marks_database_closed(self, db_manager):
        """After close, get_connection should raise DatabaseError."""
        db_manager.close()
        
        with pytest.raises(DatabaseError) as exc_info:
            db_manager.get_connection()
        assert exc_info.value.kind == "closed"
        assert "Database is closed" in str(exc_info.value)

    def test_stale_connection_detected_after_close(self, db_manager):
        """Thread-local stale connections should be detected after close."""
        # Get a connection in this thread
        conn = db_manager.get_connection()
        assert conn is not None
        
        # Close the database (simulates another thread calling close)
        db_manager.close()
        
        # Try to use the stale connection - should raise and create new
        with pytest.raises(DatabaseError) as exc_info:
            db_manager.get_connection()
        assert exc_info.value.kind == "closed"

    def test_concurrent_threads_get_separate_connections(self, db_manager):
        """Multiple threads should get their own connections."""
        results = []
        errors = []
        
        def worker():
            try:
                conn = db_manager.get_connection()
                cursor = conn.execute("SELECT 1")
                row = cursor.fetchone()
                results.append(row[0])
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 5
        assert all(r == 1 for r in results)

    def test_execute_many_works(self, db_manager):
        """execute_many should insert multiple rows."""
        db_manager.execute("CREATE TABLE test_many (id INTEGER PRIMARY KEY, value TEXT)")
        rows = [(f"value_{i}",) for i in range(10)]
        db_manager.execute_many("INSERT INTO test_many (value) VALUES (?)", rows)
        
        count = db_manager.fetch_one("SELECT COUNT(*) as c FROM test_many")
        assert count["c"] == 10

    def test_backup_and_validate(self, db_manager, temp_db_path):
        """backup_to and validate_database_file should work."""
        db_manager.execute("CREATE TABLE test_backup (id INTEGER PRIMARY KEY)")
        db_manager.execute("INSERT INTO test_backup (id) VALUES (1), (2), (3)")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            backup_path = Path(f.name)
        
        try:
            db_manager.backup_to(backup_path)
            assert backup_path.exists()
            
            # Validate the backup
            assert db_manager.validate_database_file(backup_path) is True
            
            # Validate original
            assert db_manager.validate_database_file(temp_db_path) is True
        finally:
            if backup_path.exists():
                backup_path.unlink()

    def test_invalid_backup_rejected(self, db_manager):
        """validate_database_file should reject invalid files."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            invalid_path = Path(f.name)
        invalid_path.write_text("not a sqlite database")
        
        try:
            assert db_manager.validate_database_file(invalid_path) is False
        finally:
            invalid_path.unlink()