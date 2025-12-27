"""SQL execution tool for PostgreSQL."""

import asyncpg
from typing import List, Dict, Any, Optional
import json


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
        limit: Optional[int] = 100
    ) -> Dict[str, Any]:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query to execute
            limit: Maximum number of rows to return
            
        Returns:
            Dict with 'columns', 'rows', 'row_count', and optional 'error'
        """
        try:
            # Add LIMIT if not present and it's a SELECT
            if limit and sql.strip().upper().startswith('SELECT'):
                if 'LIMIT' not in sql.upper():
                    sql = f"{sql.rstrip(';')} LIMIT {limit}"
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(sql)
                
                if not rows:
                    return {
                        "columns": [],
                        "rows": [],
                        "row_count": 0
                    }
                
                # Extract column names
                columns = list(rows[0].keys())
                
                # Convert rows to list of dicts
                result_rows = [dict(row) for row in rows]
                
                return {
                    "columns": columns,
                    "rows": result_rows,
                    "row_count": len(result_rows)
                }
                
        except Exception as e:
            return {
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0
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
