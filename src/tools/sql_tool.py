"""SQL execution tool for PostgreSQL."""

import logging
import re
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Statements the agent is allowed to send to a user data source.
# Anything else — INSERT, UPDATE, DELETE, DDL, COPY, GRANT, etc. — is rejected
# before we ever reach the database. The read-only transaction wrapper inside
# `run_sql` is a second line of defence that catches anything this regex misses
# (e.g. a function call that mutates state).
_ALLOWED_LEAD_KEYWORDS = re.compile(
    r"^(SELECT|WITH)\b",
    re.IGNORECASE,
)
# Strip leading SQL comments + whitespace so a query that starts with
# "-- comment\nSELECT ..." or "/* foo */ SELECT ..." still passes the
# leading-keyword check.
_LEADING_COMMENTS = re.compile(
    r"\s*(?:--[^\n]*\n|/\*.*?\*/)\s*",
    re.DOTALL,
)


def _strip_leading_noise(sql: str) -> str:
    """Drop leading whitespace and any chained leading SQL comments."""
    text = sql or ""
    while True:
        new_text = _LEADING_COMMENTS.sub("", text, count=1)
        if new_text == text:
            break
        text = new_text
    return text.lstrip()


def is_read_only_sql(sql: str) -> bool:
    """Return True iff `sql` starts with SELECT or WITH (after stripping comments).

    This is intentionally strict: the agent's contract is to produce read-only
    queries, and the safest place to enforce that is here, before the SQL
    reaches the connection pool.
    """
    if not sql or not sql.strip():
        return False
    cleaned = _strip_leading_noise(sql)
    return bool(_ALLOWED_LEAD_KEYWORDS.match(cleaned))


class PostgresSqlRunner:
    """
    PostgreSQL SQL runner for executing queries.
    Connects to the AdventureWorksDW data source.
    """
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize connection pool."""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=10
        )
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    async def run_sql(
        self,
        sql: str,
        limit: Optional[int] = 100,
    ) -> Dict[str, Any]:
        """Execute a read-only SQL query and return its result rows.

        Two layers of safety:

        1. **Pre-check**: only SQL whose leading keyword (after stripping
           comments) is ``SELECT`` or ``WITH`` is allowed through. Anything
           else is rejected without ever touching the connection pool.
        2. **Read-only transaction**: the query runs inside a Postgres
           ``READ ONLY`` transaction. If a function call or anything the
           pre-check missed tries to mutate state, Postgres raises an error
           and the transaction rolls back automatically.

        Note: for the strongest possible guarantee, also connect with a
        Postgres role whose only privilege on the schema is ``SELECT``.
        """
        if not is_read_only_sql(sql):
            logger.warning(
                "run_sql: blocked non-read-only SQL (first 80 chars): %s",
                (sql or "").strip()[:80],
            )
            return {
                "error": (
                    "Only read-only queries are allowed. The query must start "
                    "with SELECT or WITH."
                ),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

        # Add LIMIT if not present (only safe to do for the SELECT/WITH
        # statements this runner accepts).
        if limit and "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip().rstrip(';')} LIMIT {limit}"

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    rows = await conn.fetch(sql)

            if not rows:
                return {"columns": [], "rows": [], "row_count": 0}

            columns = list(rows[0].keys())
            result_rows = [dict(row) for row in rows]
            return {
                "columns": columns,
                "rows": result_rows,
                "row_count": len(result_rows),
            }
        except asyncpg.exceptions.ReadOnlySQLTransactionError as e:
            # The READ ONLY transaction rejected something the pre-check
            # accepted (e.g. a SELECT that calls a function with side effects).
            logger.warning("run_sql: read-only transaction rejected query: %s", e)
            return {
                "error": (
                    "This query attempted to modify the database and was "
                    "blocked. Only read-only queries are allowed."
                ),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
    
    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a table."""
        sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(sql, table_name)
                return [dict(row) for row in rows]
        except Exception as e:
            return []
    
    async def list_tables(self) -> List[str]:
        """List all tables in the database."""
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(sql)
                return [row['table_name'] for row in rows]
        except Exception as e:
            return []


class RunSqlTool:
    """
    Vanna 2.0 tool wrapper for SQL execution.
    This wraps the PostgresSqlRunner for use with Vanna's agent.
    """
    
    def __init__(self, sql_runner: PostgresSqlRunner):
        self.sql_runner = sql_runner
        self.name = "run_sql"
        self.description = "Execute a SQL query against the AdventureWorksDW database"
    
    def get_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query to execute"
                        }
                    },
                    "required": ["sql"]
                }
            }
        }
    
    async def execute(self, sql: str, **kwargs) -> Dict[str, Any]:
        """Execute the SQL query."""
        return await self.sql_runner.run_sql(sql)
