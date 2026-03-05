from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

try:
    from psycopg_pool import ConnectionPool

    HAS_POOL = True
except ImportError:
    HAS_POOL = False

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database wrapper using psycopg3."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: ConnectionPool | None = None
        self._conn: psycopg.Connection | None = None

    def connect(self) -> None:
        """Create a connection pool (or single connection if pool unavailable)."""
        if HAS_POOL:
            self._pool = ConnectionPool(
                self._dsn,
                min_size=2,
                max_size=10,
                timeout=30.0,
                max_lifetime=3600,
                kwargs={"row_factory": dict_row},
            )
            self._pool.wait()
            logger.info("Connection pool established")
        else:
            self._conn = psycopg.connect(self._dsn, row_factory=dict_row)
            logger.info("Single connection established (psycopg_pool not available)")

    def close(self) -> None:
        """Close the connection pool or single connection."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_connection(self) -> psycopg.Connection:
        """Get a connection from the pool or return the single connection."""
        if self._pool is not None:
            return self._pool.getconn()
        if self._conn is not None:
            return self._conn
        raise RuntimeError("Database not connected. Call connect() first.")

    def _put_connection(self, conn: psycopg.Connection) -> None:
        """Return a connection to the pool if using pooling."""
        if self._pool is not None:
            self._pool.putconn(conn)

    def execute(self, query: str, params: tuple | None = None) -> list[dict]:
        """Execute a query and return rows as dicts."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description is not None:
                    rows = cur.fetchall()
                    conn.commit()
                    return [dict(row) for row in rows]
                conn.commit()
                return []
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    def execute_many(self, query: str, params_seq: list[tuple]) -> int:
        """Batch execute a query, return affected row count."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                count = 0
                for params in params_seq:
                    cur.execute(query, params)
                    count += cur.rowcount if cur.rowcount >= 0 else 0
                conn.commit()
                return count
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    @contextmanager
    def transaction(self) -> Iterator[_TransactionProxy]:
        """Yield a proxy that executes multiple statements in a single transaction.

        Commits on clean exit; rolls back on exception.
        """
        conn = self._get_connection()
        proxy = _TransactionProxy(conn)
        try:
            yield proxy
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    def run_migrations(self, migrations_dir: str) -> None:
        """Run SQL migration files in order, tracking applied migrations."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Create migrations tracking table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS _migrations (
                        filename TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                conn.commit()

                # Find applied migrations
                cur.execute("SELECT filename FROM _migrations ORDER BY filename")
                applied = {row["filename"] for row in cur.fetchall()}

                # Find and run pending migrations
                migrations_path = Path(migrations_dir)
                sql_files = sorted(migrations_path.glob("*.sql"))

                for sql_file in sql_files:
                    if sql_file.name in applied:
                        logger.debug("Skipping already applied migration: %s", sql_file.name)
                        continue

                    logger.info("Applying migration: %s", sql_file.name)
                    sql = sql_file.read_text()
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO _migrations (filename) VALUES (%s)",
                        (sql_file.name,),
                    )
                    conn.commit()
        finally:
            self._put_connection(conn)

    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            result = self.execute("SELECT 1 AS ok")
            return len(result) > 0 and result[0].get("ok") == 1
        except Exception:
            logger.exception("Health check failed")
            return False

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncDatabase:
    """Async PostgreSQL database wrapper using psycopg3 AsyncConnectionPool.

    Provides the same interface as Database but with async methods.
    Can run alongside the sync Database during gradual migration.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool = None  # psycopg_pool.AsyncConnectionPool

    async def connect(self) -> None:
        """Create an async connection pool."""
        try:
            from psycopg_pool import AsyncConnectionPool
        except ImportError:
            logger.warning("psycopg_pool not available — AsyncDatabase disabled")
            return

        self._pool = AsyncConnectionPool(
            self._dsn,
            min_size=2,
            max_size=10,
            timeout=30.0,
            max_lifetime=3600,
            kwargs={"row_factory": dict_row},
        )
        await self._pool.wait()
        logger.info("Async connection pool established")

    async def close(self) -> None:
        """Close the async connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def execute(self, query: str, params: tuple | None = None) -> list[dict]:
        """Execute a query and return rows as dicts."""
        if self._pool is None:
            raise RuntimeError("AsyncDatabase not connected")
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if cur.description is not None:
                    rows = await cur.fetchall()
                    return [dict(row) for row in rows]
                return []

    async def execute_many(self, query: str, params_seq: list[tuple]) -> int:
        """Batch execute a query, return affected row count."""
        if self._pool is None:
            raise RuntimeError("AsyncDatabase not connected")
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                count = 0
                for params in params_seq:
                    await cur.execute(query, params)
                    count += cur.rowcount if cur.rowcount >= 0 else 0
                return count

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            result = await self.execute("SELECT 1 AS ok")
            return len(result) > 0 and result[0].get("ok") == 1
        except Exception:
            logger.exception("Async health check failed")
            return False


class _TransactionProxy:
    """Wraps a single connection for use inside Database.transaction().

    Exposes only execute() — intentionally no execute_many() to keep
    transaction scope narrow and reviewable.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def execute(self, query: str, params: tuple | None = None) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is not None:
                return [dict(row) for row in cur.fetchall()]
            return []
