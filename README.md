# Vanna 2.0 Text-to-SQL Application

A production-ready **Text-to-SQL** application using **Vanna 2.0** architecture with **Azure OpenAI** and **pgvector** for natural language queries against AdventureWorksDW PostgreSQL database.

## Features

- 🤖 **Vanna 2.0 Architecture**: Custom agent orchestrator with RAG-based SQL generation
- 🔵 **Azure OpenAI Integration**: GPT-5.1 for LLM, text-embedding-3-large-2 for embeddings
- 📊 **pgvector Storage**: Vector database for DDL, documentation, and SQL examples
- 🐘 **PostgreSQL Support**: Query AdventureWorksDW database with natural language
- 🚀 **FastAPI Backend**: RESTful API with health checks and query endpoints
- 🎨 **Web UI**: Beautiful, modern interface for asking questions (NEW!)
- 🐳 **Docker Compose**: Complete containerized setup

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose                               │
│  ┌──────────────┐        ┌──────────────┐     ┌─────────────┐  │
│  │  vanna-ui    │───────▶│  vanna-app   │────▶│ pgvector-db │  │
│  │  (Flask UI)  │        │  (FastAPI)   │     │ (Vectors)   │  │
│  │  Port: 8501  │        │  Port: 8000  │     │ Port: 5433  │  │
│  └──────────────┘        └──────────────┘     └─────────────┘  │
│                                 │                                │
│                                 ▼                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Azure OpenAI (gpt-5.1 + embeddings)                       │ │
│  │ AdventureWorksDW PostgreSQL (Data Source)                 │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker Desktop
- Azure OpenAI API access
- AdventureWorksDW PostgreSQL database

### 1. Start Services

```bash
docker-compose up -d
```

This will start:
- **pgvector-db**: Vector database on port 5433
- **vanna-app**: FastAPI application on port 8000
- **vanna-ui**: Web UI on port 8501

### 2. Load Training Data

```bash
docker exec -it vanna-app python scripts/load_training_data.py
```

This loads:
- 5 DDL statements
- 5 documentation entries
- 8 SQL example pairs

### 3. Access the UI

Open your browser and navigate to:

**http://localhost:8501**

You'll see a beautiful web interface where you can:
- Ask questions in natural language
- View generated SQL
- See query results in formatted tables
- Browse available database tables
- Try sample questions

**See [UI_README.md](UI_README.md) for detailed UI documentation.**

### 4. Test the API (Optional)

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Query Database:**
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'
```

**List Tables:**
```bash
curl http://localhost:8000/api/tables
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/api/query` | POST | Process natural language query |
| `/api/tables` | GET | List all tables |
| `/api/schema/{table}` | GET | Get table schema |

### Example Query Request

```json
{
  "question": "Show me top 10 customers by total purchases"
}
```

### Example Query Response

```json
{
  "question": "Show me top 10 customers by total purchases",
  "sql": "SELECT c.FirstName, c.LastName, SUM(f.SalesAmount) as TotalPurchases\nFROM FactInternetSales f\nJOIN DimCustomer c ON f.CustomerKey = c.CustomerKey\nGROUP BY c.CustomerKey, c.FirstName, c.LastName\nORDER BY TotalPurchases DESC\nLIMIT 10;",
  "results": {
    "columns": ["firstname", "lastname", "totalpurchases"],
    "rows": [...],
    "row_count": 10
  },
  "explanation": "Generated SQL query to find top customers",
  "error": null
}
```

## Project Structure

```
venna_test3/
├── docker-compose.yml          # Docker services configuration
├── Dockerfile                  # Application container
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
├── src/
│   ├── config.py              # Configuration from .env
│   ├── main.py                # FastAPI application
│   ├── agent/
│   │   ├── vanna_agent.py     # Agent orchestrator
│   │   ├── llm_service.py     # Azure OpenAI LLM
│   │   └── user_resolver.py   # User management
│   ├── memory/
│   │   ├── pgvector_memory.py # Custom AgentMemory
│   │   └── embedding_service.py # Azure embeddings
│   └── tools/
│       └── sql_tool.py        # SQL execution tool
├── training_data/
│   ├── ddl.json               # Database schema
│   ├── documentation.json     # Business rules
│   └── sql_examples.json      # Example queries
└── scripts/
    ├── init_pgvector.sql      # Database initialization
    └── load_training_data.py  # Training data loader
```

## How It Works

### 1. RAG-Based SQL Generation

When a user asks a question:

1. **Embedding**: Question is embedded using Azure OpenAI
2. **Retrieval**: pgvector searches for:
   - Relevant DDL statements (schema)
   - Business documentation
   - Similar SQL examples
3. **Augmentation**: Context is injected into LLM prompt
4. **Generation**: Azure OpenAI GPT-5.1 generates SQL
5. **Execution**: SQL runs against AdventureWorksDW
6. **Learning**: Successful queries saved to memory

### 2. Vector Storage

pgvector stores embeddings for:

- **vanna_ddl**: Database schema (3072-dim vectors)
- **vanna_documentation**: Business rules
- **vanna_sql_examples**: Question-SQL pairs
- **vanna_tool_memory**: Past successful queries

### 3. Components

- **VannaTextToSqlAgent**: Main orchestrator
- **AzureOpenAILlmService**: GPT-5.1 for SQL generation
- **AzureEmbeddingService**: text-embedding-3-large-2
- **PgVectorAgentMemory**: Custom memory with RAG
- **PostgresSqlRunner**: Execute SQL on data source

## Configuration

All configuration is in `.env`:

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.1
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large-2

# Data Source (AdventureWorksDW)
DATA_SOURCE_HOST=your-postgres.database.azure.com
DATA_SOURCE_DB=AdventureWorksDW
DATA_SOURCE_USER=admin
DATA_SOURCE_PASSWORD=password

# pgvector (local)
PGVECTOR_HOST=pgvector-db
PGVECTOR_DB=vanna_vectors
PGVECTOR_USER=vanna
PGVECTOR_PASSWORD=vanna_secure_password_123
```

## Development

### Run Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Update .env (set PGVECTOR_HOST=localhost)
# Start pgvector separately

# Run application
python -m uvicorn src.main:app --reload
```

### View Logs

```bash
# Application logs
docker logs -f vanna-app

# pgvector logs
docker logs -f pgvector-db
```

### Stop Services

```bash
docker-compose down

# With volume cleanup
docker-compose down -v
```

## Sample Questions

Try these natural language queries:

- "What is the total revenue?"
- "Show me top 10 customers by total purchases"
- "How many high-value customers do we have?"
- "What are the total sales by year?"
- "Show me the top 5 products by revenue"
- "What is the average order value?"
- "Show sales by country"

## Troubleshooting

### pgvector connection failed

Ensure pgvector container is healthy:
```bash
docker ps
docker logs pgvector-db
```

### Azure OpenAI 401 Unauthorized

Check API key and endpoint in `.env`

### Training data not loading

Check file paths and permissions:
```bash
docker exec -it vanna-app ls -la /app/training_data
```

### SQL execution errors

Verify AdventureWorksDW connection:
```bash
curl http://localhost:8000/api/tables
```

## License

MIT License

## Contributing

Contributions welcome! Please open issues and pull requests.
