from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from investmentology.registry.db import Database


class TestDatabaseInit:
    def test_stores_dsn(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")
        assert db._dsn == "postgresql://u:p@localhost:5432/testdb"

    def test_not_connected_by_default(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")
        assert db._pool is None
        assert db._conn is None


class TestDatabaseExecute:
    def test_execute_returns_dicts(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        # Mock a connection with dict rows
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db._conn = mock_conn

        result = db.execute("SELECT id, name FROM stocks")
        assert result == [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]

    def test_execute_no_results(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db._conn = mock_conn

        result = db.execute("INSERT INTO stocks (name) VALUES (%s)", ("AAPL",))
        assert result == []

    def test_execute_raises_when_not_connected(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")
        with pytest.raises(RuntimeError, match="not connected"):
            db.execute("SELECT 1")


class TestDatabaseExecuteMany:
    def test_execute_many_returns_count(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db._conn = mock_conn

        count = db.execute_many(
            "INSERT INTO stocks (name) VALUES (%s)",
            [("AAPL",), ("GOOG",), ("MSFT",)],
        )
        assert count == 3


class TestMigrationRunner:
    def test_finds_and_runs_sql_files(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        # Create temp migration files
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "001_create_table.sql").write_text(
                "CREATE TABLE test (id INT);"
            )
            (Path(tmpdir) / "002_add_column.sql").write_text(
                "ALTER TABLE test ADD COLUMN name TEXT;"
            )

            # Mock cursor
            mock_cursor = MagicMock()
            # First fetchall returns empty (no applied migrations)
            mock_cursor.fetchall.return_value = []
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=False)

            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            db._conn = mock_conn

            db.run_migrations(tmpdir)

            # Should have executed: CREATE _migrations table, SELECT applied,
            # then for each migration: execute SQL + INSERT into _migrations
            # Plus commits
            calls = mock_cursor.execute.call_args_list
            # CREATE TABLE _migrations
            assert "_migrations" in str(calls[0])
            # SELECT applied
            assert "SELECT filename" in str(calls[1])
            # Two migration files executed (SQL + INSERT each)
            assert len(calls) == 6  # CREATE + SELECT + 2*(SQL + INSERT)

    def test_skips_applied_migrations(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "001_create_table.sql").write_text("CREATE TABLE test (id INT);")
            (Path(tmpdir) / "002_add_column.sql").write_text("ALTER TABLE test ADD COLUMN name TEXT;")

            mock_cursor = MagicMock()
            # Return first migration as already applied
            mock_cursor.fetchall.return_value = [{"filename": "001_create_table.sql"}]
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=False)

            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            db._conn = mock_conn

            db.run_migrations(tmpdir)

            calls = mock_cursor.execute.call_args_list
            # CREATE + SELECT + only 1 migration (SQL + INSERT) = 4
            assert len(calls) == 4


class TestHealthCheck:
    def test_healthy(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")

        mock_cursor = MagicMock()
        mock_cursor.description = [("ok",)]
        mock_cursor.fetchall.return_value = [{"ok": 1}]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        db._conn = mock_conn

        assert db.health_check() is True

    def test_unhealthy(self) -> None:
        db = Database("postgresql://u:p@localhost:5432/testdb")
        # Not connected, so execute will raise
        assert db.health_check() is False


class TestContextManager:
    @patch("investmentology.registry.db.HAS_POOL", False)
    @patch("investmentology.registry.db.psycopg")
    def test_context_manager(self, mock_psycopg: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_psycopg.connect.return_value = mock_conn

        with Database("postgresql://u:p@localhost:5432/testdb") as db:
            assert db._conn is mock_conn

        mock_conn.close.assert_called_once()
