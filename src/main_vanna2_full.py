"""FastAPI application with full Vanna 2.0 Agent integration."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import logging

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.agent import AgentConfig
from vanna.servers.base import ChatHandler
from vanna.servers.fastapi.routes import register_chat_routes

from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver
from src.memory.pgvector_memory import PgVectorAgentMemory
from src.memory.embedding_service import AzureEmbeddingService
from src.tools.sql_tool import PostgresSqlRunner
from src.tools.vanna_sql_tool import VannaRunSqlTool
from src.tools.chart_generation_tool import ChartGenerationTool
from src.tools.insights_generation_tool import InsightsGenerationTool
from src.conversation import PostgresConversationStore
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global components
agent: Optional[Agent] = None
sql_runner: Optional[PostgresSqlRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global agent, sql_runner
    
    # Startup: Initialize Vanna 2.0 Agent
    logger.info("🚀 Initializing Full Vanna 2.0 Agent...")
    try:
        # Initialize conversation store
        conversation_store = PostgresConversationStore(
            connection_string=settings.pgvector_connection_string
        )
        await conversation_store.initialize()
        logger.info("✅ Conversation store initialized")
        
        # Initialize user resolver
        user_resolver = SimpleUserResolver()
        logger.info("✅ User resolver initialized")
        
        # Initialize embedding service
        embedding_service = AzureEmbeddingService(
            api_key=settings.AZURE_OPENAI_API_KEY,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            api_version=settings.AZURE_OPENAI_EMBEDDINGS_API_VERSION
        )
        
        # Initialize agent memory (not used by Vanna Agent directly, but available)
        agent_memory = PgVectorAgentMemory(
            connection_string=settings.pgvector_connection_string,
            embedding_service=embedding_service
        )
        await agent_memory.initialize()
        logger.info("✅ Agent memory initialized")
        
        # Initialize LLM service
        llm_service = AzureOpenAILlmService(
            api_key=settings.AZURE_OPENAI_API_KEY,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=settings.AZURE_OPENAI_API_VERSION
        )
        logger.info("✅ LLM service initialized")
        
        # Initialize SQL runner
        sql_runner = PostgresSqlRunner(
            connection_string=settings.data_source_connection_string
        )
        await sql_runner.initialize()
        logger.info("✅ SQL runner initialized")
        
        # Create tool registry
        tool_registry = ToolRegistry()
        
        # Register SQL tool
        sql_tool = VannaRunSqlTool(sql_runner)
        tool_registry.register_local_tool(
            sql_tool,
            access_groups=[]  # Allow all users
        )
        
        # Register chart generation tool
        chart_tool = ChartGenerationTool(llm_service)
        tool_registry.register_local_tool(
            chart_tool,
            access_groups=[]
        )
        
        # Register insights generation tool
        insights_tool = InsightsGenerationTool(llm_service, agent_memory)
        tool_registry.register_local_tool(
            insights_tool,
            access_groups=[]
        )
        
        logger.info("✅ Tool registry created with SQL, Chart, and Insights tools")
        
        # Configure Vanna Agent
        agent_config = AgentConfig(
            max_tool_iterations=10,
            stream_responses=True,
            auto_save_conversations=True,
            temperature=0.3,
            max_tokens=2048
        )
        
        # Create Vanna Agent
        # Now that PgVectorAgentMemory properly inherits from AgentMemory,
        # we can pass it to the Agent constructor
        agent = Agent(
            llm_service=llm_service,
            tool_registry=tool_registry,
            user_resolver=user_resolver,
            agent_memory=agent_memory,
            conversation_store=conversation_store,
            config=agent_config
        )
        logger.info("✅ Vanna 2.0 Agent created!")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Vanna Agent: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown: Cleanup
    logger.info("👋 Shutting down...")
    if sql_runner:
        await sql_runner.close()


app = FastAPI(
    title="Vanna 2.0 Full Agent Text-to-SQL",
    description="Natural language to SQL using Vanna 2.0 Agent with Azure OpenAI",
    version="2.0.0-full",
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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vanna 2.0 Full Agent Text-to-SQL",
        "version": "2.0.0-full",
        "status": "running",
        "features": [
            "vanna_agent",
            "conversation_history",
            "streaming",
            "tool_registry",
            "rag"
        ],
        "endpoints": {
            "chat_sse": "/api/vanna/v2/chat_sse",
            "chat_poll": "/api/vanna/v2/chat_poll",
            "health": "/health",
            "tables": "/api/tables"
        }
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
            "data_source": "AdventureWorksDW",
            "conversation_store": "PostgreSQL",
            "agent_type": "Vanna 2.0 Full Agent"
        }
    }


@app.get("/api/tables")
async def list_tables():
    """List all tables in the database."""
    if not sql_runner:
        raise HTTPException(status_code=503, detail="SQL runner not initialized")
    
    try:
        tables = await sql_runner.list_tables()
        return {"tables": tables}
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    if not sql_runner:
        raise HTTPException(status_code=503, detail="SQL runner not initialized")
    
    try:
        schema = await sql_runner.get_table_schema(table_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        return {"table": table_name, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Custom endpoint for existing UI compatibility
from pydantic import BaseModel

class QueryRequest(BaseModel):
    """Request model for custom UI."""
    question: str
    conversation_id: Optional[str] = None


@app.post("/api/query")
async def query_for_ui(request: QueryRequest):
    """
    Custom endpoint for existing UI compatibility.
    Calls Vanna Agent and returns results in expected format.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        from vanna.core.user import RequestContext
        
        # Create request context
        context = RequestContext(metadata={"source": "custom_ui"})
        
        # Send message to agent (this will handle conversation internally)
        conversation_id = request.conversation_id or ""
        
        # Collect all responses from streaming
        responses = []
        async for response in agent.send_message(
            context,
            request.question,
            conversation_id=conversation_id
        ):
            responses.append(response)
        
        # Extract data from responses
        sql = None
        results = None
        chart_config = None
        chart_type = None
        insights = None
        explanation = ""
        
        for resp in responses:
            # Look for SQL and results in tool results
            if hasattr(resp, 'tool_result'):
                tool_result = resp.tool_result
                if hasattr(tool_result, 'data') and tool_result.data:
                    data = tool_result.data
                    
                    # Check if this is SQL results
                    if isinstance(data, dict):
                        if 'sql' in data:
                            sql = data['sql']
                        if 'rows' in data and 'columns' in data:
                            results = data
                        
                        # Check if this is chart data
                        if 'chart_config' in data:
                            chart_config = data['chart_config']
                            chart_type = data.get('chart_type', 'bar')
                        
                        # Check if this is insights data
                        if 'summary' in data and 'findings' in data:
                            insights = data
            
            # Collect explanation text
            if hasattr(resp, 'content') and resp.content:
                explanation += resp.content
        
        # Build response
        response_data = {
            "question": request.question,
            "sql": sql,
            "results": results,
            "explanation": explanation.strip() if explanation else None,
            "conversation_id": conversation_id,
            "error": None
        }
        
        # Add chart if generated
        if chart_config:
            response_data["chart_config"] = chart_config
            response_data["chart_type"] = chart_type
        
        # Add insights if generated
        if insights:
            response_data["insights"] = insights
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error in UI query endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Register Vanna's chat routes
if agent:
    chat_handler = ChatHandler(agent)
    register_chat_routes(
        app,
        chat_handler,
        config={
            "dev_mode": False,
            "cdn_url": "https://img.vanna.ai/vanna-components.js"
        }
    )
    logger.info("✅ Vanna chat routes registered")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main_vanna2_full:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
