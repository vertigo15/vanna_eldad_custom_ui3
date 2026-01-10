# Vanna 2.0 Full Agent - Maintenance Guide

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Component Details](#component-details)
- [Adding New Tools](#adding-new-tools)
- [Testing Guidelines](#testing-guidelines)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)
- [Performance Monitoring](#performance-monitoring)

---

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│                     (Flask/Streamlit)                        │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST API
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI Application                       │
│                   (main_vanna2_full.py)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     Vanna 2.0 Agent                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tool Registry                                        │   │
│  │  ├── VannaRunSqlTool (SQL execution)                 │   │
│  │  ├── ChartGenerationTool (ECharts config)            │   │
│  │  └── InsightsGenerationTool (Data analysis)          │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐  ┌─────▼──────┐  ┌─────▼────────┐
│ Azure OpenAI │  │ PostgreSQL │  │  PgVector    │
│   (LLM)      │  │   (Data)   │  │  (Memory)    │
└──────────────┘  └────────────┘  └──────────────┘
```

### Data Flow

1. **Query Request** → UI sends question to `/api/query`
2. **Agent Processing** → Vanna Agent orchestrates tool execution
3. **SQL Generation** → Agent generates SQL using RAG + LLM
4. **Query Execution** → VannaRunSqlTool executes SQL on PostgreSQL
5. **Chart Generation** → ChartGenerationTool creates ECharts config
6. **Insights Generation** → InsightsGenerationTool analyzes results
7. **Response** → Aggregated response returned to UI

---

## Component Details

### 1. Vanna Agent (`main_vanna2_full.py`)

**Purpose**: Orchestrates all tools and manages conversation flow

**Key Components**:
- `Agent`: Vanna 2.0 Agent instance
- `ToolRegistry`: Registry of available tools
- `ConversationStore`: PostgreSQL-based conversation storage
- `AgentMemory`: PgVector-based RAG memory

**Configuration**:
```python
agent_config = AgentConfig(
    max_tool_iterations=10,
    stream_responses=True,
    auto_save_conversations=True,
    temperature=0.3,
    max_tokens=2048
)
```

### 2. Tools

#### VannaRunSqlTool (`src/tools/vanna_sql_tool.py`)
- **Purpose**: Execute SQL queries on PostgreSQL
- **Inputs**: `sql` (string)
- **Outputs**: `{sql, rows, columns}`
- **Error Handling**: Returns structured errors for invalid SQL

#### ChartGenerationTool (`src/tools/chart_generation_tool.py`)
- **Purpose**: Generate ECharts configuration from query results
- **Inputs**: `columns`, `column_names`, `data`, `chart_type`
- **Outputs**: `{chart_config, chart_type}`
- **Features**:
  - Auto-detect chart type (bar, line, pie, scatter, area)
  - Smart number formatting (K/M/B abbreviations)
  - Date consolidation (YYYY/MM format)
  - Currency/percentage auto-detection

#### InsightsGenerationTool (`src/tools/insights_generation_tool.py`)
- **Purpose**: Generate insights from query results
- **Inputs**: `dataset`, `question`
- **Outputs**: `{summary, findings, suggestions}`
- **Features**:
  - Statistical analysis (min, max, mean, median)
  - Pattern detection
  - Actionable suggestions

### 3. Storage

#### PostgreSQL
- **Database**: AdventureWorksDW (or configured data source)
- **Connection**: Via SQLAlchemy
- **Tables**: Business data tables

#### PgVector
- **Database**: Same PostgreSQL instance, different database
- **Tables**:
  - `conversations`: Conversation metadata
  - `conversation_messages`: Message history
  - `embeddings`: Vector embeddings for RAG

---

## Adding New Tools

### Step-by-Step Guide

#### 1. Create Tool Class

Create new file `src/tools/your_tool.py`:

```python
from typing import Any, Dict
from vanna.core.tool import Tool, ToolContext, ToolResult

class YourTool(Tool):
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.name = "your_tool_name"
        self.description = "What your tool does"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            }
        }
    
    async def execute(
        self,
        context: ToolContext,
        param1: str
    ) -> ToolResult:
        try:
            # Your tool logic here
            result = your_processing(param1)
            
            return ToolResult(
                success=True,
                data=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
```

#### 2. Register Tool

In `src/main_vanna2_full.py`, add:

```python
from src.tools.your_tool import YourTool

# In lifespan() function, after creating tool_registry:
your_tool = YourTool(llm_service)
tool_registry.register_local_tool(
    your_tool,
    access_groups=[]  # Or specific groups
)
```

#### 3. Write Tests

Create `tests/test_your_tool.py`:

```python
import pytest
from unittest.mock import AsyncMock
from src.tools.your_tool import YourTool

@pytest.mark.asyncio
async def test_your_tool():
    mock_llm = AsyncMock()
    tool = YourTool(mock_llm)
    
    result = await tool.execute(
        context=mock_context,
        param1="test"
    )
    
    assert result.success is True
```

#### 4. Update Documentation

Add your tool to this guide and update API docs.

---

## Testing Guidelines

### Running Tests

**Unit Tests**:
```bash
pytest tests/test_tools.py -v
```

**Integration Tests** (requires test DB):
```bash
pytest tests/test_integration.py -v -m integration
```

**All Tests with Coverage**:
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Test Structure

```
tests/
├── __init__.py
├── test_tools.py           # Unit tests for tools
├── test_integration.py     # End-to-end workflow tests
└── conftest.py             # Shared fixtures (if needed)
```

### Writing Good Tests

**DO**:
- ✅ Mock external dependencies (LLM, DB)
- ✅ Test happy path and error cases
- ✅ Use descriptive test names
- ✅ Test with realistic data
- ✅ Verify both success and error responses

**DON'T**:
- ❌ Make real LLM calls in tests (expensive, slow)
- ❌ Rely on external services
- ❌ Test multiple things in one test
- ❌ Use production credentials

---

## Troubleshooting

### Common Issues

#### 1. Charts Not Displaying

**Symptom**: UI shows "No chart generated"

**Possible Causes**:
- ChartGenerationTool not registered
- LLM returning invalid JSON
- Data not suitable for visualization

**Solution**:
```bash
# Check logs
docker logs vanna-app | grep "chart"

# Verify tool registration
curl http://localhost:8000/health

# Test chart endpoint directly
curl -X POST http://localhost:8000/api/generate-chart \
  -H "Content-Type: application/json" \
  -d '{"columns": [...], "data": [...]}'
```

#### 2. Insights Not Generated

**Symptom**: Empty insights returned

**Possible Causes**:
- Dataset too small (<2 rows)
- LLM timeout
- AgentMemory not initialized

**Solution**:
```bash
# Check dataset size
# Insights require at least 2 rows of data

# Check LLM service
docker logs vanna-app | grep "LLM service"

# Verify agent memory
docker logs vanna-app | grep "Agent memory initialized"
```

#### 3. Conversation History Not Saved

**Symptom**: Follow-up questions don't use context

**Possible Causes**:
- ConversationStore not initialized
- PostgreSQL connection issue
- Missing conversation_id in requests

**Solution**:
```bash
# Check PostgreSQL
docker logs pgvector-db

# Check conversation tables
docker exec -it pgvector-db psql -U vannauser -d pgvector \
  -c "SELECT * FROM conversations LIMIT 5;"

# Verify conversation_id in requests
# UI must send same conversation_id for follow-ups
```

#### 4. Database Connection Errors

**Symptom**: "Connection refused" or timeout errors

**Possible Causes**:
- PostgreSQL not running
- Wrong connection string
- Network issues in Docker

**Solution**:
```bash
# Check containers
docker ps

# Test database connection
docker exec -it vanna-app python -c \
  "import asyncpg; asyncpg.connect('postgresql://...')"

# Check .env file
cat .env | grep PGVECTOR_HOST
# Should be 'pgvector-db' for Docker, 'localhost' for local
```

### Log Locations

**Application Logs**:
```bash
docker logs vanna-app
docker logs -f vanna-app  # Follow mode
```

**Database Logs**:
```bash
docker logs pgvector-db
```

**Filter Logs by Component**:
```bash
# Chart generation
docker logs vanna-app | grep "ChartGenerationTool"

# Insights generation
docker logs vanna-app | grep "InsightsGenerationTool"

# SQL execution
docker logs vanna-app | grep "VannaRunSqlTool"

# Errors only
docker logs vanna-app | grep "ERROR"
```

---

## Deployment

### Docker Deployment

#### 1. Build Image
```bash
docker-compose build
```

#### 2. Start Services
```bash
docker-compose up -d
```

#### 3. Verify Deployment
```bash
# Check health
curl http://localhost:8000/health

# Test query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show total sales"}'
```

### Environment Variables

Required in `.env`:
```bash
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# PostgreSQL
DATA_SOURCE_CONNECTION_STRING=postgresql://...
PGVECTOR_CONNECTION_STRING=postgresql://...

# App Settings
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/api/tables
```

---

## Performance Monitoring

### Metrics to Track

1. **Query Latency**
   - Target: <5 seconds per query
   - Measure: Time from question to results

2. **LLM Token Usage**
   - Track tokens per request
   - Monitor costs

3. **Database Query Performance**
   - Check slow queries
   - Optimize indexes if needed

4. **Memory Usage**
   - Monitor Docker container memory
   - Watch for memory leaks

### Performance Tips

**Optimization Strategies**:

1. **Caching**
   - Cache frequent queries
   - Cache chart configurations
   - Cache insights for repeated data

2. **Connection Pooling**
   - Already configured in SQLAlchemy
   - Adjust pool size if needed

3. **Batch Processing**
   - Process multiple tool calls in parallel
   - Use async operations

4. **LLM Optimization**
   - Reduce max_tokens for faster responses
   - Use lower temperature for deterministic results
   - Cache embeddings in PgVector

### Monitoring Commands

```bash
# Container stats
docker stats vanna-app pgvector-db

# Database connections
docker exec -it pgvector-db psql -U vannauser -d postgres \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Application metrics (if implemented)
curl http://localhost:8000/metrics
```

---

## Maintenance Schedule

### Daily
- Check application logs for errors
- Monitor query response times

### Weekly
- Review LLM token usage and costs
- Check database disk usage
- Backup conversation history

### Monthly
- Update dependencies
- Review and optimize slow queries
- Archive old conversations

---

## Support & Contact

For issues or questions:
1. Check this maintenance guide
2. Review logs for error messages
3. Consult the implementation plan document
4. Check Vanna 2.0 documentation: https://docs.vanna.ai

---

## Version History

- **v2.0.0-full** (Current): Full Vanna 2.0 Agent with tools
  - ChartGenerationTool
  - InsightsGenerationTool
  - Conversation history
  - RAG-based memory

- **v2.0.0**: Vanna 2.0 with custom orchestration
- **v1.0.0**: Original implementation

---

*Last Updated: 2026-01-10*
