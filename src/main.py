"""FastAPI application for Vanna 2.0 Text-to-SQL."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from src.agent.vanna_agent import create_vanna_agent, VannaTextToSqlAgent
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global agent instance
agent: Optional[VannaTextToSqlAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global agent
    
    # Startup: Initialize Vanna agent
    logger.info("🚀 Initializing Vanna Text-to-SQL Agent...")
    try:
        agent = await create_vanna_agent()
        logger.info("✅ Vanna Agent ready!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
        raise
    
    yield
    
    # Shutdown: Cleanup
    logger.info("👋 Shutting down...")
    if agent:
        await agent.close()


app = FastAPI(
    title="Vanna 2.0 Text-to-SQL",
    description="Natural language to SQL using Azure OpenAI and pgvector",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class QueryRequest(BaseModel):
    """Request model for SQL query."""
    question: str
    user_context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for SQL query."""
    question: str
    sql: Optional[str]
    results: Optional[Dict[str, Any]]
    explanation: Optional[str]
    prompt: Optional[str] = None
    error: Optional[str]


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vanna 2.0 Text-to-SQL",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "services": {
            "llm": "Azure OpenAI gpt-5.1",
            "embeddings": "text-embedding-3-large-2",
            "vector_store": "pgvector",
            "data_source": "AdventureWorksDW"
        }
    }


@app.post("/api/query", response_model=QueryResponse)
async def query_database(request: QueryRequest):
    """
    Process natural language question and execute SQL.
    
    Args:
        request: QueryRequest with question and optional user context
        
    Returns:
        QueryResponse with SQL, results, and explanation
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    logger.info(f"Processing question: {request.question}")
    
    try:
        result = await agent.process_question(
            question=request.question,
            user_context=request.user_context or {}
        )
        
        logger.info(f"Query result: SQL={'✓' if result['sql'] else '✗'}, "
                   f"Results={'✓' if result['results'] else '✗'}, "
                   f"Error={'✗' if result['error'] else '✓'}")
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables")
async def list_tables():
    """List all tables in the database."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        tables = await agent.sql_runner.list_tables()
        return {"tables": tables}
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        schema = await agent.sql_runner.get_table_schema(table_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        return {"table": table_name, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
