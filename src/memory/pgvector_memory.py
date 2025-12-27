"""Custom AgentMemory implementation using pgvector for Vanna 2.0."""

from typing import List, Dict, Any, Optional
import asyncpg
import json
from dataclasses import dataclass


@dataclass
class ToolMemory:
    """Tool memory record."""
    question: str
    tool_name: str
    args: Dict[str, Any]


@dataclass
class ToolMemorySearchResult:
    """Tool memory search result."""
    memory: ToolMemory
    similarity_score: float
    rank: int


class PgVectorAgentMemory:
    """
    Custom AgentMemory implementation using pgvector.
    Implements memory storage and RAG retrieval for Vanna 2.0.
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
        user_id: Optional[str] = None,
        success: bool = True
    ) -> None:
        """Save tool usage to pgvector for learning."""
        embedding = await self.embedding_service.embed(question)
        
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
        user_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[ToolMemorySearchResult]:
        """Search for similar past tool usage."""
        embedding = await self.embedding_service.embed(question)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    question, tool_name, args,
                    1 - (embedding <=> $1::vector) as similarity
                FROM vanna_tool_memory
                WHERE success = TRUE
                  AND 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, str(embedding), similarity_threshold, limit)
        
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
