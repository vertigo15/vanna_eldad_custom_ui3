# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Start Docker Containers

```bash
docker-compose up -d
```

Wait for services to be healthy (~30 seconds):

```bash
docker ps
```

You should see:
- `vanna-app` (port 8000)
- `pgvector-db` (port 5433)

### Step 2: Load Training Data

```bash
docker exec -it vanna-app python scripts/load_training_data.py
```

Expected output:
```
======================================================================
VANNA TEXT-TO-SQL TRAINING DATA LOADER
======================================================================

🔧 Initializing Azure OpenAI embedding service...
✅ Embedding service ready

🔧 Connecting to pgvector database...
✅ Connected to pgvector

📥 Loading DDL statements...
  ✓ DimCustomer
  ✓ FactInternetSales
  ✓ DimProduct
  ✓ DimDate
  ✓ DimGeography
✅ Loaded 5 DDL statements

📥 Loading documentation...
  ✓ Customer Segmentation
  ✓ Sales Metrics
  ✓ Date Dimension
  ✓ Product Information
  ✓ Geography Data
✅ Loaded 5 documentation entries

📥 Loading SQL examples...
  ✓ What is the total revenue?
  ✓ Show me top 10 customers by total purchases
  ✓ How many high-value customers do we have?
  ✓ What are the total sales by year?
  ✓ Show me the top 5 products by revenue
  ✓ What is the average order value?
  ✓ How many orders were placed in 2023?
  ✓ Show sales by country
✅ Loaded 8 SQL examples

======================================================================
SUMMARY
======================================================================
  DDL Statements:  5
  Documentation:   5
  SQL Examples:    8
  Total:           18

✅ Training data loaded successfully!
======================================================================
```

### Step 3: Test Queries

**Test 1: Health Check**

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "agent_ready": true,
  "services": {
    "llm": "Azure OpenAI gpt-5.1",
    "embeddings": "text-embedding-3-large-2",
    "vector_store": "pgvector",
    "data_source": "AdventureWorksDW"
  }
}
```

**Test 2: Simple Query**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'
```

**Test 3: Complex Query**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me top 10 customers by total purchases"}'
```

**Test 4: List Tables**

```bash
curl http://localhost:8000/api/tables
```

## 🎯 Sample Questions to Try

Copy and paste these commands:

```bash
# Total revenue
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'

# Top customers
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me top 10 customers by total purchases"}'

# High-value customers
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many high-value customers do we have?"}'

# Sales by year
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the total sales by year?"}'

# Top products
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me the top 5 products by revenue"}'

# Average order value
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the average order value?"}'

# Sales by country
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show sales by country"}'
```

## 📊 Access Logs

View real-time logs:

```bash
# Application logs
docker logs -f vanna-app

# pgvector logs
docker logs -f pgvector-db
```

## 🛑 Stop Services

```bash
docker-compose down
```

To also remove volumes (clears training data):

```bash
docker-compose down -v
```

## 🐛 Troubleshooting

### Services not starting?

```bash
# Check status
docker-compose ps

# View logs
docker-compose logs

# Restart
docker-compose restart
```

### Training data not loading?

```bash
# Check files exist
docker exec -it vanna-app ls -la /app/training_data

# Check pgvector is running
docker exec -it pgvector-db psql -U vanna -d vanna_vectors -c "\dt"
```

### Can't connect to AdventureWorksDW?

Check `.env` file:
- `DATA_SOURCE_HOST`
- `DATA_SOURCE_USER`
- `DATA_SOURCE_PASSWORD`
- `DATA_SOURCE_DB`

### Azure OpenAI errors?

Check `.env` file:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME`

## 📚 Next Steps

1. **Explore API**: Visit http://localhost:8000/docs for Swagger UI
2. **Add Training Data**: Add more DDL, docs, and examples to `training_data/`
3. **Customize**: Modify `src/agent/vanna_agent.py` to adjust behavior
4. **Monitor**: Check logs for query performance and errors

## 🎉 Success!

You now have a fully functional Text-to-SQL system powered by:
- **Vanna 2.0** architecture
- **Azure OpenAI** GPT-5.1
- **pgvector** for RAG
- **AdventureWorksDW** PostgreSQL database

Ask natural language questions and get SQL + results instantly!
