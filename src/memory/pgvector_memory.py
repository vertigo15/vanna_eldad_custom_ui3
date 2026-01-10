"""Custom AgentMemory implementation using pgvector for Vanna 2.0."""

from typing import List, Dict, Any, Optional
import asyncpg
import json
from dataclasses import dataclass
from datetime import datetime
from vanna.capabilities.agent_memory.base import AgentMemory
from vanna.capabilities.agent_memory.models import ToolMemory, ToolMemorySearchResult, TextMemory, TextMemorySearchResult


class PgVectorAgentMemory(AgentMemory):
    """
    Custom AgentMemory implementation using pgvector.
    Implements memory storage and RAG retrieval for Vanna 2.0.
    Inherits from vanna.capabilities.agent_memory.base.AgentMemory.
    """
    
    def __init__(self, connection_string: str, embedding_service):
        self.connection_string = connection_string
        self.embedding_service = embedding_service
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
    
    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: Dict[str, Any],
        context: "ToolContext",
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save tool usage to pgvector for learning."""
        from vanna.core.tool import ToolContext
        
        embedding = await self.embedding_service.embed(question)
        user_id = context.user.id if context and hasattr(context, 'user') else None
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO vanna_tool_memory 
                (question, tool_name, args, user_id, success, embedding)
                VALUES ($1, $2, $3, $4, $5, $6::vector)
            """, question, tool_name, json.dumps(args), 
                user_id, success, str(embedding))
    
    async def search_similar_usage(
        self,
        question: str,
        context: "ToolContext",
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        tool_name_filter: Optional[str] = None
    ) -> List[ToolMemorySearchResult]:
        """Search for similar past tool usage."""
        from vanna.core.tool import ToolContext
        
        embedding = await self.embedding_service.embed(question)
        
        async with self.pool.acquire() as conn:
            query = """
                SELECT 
                    question, tool_name, args,
                    1 - (embedding <=> $1::vector) as similarity
                FROM vanna_tool_memory
                WHERE success = TRUE
                  AND 1 - (embedding <=> $1::vector) >= $2
            """
            params = [str(embedding), similarity_threshold]
            
            if tool_name_filter:
                query += " AND tool_name = $" + str(len(params) + 1)
                params.append(tool_name_filter)
            
            query += " ORDER BY embedding <=> $1::vector LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
        
        results = []
        for i, row in enumerate(rows):
            results.append(ToolMemorySearchResult(
                memory=ToolMemory(
                    question=row['question'],
                    tool_name=row['tool_name'],
                    args=json.loads(row['args'])
                ),
                similarity_score=row['similarity'],
                rank=i
            ))
        return results
    
    # RAG methods for SQL generation
    
    async def search_ddl(self, question: str, limit: int = 10) -> List[str]:
        """Search relevant DDL statements."""
        embedding = await self.embedding_service.embed(question)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT ddl_text,
                       1 - (embedding <=> $1::vector) as similarity
                FROM vanna_ddl
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, str(embedding), limit)
        
        return [row['ddl_text'] for row in rows]
    
    async def search_documentation(self, question: str, limit: int = 5) -> List[str]:
        """Search relevant documentation."""
        embedding = await self.embedding_service.embed(question)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT doc_text,
                       1 - (embedding <=> $1::vector) as similarity
                FROM vanna_documentation
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, str(embedding), limit)
        
        return [row['doc_text'] for row in rows]
    
    async def search_sql_examples(self, question: str, limit: int = 5) -> List[Dict]:
        """Search similar SQL examples."""
        embedding = await self.embedding_service.embed(question)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT question, sql_query,
                       1 - (embedding <=> $1::vector) as similarity
                FROM vanna_sql_examples
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, str(embedding), limit)
        
        return [{
            'question': row['question'], 
            'sql': row['sql_query'],
            'similarity': row['similarity']
        } for row in rows]
    
    async def get_context_for_question(self, question: str) -> Dict[str, Any]:
        """
        Get all relevant context for a question (DDL, docs, SQL examples).
        This is used to enhance the LLM prompt with RAG.
        """
        ddl_statements = await self.search_ddl(question, limit=10)
        documentation = await self.search_documentation(question, limit=5)
        sql_examples = await self.search_sql_examples(question, limit=5)
        
        return {
            'ddl': ddl_statements,
            'documentation': documentation,
            'sql_examples': sql_examples
        }
    
    # Implement remaining abstract methods required by AgentMemory base class
    
    async def save_text_memory(
        self, content: str, context: "ToolContext"
    ) -> TextMemory:
        """Save a free-form text memory."""
        from vanna.core.tool import ToolContext
        import uuid
        
        memory_id = str(uuid.uuid4())
        user_id = context.user.id if context and hasattr(context, 'user') else None
        embedding = await self.embedding_service.embed(content)
        created_at = datetime.utcnow().isoformat()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO vanna_text_memory 
                (id, content, user_id, embedding, created_at)
                VALUES ($1, $2, $3, $4::vector, $5)
            """, memory_id, content, user_id, str(embedding), created_at)
        
        return TextMemory(
            id=memory_id,
            content=content,
            user_id=user_id,
            created_at=created_at
        )
    
    async def search_text_memories(
        self,
        query: str,
        context: "ToolContext",
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[TextMemorySearchResult]:
        """Search stored text memories based on a query."""
        from vanna.core.tool import ToolContext
        
        embedding = await self.embedding_service.embed(query)
        user_id = context.user.id if context and hasattr(context, 'user') else None
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, content, user_id, created_at,
                       1 - (embedding <=> $1::vector) as similarity
                FROM vanna_text_memory
                WHERE 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, str(embedding), similarity_threshold, limit)
        
        results = []
        for i, row in enumerate(rows):
            results.append(TextMemorySearchResult(
                memory=TextMemory(
                    id=row['id'],
                    content=row['content'],
                    user_id=row['user_id'],
                    created_at=row['created_at']
                ),
                similarity_score=row['similarity'],
                rank=i
            ))
        return results
    
    async def get_recent_memories(
        self, context: "ToolContext", limit: int = 10
    ) -> List[ToolMemory]:
        """Get recently added memories. Returns most recent memories first."""
        from vanna.core.tool import ToolContext
        
        user_id = context.user.id if context and hasattr(context, 'user') else None
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT question, tool_name, args, created_at
                FROM vanna_tool_memory
                WHERE success = TRUE
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
        
        return [
            ToolMemory(
                question=row['question'],
                tool_name=row['tool_name'],
                args=json.loads(row['args'])
            )
            for row in rows
        ]
    
    async def get_recent_text_memories(
        self, context: "ToolContext", limit: int = 10
    ) -> List[TextMemory]:
        """Fetch recently stored text memories."""
        from vanna.core.tool import ToolContext
        
        user_id = context.user.id if context and hasattr(context, 'user') else None
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, content, user_id, created_at
                FROM vanna_text_memory
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
        
        return [
            TextMemory(
                id=row['id'],
                content=row['content'],
                user_id=row['user_id'],
                created_at=row['created_at']
            )
            for row in rows
        ]
    
    async def delete_by_id(self, context: "ToolContext", memory_id: str) -> bool:
        """Delete a memory by its ID. Returns True if deleted, False if not found."""
        from vanna.core.tool import ToolContext
        
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM vanna_tool_memory
                WHERE id = $1
            """, memory_id)
            
            # Check if any rows were deleted
            return result != "DELETE 0"
    
    async def delete_text_memory(self, context: "ToolContext", memory_id: str) -> bool:
        """Delete a text memory by its ID. Returns True if deleted, False if not found."""
        from vanna.core.tool import ToolContext
        
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM vanna_text_memory
                WHERE id = $1
            """, memory_id)
            
            return result != "DELETE 0"
    
    async def clear_memories(
        self,
        context: "ToolContext",
        tool_name: Optional[str] = None,
        before_date: Optional[str] = None
    ) -> int:
        """Clear stored memories (tool or text). Returns number of memories deleted."""
        from vanna.core.tool import ToolContext
        
        count = 0
        
        async with self.pool.acquire() as conn:
            # Clear tool memories
            query = "DELETE FROM vanna_tool_memory WHERE 1=1"
            params = []
            
            if tool_name:
                query += " AND tool_name = $" + str(len(params) + 1)
                params.append(tool_name)
            
            if before_date:
                query += " AND created_at < $" + str(len(params) + 1)
                params.append(before_date)
            
            result = await conn.execute(query, *params) if params else await conn.execute(query)
            if result != "DELETE 0":
                count += int(result.split()[-1])
        
        return count
