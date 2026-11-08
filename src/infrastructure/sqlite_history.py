import datetime
import json
import sqlite3
from contextlib import contextmanager
from typing import List

from src.domain.history import HistoryEntry, HistoryRepository


class SQLiteHistoryRepository(HistoryRepository):
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._memory_conn = None
        self._init_db()

    def _get_connection(self):
        # Aislamiento básico y pragmas de seguridad
        if self.db_path == ":memory:" or "?mode=memory" in self.db_path:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(
                    self.db_path,
                    uri=True
                    if "?mode=" in self.db_path or self.db_path.startswith("file:")
                    else False,
                )
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.execute("PRAGMA foreign_keys = ON;")
            return self._memory_conn

        if self.db_path.startswith("file:"):
            conn = sqlite3.connect(self.db_path, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    original_input TEXT NOT NULL,
                    module_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    response_summary TEXT
                )
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(history)")}
            if "parameters" not in columns:
                conn.execute(
                    (
                        "ALTER TABLE history ADD COLUMN parameters TEXT NOT "
                        "NULL DEFAULT '{}'"
                    )
                )
            conn.execute("PRAGMA user_version = 1")

    @contextmanager
    def _connection(self):
        conn = self._get_connection()
        try:
            with conn:
                yield conn
        finally:
            if conn is not self._memory_conn:
                conn.close()

    def close(self) -> None:
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    def save(self, entry: HistoryEntry) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO history (
                    id, original_input, module_id, created_at,
                    response_summary, parameters
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.id,
                    entry.original_input,
                    entry.module_id,
                    entry.created_at.isoformat(),
                    entry.response_summary,
                    json.dumps(entry.parameters),
                ),
            )

    def get_all(self, limit: int = 50) -> List[HistoryEntry]:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, original_input, module_id, created_at,
                       response_summary, parameters
                FROM history
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            return [
                HistoryEntry(
                    id=row["id"],
                    original_input=row["original_input"],
                    module_id=row["module_id"],
                    created_at=datetime.datetime.fromisoformat(row["created_at"]),
                    response_summary=row["response_summary"],
                    parameters=json.loads(row["parameters"]),
                )
                for row in rows
            ]

    def clear(self) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM history")
