"""Vanna 2.0 compatible SQL tool."""

from typing import Dict, Any, List
import json
from pydantic import BaseModel, Field

try:
    from vanna.core.tool import Tool, ToolContext, ToolResult
    from vanna.core.schema import ToolSchema, ToolParameter
    VANNA2_AVAILABLE = True
except ImportError:
    VANNA2_AVAILABLE = False
    # Fallback
    class Tool:
        pass
    class ToolContext:
        pass
    class ToolResult:
        pass
    class ToolSchema:
        pass
    class ToolParameter:
        pass

from src.tools.sql_tool import PostgresSqlRunner


class RunSqlArgs(BaseModel):
    """Arguments for run_sql tool."""
    sql: str = Field(description="The SQL query to execute")


class VannaRunSqlTool(Tool):
    """
    Vanna 2.0 compatible SQL execution tool.
    Wraps PostgresSqlRunner for use with Vanna Agent.
    """
    
    def __init__(self, sql_runner: PostgresSqlRunner):
        super().__init__()
        self.sql_runner = sql_runner
    
    @property
    def name(self) -> str:
        return "run_sql"
    
    @property
    def description(self) -> str:
        return "Execute a SQL query against the AdventureWorksDW database"
    
    @property
    def access_groups(self) -> List[str]:
        return []  # Allow all users
    
    def get_args_schema(self) -> type[RunSqlArgs]:
        return RunSqlArgs
    
    
    async def execute(
        self,
        context: ToolContext,
        args: RunSqlArgs
    ) -> ToolResult:
        """
        Execute SQL query.
        
        Args:
            context: Tool execution context (user, conversation, etc.)
            args: Validated arguments containing SQL query
            
        Returns:
            ToolResult with query results
        """
        try:
            # Execute SQL
            result = await self.sql_runner.run_sql(args.sql)
            
            if "error" in result:
                # Return error result
                if VANNA2_AVAILABLE:
                    return ToolResult(
                        success=False,
                        error=result["error"],
                        data=result
                    )
                else:
                    return {
                        "success": False,
                        "error": result["error"],
                        "data": result
                    }
            
            # Return success result
            if VANNA2_AVAILABLE:
                return ToolResult(
                    success=True,
                    data=result,
                    metadata={
                        "row_count": result.get("row_count", 0),
                        "column_count": len(result.get("columns", []))
                    }
                )
            else:
                return {
                    "success": True,
                    "data": result,
                    "metadata": {
                        "row_count": result.get("row_count", 0),
                        "column_count": len(result.get("columns", []))
                    }
                }
        
        except Exception as e:
            # Handle unexpected errors
            error_msg = str(e)
            if VANNA2_AVAILABLE:
                return ToolResult(
                    success=False,
                    error=error_msg,
                    data={"error": error_msg, "columns": [], "rows": [], "row_count": 0}
                )
            else:
                return {
                    "success": False,
                    "error": error_msg,
                    "data": {"error": error_msg, "columns": [], "rows": [], "row_count": 0}
                }
    
    def validate_permissions(self, context: ToolContext) -> bool:
        """
        Validate if user has permission to use this tool.
        
        Args:
            context: Tool execution context
            
        Returns:
            True if user has permission
        """
        # For now, allow all users
        # In production, check context.user.group_memberships
        return True
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        return await self.sql_runner.get_table_schema(table_name)
    
    async def list_tables(self) -> list:
        """List all tables in the database."""
        return await self.sql_runner.list_tables()
