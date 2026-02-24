# Database

Database introspection and query execution via SQLAlchemy. Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MS SQL Server, etc.).

## Highlights

- Connection pooling with automatic health checks
- Vertical result formatting optimized for LLM consumption
- Parameterized queries for safe SQL execution
- Large results truncated at 4000 characters
- Per-URL connection pools with 1-hour recycling

## Functions

| Function | Description |
|----------|-------------|
| `db.tables(db_url, ...)` | List table names in the database |
| `db.schema(table_names, db_url)` | Get schema definitions for tables |
| `db.query(sql, db_url, ...)` | Execute SQL and return formatted results |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `db_url` | str | SQLAlchemy connection string (required) |
| `filter` | str | Substring to filter table names (tables only) |
| `ignore_case` | bool | Case-insensitive filter matching (tables only, default: False) |
| `table_names` | list[str] | Tables to inspect (schema only) |
| `params` | dict | Query parameters for safe substitution (query only) |

## Examples

```python
db_url = "postgresql://localhost/myapp"

# List all tables
db.tables(db_url=db_url)

# Filter tables
db.tables(db_url=db_url, filter="user")

# Get schema for tables
db.schema(["users", "orders"], db_url=db_url)

# Execute queries (parameterized for safety)
db.query("SELECT * FROM users LIMIT 5", db_url=db_url)
db.query(
    "SELECT * FROM users WHERE status = :status",
    db_url=db_url,
    params={"status": "active"}
)
```

## Project Configuration

Configure database connections in `onetool.yaml`:

```yaml
projects:
  myapp:
    path: /path/to/project
    attrs:
      db_url: postgresql://localhost/myapp

  demo:
    path: .
    attrs:
      db_url: sqlite:///demo/data/northwind.db
```

### Supported Databases

Any SQLAlchemy-compatible database:

- SQLite: `sqlite:///path/to/db.db`
- PostgreSQL: `postgresql://user:pass@host/db`
- MySQL: `mysql://user:pass@host/db`

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `db.max_chars` | 4000 | Maximum output characters |

```yaml
tools:
  db:
    max_chars: 8000  # Larger output
```

## Security

- Queries are read-only by default
- Use parameterized queries for user input
- Configure `max_chars` to prevent excessive output
