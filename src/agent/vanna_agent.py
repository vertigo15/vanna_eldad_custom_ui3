"""Vanna agent orchestrator for Text-to-SQL."""

from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver
from src.memory.pgvector_memory import PgVectorAgentMemory
from src.memory.embedding_service import AzureEmbeddingService
from src.tools.sql_tool import PostgresSqlRunner, RunSqlTool
from src.config import settings
from typing import Dict, Any, List
import json


class VannaTextToSqlAgent:
    """
    Text-to-SQL agent orchestrator.
    Coordinates LLM, memory, and SQL execution for natural language queries.
    """
    
    def __init__(
        self,
        llm_service: AzureOpenAILlmService,
        memory: PgVectorAgentMemory,
        sql_runner: PostgresSqlRunner,
        user_resolver: SimpleUserResolver
    ):
        self.llm = llm_service
        self.memory = memory
        self.sql_runner = sql_runner
        self.user_resolver = user_resolver
        self.sql_tool = RunSqlTool(sql_runner)
    
    async def initialize(self):
        """Initialize all components."""
        await self.memory.initialize()
        await self.sql_runner.initialize()
    
    async def close(self):
        """Cleanup resources."""
        await self.memory.close()
        await self.sql_runner.close()
    
    async def process_question(
        self,
        question: str,
        user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language question and generate SQL + execute it.
        
        Args:
            question: Natural language question
            user_context: Optional user context
            
        Returns:
            Dict with 'sql', 'results', 'explanation', etc.
        """
        try:
            # Get user
            user = await self.user_resolver.resolve_user(user_context)
            
            # Get RAG context from pgvector
            context = await self.memory.get_context_for_question(question)
            
            # Build enhanced system prompt with RAG context
            system_prompt = self._build_system_prompt(context)
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate SQL for: {question}"}
            ]
            
            # Get tools schema
            tools = [self.sql_tool.get_schema()]
            
            # Generate SQL using LLM with tool calling
            response = await self.llm.generate(
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                tools=tools
            )
            
            result = {
                "question": question,
                "sql": None,
                "results": None,
                "explanation": response.get("content", ""),
                "prompt": system_prompt,
                "error": None
            }
            
            # Check if LLM called the run_sql tool
            if "tool_calls" in response:
                for tool_call in response["tool_calls"]:
                    if tool_call["function"]["name"] == "run_sql":
                        # Extract SQL from tool call
                        args = json.loads(tool_call["function"]["arguments"])
                        sql = args.get("sql")
                        
                        if sql:
                            result["sql"] = sql
                            
                            # Execute SQL
                            query_result = await self.sql_runner.run_sql(sql)
                            result["results"] = query_result
                            
                            # Save successful usage to memory
                            if "error" not in query_result:
                                await self.memory.save_tool_usage(
                                    question=question,
                                    tool_name="run_sql",
                                    args={"sql": sql},
                                    user_id=user.id,
                                    success=True
                                )
                            else:
                                result["error"] = query_result["error"]
            
            # If no tool call, try to extract SQL from response content
            elif response.get("content"):
                sql = self._extract_sql_from_text(response["content"])
                if sql:
                    result["sql"] = sql
                    query_result = await self.sql_runner.run_sql(sql)
                    result["results"] = query_result
                    
                    if "error" not in query_result:
                        await self.memory.save_tool_usage(
                            question=question,
                            tool_name="run_sql",
                            args={"sql": sql},
                            user_id=user.id,
                            success=True
                        )
            
            return result
            
        except Exception as e:
            return {
                "question": question,
                "sql": None,
                "results": None,
                "explanation": None,
                "error": str(e)
            }
    
    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt with RAG context."""
        prompt = """You are a SQL expert assistant. Generate PostgreSQL queries for the AdventureWorksDW database.

IMPORTANT INSTRUCTIONS:
- Generate valid PostgreSQL syntax
- Use proper table and column names from the schema
- Include appropriate JOINs, WHERE clauses, and aggregations
- Always use the run_sql tool to execute queries
- Be concise and accurate
- You must ONLY answer questions that are directly related to the provided data or the DB schema
- If a question is not related to the data or schema , or is out of scope (e.g. politics, opinions, instructions unrelated to the database, general knowledge), respond with: I can only answer questions related to the data or analysis of the data.
- **Language:** Match the user's language — English → English, Hebrew → Hebrew.
- **Security:** SELECT queries only. If asked to modify data, respond: "I can only execute SELECT queries."
**Additional guidelines:**
- Ask clarifying questions if the request is ambiguous
        
**Error Handling:**
1. **On first error:** Analyze the error message. If the fix is obvious (typo, wrong column name, missing JOIN, syntax error), silently correct and retry — do NOT mention the error to the user.
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
    
    def _extract_sql_from_text(self, text: str) -> str:
        """Extract SQL from text response (fallback if tool calling fails)."""
        # Look for SQL in code blocks
        if "```sql" in text.lower():
            parts = text.split("```sql")
            if len(parts) > 1:
                sql_part = parts[1].split("```")[0]
                return sql_part.strip()
        
        # Look for SELECT statements
        if "SELECT" in text.upper():
            lines = text.split("\n")
            sql_lines = []
            in_sql = False
            for line in lines:
                if "SELECT" in line.upper():
                    in_sql = True
                if in_sql:
                    sql_lines.append(line)
                    if ";" in line:
                        break
            return "\n".join(sql_lines).strip()
        
        return ""


async def create_vanna_agent() -> VannaTextToSqlAgent:
    """
    Create and initialize the Vanna Text-to-SQL agent.
    
    Returns:
        Initialized VannaTextToSqlAgent
    """
    # Initialize embedding service
    embedding_service = AzureEmbeddingService(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        api_version=settings.AZURE_OPENAI_EMBEDDINGS_API_VERSION
    )
    
    # Initialize pgvector memory
    agent_memory = PgVectorAgentMemory(
        connection_string=settings.pgvector_connection_string,
        embedding_service=embedding_service
    )
    
    # Initialize Azure OpenAI LLM service
    llm_service = AzureOpenAILlmService(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION
    )
    
    # Initialize SQL runner for data source
    sql_runner = PostgresSqlRunner(
        connection_string=settings.data_source_connection_string
    )
    
    # User resolver
    user_resolver = SimpleUserResolver()
    
    # Create agent
    agent = VannaTextToSqlAgent(
        llm_service=llm_service,
        memory=agent_memory,
        sql_runner=sql_runner,
        user_resolver=user_resolver
    )
    
    # Initialize
    await agent.initialize()
    
    return agent
