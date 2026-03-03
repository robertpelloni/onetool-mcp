"""Integration tests for the db tool pack.

Tests all three tools (tables, schema, query) against a real SQLite database
created in memory. No network or API keys required — SQLAlchemy must be installed.

Run:
  uv run pytest tests/integration/tools/test_db.py -m integration -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.tools]


def _require_sqlalchemy() -> None:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        pytest.fail("sqlalchemy not installed — install with: pip install onetool-mcp[dev]")


@pytest.fixture(scope="module")
def db_url() -> str:
    """Create a temp SQLite database with sample schema and data; return its URL."""
    _require_sqlalchemy()
    import sqlalchemy as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        url = f"sqlite:///{db_path}"

        engine = sa.create_engine(url)
        with engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    active INTEGER DEFAULT 1
                )
            """))
            conn.execute(sa.text("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    amount REAL NOT NULL,
                    created_at TEXT
                )
            """))
            conn.execute(sa.text("""
                INSERT INTO users (name, email, active) VALUES
                    ('Alice', 'alice@example.invalid', 1),
                    ('Bob',   'bob@example.invalid',   1),
                    ('Carol', 'carol@example.invalid', 0)
            """))
            conn.execute(sa.text("""
                INSERT INTO orders (user_id, amount, created_at) VALUES
                    (1, 99.99,  '2024-01-01'),
                    (1, 149.50, '2024-02-15'),
                    (2, 29.00,  '2024-03-10')
            """))
        engine.dispose()

        yield url


class TestTables:
    """db.tables() lists tables in the database."""

    def test_lists_all_tables(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.tables(db_url=db_url))
        assert isinstance(result, list)
        assert set(result) == {"users", "orders"}

    def test_filter_by_substring(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.tables(db_url=db_url, filter="user"))
        assert result == ["users"]

    def test_filter_case_insensitive(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.tables(db_url=db_url, filter="USER", ignore_case=True))
        assert result == ["users"]

    def test_filter_no_match(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.tables(db_url=db_url, filter="nonexistent"))
        assert result == []

    def test_empty_db_url_returns_error(self) -> None:
        from otdev.tools import db

        result = json.loads(db.tables(db_url=""))
        assert "error" in result


class TestSchema:
    """db.schema() returns column and relationship info for tables."""

    def test_single_table_schema(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.schema(table_names=["users"], db_url=db_url))
        assert isinstance(result, list) and len(result) == 1

        tbl = result[0]
        assert tbl["table_name"] == "users"

        col_names = [c["name"] for c in tbl["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names
        assert "active" in col_names

        # id should be the primary key
        id_col = next(c for c in tbl["columns"] if c["name"] == "id")
        assert id_col["primary_key"] is True

    def test_table_with_foreign_key(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.schema(table_names=["orders"], db_url=db_url))
        tbl = result[0]
        assert tbl["table_name"] == "orders"

        # Foreign key from user_id → users.id
        rels = tbl["relationships"]
        assert len(rels) >= 1
        fk = rels[0]
        assert "user_id" in fk["constrained_columns"]
        assert fk["referred_table"] == "users"

    def test_multiple_tables(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.schema(table_names=["users", "orders"], db_url=db_url))
        assert len(result) == 2
        names = {t["table_name"] for t in result}
        assert names == {"users", "orders"}

    def test_missing_table_returns_error_entry(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.schema(table_names=["nonexistent"], db_url=db_url))
        assert result[0]["table_name"] == "nonexistent"
        assert "error" in result[0]

    def test_empty_table_names_returns_error(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.schema(table_names=[], db_url=db_url))
        assert "error" in result


class TestQuery:
    """db.query() executes SQL and returns results."""

    def test_select_all_rows(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.query(sql="SELECT * FROM users", db_url=db_url))
        assert result["row_count"] == 3
        assert len(result["rows"]) == 3
        assert result["truncated"] is False

    def test_select_with_where(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(
            db.query(sql="SELECT name FROM users WHERE active = 0", db_url=db_url)
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "Carol"

    def test_parameterized_query(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(
            db.query(
                sql="SELECT * FROM users WHERE name = :name",
                db_url=db_url,
                params={"name": "Alice"},
            )
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "Alice"

    def test_aggregation(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(
            db.query(sql="SELECT COUNT(*) AS cnt FROM orders", db_url=db_url)
        )
        assert result["rows"][0]["cnt"] == 3

    def test_join(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(
            db.query(
                sql=(
                    "SELECT u.name, SUM(o.amount) AS total "
                    "FROM users u JOIN orders o ON u.id = o.user_id "
                    "GROUP BY u.id ORDER BY u.name"
                ),
                db_url=db_url,
            )
        )
        assert result["row_count"] == 2
        names = [r["name"] for r in result["rows"]]
        assert "Alice" in names and "Bob" in names

    def test_empty_result(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(
            db.query(sql="SELECT * FROM users WHERE id = 9999", db_url=db_url)
        )
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_invalid_sql_returns_error(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.query(sql="SELECT * FROM no_such_table", db_url=db_url))
        assert "error" in result

    def test_empty_sql_returns_error(self, db_url: str) -> None:
        from otdev.tools import db

        result = json.loads(db.query(sql="", db_url=db_url))
        assert "error" in result
