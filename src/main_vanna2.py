"""FastAPI application with Vanna 2.0 Agent integration."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
import uuid

from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver, RequestContext
from src.memory.pgvector_memory import PgVectorAgentMemory
from src.memory.embedding_service import AzureEmbeddingService
from src.tools.sql_tool import PostgresSqlRunner, RunSqlTool
from src.conversation import PostgresConversationStore, Message
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global components
conversation_store: Optional[PostgresConversationStore] = None
user_resolver: Optional[SimpleUserResolver] = None
llm_service: Optional[AzureOpenAILlmService] = None
agent_memory: Optional[PgVectorAgentMemory] = None
sql_runner: Optional[PostgresSqlRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global conversation_store, user_resolver, llm_service, agent_memory, sql_runner
    
    # Startup: Initialize components
    logger.info("🚀 Initializing Vanna 2.0 components...")
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
        
        # Initialize agent memory
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
        
        logger.info("✅ All components ready!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}")
        raise
    
    yield
    
    # Shutdown: Cleanup
    logger.info("👋 Shutting down...")
    if conversation_store:
        await conversation_store.close()
    if agent_memory:
        await agent_memory.close()
    if sql_runner:
        await sql_runner.close()


app = FastAPI(
    title="Vanna 2.0 Text-to-SQL with Conversation History",
    description="Natural language to SQL using Azure OpenAI, pgvector, and conversation tracking",
    version="2.0.0",
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
    """Request model for SQL query with conversation support."""
    question: str
    conversation_id: Optional[str] = None  # NEW: conversation tracking
    user_context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for SQL query."""
    question: str
    sql: Optional[str]
    results: Optional[Dict[str, Any]]
    explanation: Optional[str]
    conversation_id: str  # NEW: return conversation ID
    prompt: Optional[str] = None
    error: Optional[str]


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vanna 2.0 Text-to-SQL",
        "version": "2.0.0",
        "status": "running",
        "features": ["conversation_history", "agent_memory", "rag"]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "conversation_store": conversation_store is not None,
            "llm_service": llm_service is not None,
            "agent_memory": agent_memory is not None,
            "sql_runner": sql_runner is not None
        },
        "services": {
            "llm": "Azure OpenAI gpt-5.1",
            "embeddings": "text-embedding-3-large-2",
            "vector_store": "pgvector",
            "data_source": "AdventureWorksDW",
            "conversation_store": "PostgreSQL"
        }
    }


@app.post("/api/query", response_model=QueryResponse)
async def query_database(request: QueryRequest):
    """
    Process natural language question with conversation history support.
    
    Args:
        request: QueryRequest with question, optional conversation_id, and user context
        
    Returns:
        QueryResponse with SQL, results, explanation, and conversation_id
    """
    if not all([llm_service, agent_memory, sql_runner, user_resolver, conversation_store]):
        raise HTTPException(status_code=503, detail="Components not initialized")
    
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Generate or use existing conversation ID
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    logger.info(f"Processing question: {request.question} (conversation: {conversation_id})")
    
    try:
        # Resolve user
        request_context = RequestContext(metadata=request.user_context or {})
        user = await user_resolver.resolve_user(request_context)
        
        # Get conversation history
        conversation_history = []
        if request.conversation_id:
            recent_messages = await conversation_store.get_recent_messages(
                conversation_id=conversation_id,
                user_id=user.id,
                limit=5  # Last 5 messages for context
            )
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in recent_messages
            ]
        
        # Save user message
        await conversation_store.save_message(
            conversation_id=conversation_id,
            message=Message(role="user", content=request.question),
            user_id=user.id
        )
        
        # Get RAG context from agent memory
        context = await agent_memory.get_context_for_question(request.question)
        
        # Build system prompt with RAG context
        system_prompt = _build_system_prompt(context)
        
        # Build messages with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current question
        messages.append({"role": "user", "content": f"Generate SQL for: {request.question}"})
        
        # Get SQL tool schema
        sql_tool = RunSqlTool(sql_runner)
        tools = [sql_tool.get_schema()]
        
        # Generate SQL using LLM
        response = await llm_service.generate(
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
            tools=tools
        )
        
        result = {
            "question": request.question,
            "sql": None,
            "results": None,
            "explanation": response.get("content", ""),
            "conversation_id": conversation_id,
            "prompt": system_prompt,
            "error": None
        }
        
        # Check if LLM called the run_sql tool
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                if tool_call["function"]["name"] == "run_sql":
                    args = json.loads(tool_call["function"]["arguments"])
                    sql = args.get("sql")
                    
                    if sql:
                        result["sql"] = sql
                        
                        # Execute SQL
                        query_result = await sql_runner.run_sql(sql)
                        result["results"] = query_result
                        
                        # Save successful query to memory
                        if "error" not in query_result:
                            await agent_memory.save_tool_usage(
                                question=request.question,
                                tool_name="run_sql",
                                args={"sql": sql},
                                user_id=user.id,
                                success=True
                            )
                        else:
                            result["error"] = query_result["error"]
        
        # Save assistant response to conversation
        assistant_message = result["explanation"] or f"Generated SQL query"
        await conversation_store.save_message(
            conversation_id=conversation_id,
            message=Message(role="assistant", content=assistant_message),
            user_id=user.id
        )
        
        logger.info(f"Query completed: SQL={'✓' if result['sql'] else '✗'}, conversation_id={conversation_id}")
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations")
async def list_conversations(user_id: str = "default", limit: int = 50):
    """List conversations for a user."""
    if not conversation_store:
        raise HTTPException(status_code=503, detail="Conversation store not initialized")
    
    try:
        conversations = await conversation_store.list_conversations(user_id, limit)
        return {
            "conversations": [
                {
                    "id": conv.id,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "metadata": conv.metadata
                }
                for conv in conversations
            ]
        }
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user_id: str = "default"):
    """Get a conversation with all messages."""
    if not conversation_store:
        raise HTTPException(status_code=503, detail="Conversation store not initialized")
    
    try:
        conversation = await conversation_store.get_conversation(conversation_id, user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in conversation.messages
            ],
            "metadata": conversation.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


def _build_system_prompt(context: Dict[str, Any]) -> str:
    """Build system prompt with RAG context."""
    prompt = """You are a SQL expert assistant. Generate PostgreSQL queries for the AdventureWorksDW database.

IMPORTANT INSTRUCTIONS:
- Generate valid PostgreSQL syntax
- Use proper table and column names from the schema
- Include appropriate JOINs, WHERE clauses, and aggregations
- Always use the run_sql tool to execute queries
- Be concise and accurate
- You must ONLY answer questions that are directly related to the provided data or the DB schema
- If a question is not related to the data or schema, respond with: I can only answer questions related to the data or analysis of the data.
- **Language:** Match the user's language — English → English, Hebrew → Hebrew.
- **Security:** SELECT queries only. If asked to modify data, respond: "I can only execute SELECT queries."

**Error Handling:**
1. **On first error:** Analyze the error message. If the fix is obvious (typo, wrong column name, missing JOIN, syntax error), silently correct and retry.
2. **On second error (or if the fix is unclear):** Stop retrying. Briefly explain the issue and ask the user for clarification.
3. **Never retry more than once.**
"""
    
    # Add DDL context
    if context.get('ddl'):
        prompt += "\n## DATABASE SCHEMA:\n"
        for ddl in context['ddl'][:10]:
            prompt += f"{ddl}\n\n"
    
    # Add documentation context
    if context.get('documentation'):
        prompt += "\n## BUSINESS RULES:\n"
        for doc in context['documentation']:
            prompt += f"- {doc}\n"
    
    # Add SQL examples
    if context.get('sql_examples'):
        prompt += "\n## SIMILAR EXAMPLES:\n"
        for ex in context['sql_examples'][:3]:
            prompt += f"Q: {ex['question']}\nSQL: {ex['sql']}\n\n"
    
    return prompt


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main_vanna2:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
