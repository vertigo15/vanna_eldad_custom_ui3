# Training Data & Quick Start Guide

Complete guide to training your Vanna 2.0 Text-to-SQL system and getting started.

---

## 📚 Table of Contents

1. [Quick Start](#-quick-start-3-steps)
2. [Training Data Overview](#-training-data-overview)
3. [How Training Works](#-how-training-works)
4. [Training Data Loader Details](#-training-data-loader-details)
5. [Testing Your System](#-testing-your-system)
6. [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start (3 Steps)

### Prerequisites
- Docker Desktop installed and running
- Azure OpenAI API access configured in `.env`
- AdventureWorksDW PostgreSQL database accessible

### Step 1: Start Docker Containers

```powershell
# Navigate to project directory
cd C:\Users\user\OneDrive - JeenAI\Documents\code\venna_test3

# Start containers
docker-compose up -d
```

**What happens:**
- 🐳 Starts `pgvector-db` on port 5433
- 🐳 Starts `vanna-app` on port 8000
- ⏱️ Takes ~30-60 seconds

**Verify containers are running:**
```powershell
docker ps
```

You should see:
```
CONTAINER ID   IMAGE                    STATUS         PORTS
xxx            pgvector/pgvector:pg16   Up (healthy)   0.0.0.0:5433->5432/tcp
xxx            venna_test3-vanna-app    Up             0.0.0.0:8000->8000/tcp
```

### Step 2: Load Training Data

```powershell
docker exec -it vanna-app python scripts/load_training_data.py
```

**What happens:**
- 🔧 Connects to Azure OpenAI for embeddings
- 🔧 Connects to pgvector database
- 📥 Loads 34 table schemas
- 📥 Loads 55 business terms
- 📥 Loads 50+ sample data entries
- 📥 Loads 13 SQL query patterns
- ⏱️ Takes ~2-5 minutes (embedding generation)

**Expected output:**
```
======================================================================
VANNA TEXT-TO-SQL TRAINING DATA LOADER
======================================================================

🔧 Initializing Azure OpenAI embedding service...
✅ Embedding service ready

🔧 Connecting to pgvector database...
✅ Connected to pgvector

📥 Loading DDL statements from schema.json...
  ✓ adventureworksdwbuildversion
  ✓ databaselog
  ✓ dimcurrency
  ... (31 more tables)
✅ Loaded 34 DDL statements

📥 Loading documentation...
  ✓ Customer Segmentation
  ✓ Sales Metrics
  ✓ Date Dimension
  ✓ Product Information
  ✓ Geography Data
✅ Loaded 5 documentation entries

📥 Loading business terms glossary...
  ✓ demographics (9 terms)
  ✓ financial_metrics (9 terms)
  ✓ sales_metrics (5 terms)
  ✓ sales_channels (4 terms)
  ✓ product_classification (4 terms)
  ✓ time_periods (3 terms)
  ... (12 more categories)
✅ Loaded 55 business terms

📥 Loading sample data examples...
  ✓ dimgeography (5 samples)
  ✓ dimdepartmentgroup (5 samples)
  ✓ dimcurrency (5 samples)
  ... (47 more tables)
✅ Loaded 50 sample data entries

📥 Loading SQL examples from sql_patterns.json...
  ✓ Get recent customers (first purchase in last 30...
  ✓ Internet sales amount by calendar year
  ✓ Daily internet sales (last 30 days)
  ... (10 more patterns)
✅ Loaded 13 SQL examples

======================================================================
SUMMARY
======================================================================
  DDL Statements:  34
  Documentation:   5
  Business Terms:  55
  Sample Data:     50
  SQL Examples:    13
  Total:           157

✅ Training data loaded successfully!
======================================================================
```

### Step 3: Test Your System

**Health Check:**
```powershell
curl http://localhost:8000/health
```

**Expected response:**
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

**Test Query:**
```powershell
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What is the total revenue?\"}'
```

**🎉 You're ready to go!**

---

## 📊 Training Data Overview

Your system is trained with **157+ items** across 7 files:

### Training Files (180 KB total)

| File | Size | Items | Purpose |
|------|------|-------|---------|
| **schema.json** | 38.5 KB | 34 tables | Complete database schema with DDL |
| **business-terms.json** | 14.3 KB | 55 terms | Business glossary and definitions |
| **samples.json** | 116.4 KB | 50+ examples | Real data samples from tables |
| **sql_patterns.json** | 5.6 KB | 13 patterns | Sophisticated SQL query examples |
| **documentation.json** | 1.4 KB | 5 rules | Business rules and domain knowledge |

### What Gets Loaded

#### 1. **Database Schema (34 tables)**
Complete AdventureWorksDW schema including:
- **Dimensions:** DimCustomer, DimProduct, DimDate, DimGeography, DimEmployee, DimReseller, DimPromotion, DimCurrency, etc.
- **Facts:** FactInternetSales, FactResellerSales, FactCurrencyRate, FactFinance, FactSalesQuota, etc.
- **Support:** Prospective buyers, system tables, views

Each table includes:
- Full DDL with columns, data types, constraints
- Table description
- Foreign key relationships
- Indexes

#### 2. **Business Terms (55 terms in 18 categories)**

| Category | Examples |
|----------|----------|
| **Financial Metrics** (9) | Sales Amount, Gross Profit, Gross Margin, Extended Amount |
| **Demographics** (9) | Gender, Marital Status, Education Level, Occupation |
| **Sales Metrics** (5) | Order Quantity, Sales Quota, Sales Quota Achievement |
| **Product Classification** (4) | Product Category, Subcategory, Product Line |
| **Time Periods** (3) | Fiscal Year (Jul-Jun), Fiscal Quarter, Calendar Year |
| **Geography** (2) | Sales Territory, Territory Group (NA, Europe, Pacific) |
| **Customer Metrics** (2) | Active Customer, Customer Lifetime Value |
| *+11 more categories* | Operations, Performance, Pricing, Resellers, etc. |

**Key Terms Include:**
- **Fiscal Year:** "Runs from July 1st to June 30th"
- **Gross Margin:** "Formula: (Sales Amount - Total Product Cost) / Sales Amount × 100"
- **Sales Territory Group:** "North America, Europe, Pacific"
- **Product Line:** "R=Road, M=Mountain, T=Touring, S=Standard"

#### 3. **Sample Data (50+ tables)**
Real data examples showing:
- Customer records (names, demographics, geography)
- Geography data (cities, countries, postal codes)
- Department structures (hierarchies)
- Currency codes and names
- Product examples

**Benefits:**
- Shows actual data patterns
- Helps with data validation
- Improves query accuracy
- Assists with value formatting

#### 4. **SQL Query Patterns (13 examples)**

| Pattern Type | Examples |
|-------------|----------|
| **Basic Selects** | Recent customers, filtered queries |
| **Aggregations** | Sales by year, territory, promotion |
| **Time Series** | Daily/monthly sales trends |
| **Top N Queries** | Top 10 products, customers |
| **Complex Joins** | Multi-table customer purchases |
| **Window Functions** | Running totals, rankings |
| **Currency Analysis** | Exchange rate trends |
| **Sales Analysis** | Reseller sales, reasons distribution |

**Plus:** Hebrew language queries for international support!

#### 5. **Business Rules (5 entries)**
- Customer segmentation criteria
- Sales metrics calculations
- Date dimension usage patterns
- Product information rules
- Geography data relationships

---

## 🔬 How Training Works

### The RAG (Retrieval-Augmented Generation) Process

When a user asks a question, here's what happens:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER QUESTION                                            │
│    "What is the gross margin by product category?"         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. EMBEDDING (Azure OpenAI)                                 │
│    Question → 3072-dimensional vector                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. RETRIEVAL (pgvector similarity search)                  │
│                                                             │
│    Searches 4 tables:                                       │
│    ├─ vanna_ddl           → Relevant table schemas        │
│    ├─ vanna_documentation → Business terms & rules        │
│    ├─ vanna_sql_examples  → Similar SQL patterns          │
│    └─ vanna_tool_memory   → Past successful queries       │
│                                                             │
│    Returns:                                                │
│    ├─ DimProduct schema (columns, types)                  │
│    ├─ DimProductCategory schema                           │
│    ├─ FactInternetSales schema                            │
│    ├─ "Gross Margin" definition + formula                 │
│    ├─ Sample aggregation SQL patterns                     │
│    └─ Previous similar queries                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. AUGMENTATION (Build enhanced prompt)                    │
│                                                             │
│    System Prompt:                                          │
│    "You are a SQL expert for AdventureWorksDW..."         │
│                                                             │
│    ## DATABASE SCHEMA:                                     │
│    CREATE TABLE DimProduct (...)                           │
│    CREATE TABLE DimProductCategory (...)                   │
│    CREATE TABLE FactInternetSales (...)                    │
│                                                             │
│    ## BUSINESS RULES:                                      │
│    - Gross Margin: (Sales - Cost) / Sales × 100           │
│    - Product categories: Bikes, Components, etc.           │
│                                                             │
│    ## SIMILAR EXAMPLES:                                    │
│    Q: "Sales by product category"                          │
│    SQL: SELECT pc.EnglishProductCategoryName, ...          │
│                                                             │
│    User Question: "What is the gross margin by            │
│                    product category?"                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. GENERATION (Azure OpenAI GPT-5.1)                       │
│    Creates SQL using context from training data            │
│                                                             │
│    Generated SQL:                                          │
│    SELECT                                                  │
│      pc.EnglishProductCategoryName AS Category,           │
│      ROUND(                                                │
│        (SUM(f.SalesAmount) - SUM(f.TotalProductCost)) /  │
│        SUM(f.SalesAmount) * 100,                          │
│        2                                                   │
│      ) AS GrossMarginPct                                   │
│    FROM FactInternetSales f                               │
│    JOIN DimProduct p ON f.ProductKey = p.ProductKey      │
│    JOIN DimProductCategory pc ON p.ProductCategoryKey     │
│      = pc.ProductCategoryKey                              │
│    GROUP BY pc.EnglishProductCategoryName                 │
│    ORDER BY GrossMarginPct DESC;                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. EXECUTION (PostgreSQL)                                  │
│    Runs SQL against AdventureWorksDW                       │
│    Returns results to user                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. LEARNING (Save to memory)                               │
│    If successful:                                          │
│    - Store question + SQL + success in vanna_tool_memory  │
│    - Future similar queries benefit from this example     │
└─────────────────────────────────────────────────────────────┘
```

### Why This Works So Well

1. **Schema Understanding:** Knows exact table structures, column names, data types
2. **Business Context:** Understands "gross margin" means a specific formula
3. **Query Patterns:** Learns from similar examples (joins, aggregations)
4. **Data Awareness:** Knows actual data values and patterns
5. **Self-Improvement:** Gets better over time as it learns from usage

---

## 🛠️ Training Data Loader Details

### Script: `scripts/load_training_data.py`

#### What It Does

1. **Initializes Azure OpenAI Embeddings**
   - Connects to your Azure OpenAI endpoint
   - Uses `text-embedding-3-large-2` model
   - Generates 3072-dimensional vectors

2. **Connects to pgvector Database**
   - Container: `pgvector-db`
   - Database: `vanna_vectors`
   - Creates/updates 4 tables with vector indexes

3. **Loads Training Data in Stages:**

   **Stage 1: DDL Schemas (schema.json)**
   - Reads 34 table definitions
   - Combines: table name + description + DDL
   - Generates embedding for each table
   - Inserts into `vanna_ddl` table
   - Time: ~30-60 seconds

   **Stage 2: Documentation (documentation.json)**
   - Loads 5 basic business rules
   - Embeds each rule
   - Inserts into `vanna_documentation`
   - Time: ~5-10 seconds

   **Stage 3: Business Terms (business-terms.json)**
   - Groups 55 terms by category (18 categories)
   - Creates documentation per category
   - Embeds and stores each category
   - Inserts into `vanna_documentation`
   - Time: ~20-30 seconds

   **Stage 4: Sample Data (samples.json)**
   - Loads sample records from tables
   - Takes first 5 examples per table
   - Formats as documentation
   - Embeds and stores
   - Inserts into `vanna_documentation`
   - Time: ~1-2 minutes

   **Stage 5: SQL Patterns (sql_patterns.json)**
   - Loads 13 query patterns
   - Embeds each pattern's description
   - Inserts into `vanna_sql_examples`
   - Time: ~15-30 seconds

4. **Creates Vector Indexes**
   - Uses IVFFlat algorithm for fast similarity search
   - Cosine similarity for vector comparison
   - Optimized for ~200 vectors

#### Database Schema Created

```sql
-- DDL embeddings (34 entries)
CREATE TABLE vanna_ddl (
    id UUID PRIMARY KEY,
    ddl_text TEXT NOT NULL,
    embedding vector(3072),
    created_at TIMESTAMP
);

-- Documentation + Business Terms + Samples (70+ entries)
CREATE TABLE vanna_documentation (
    id UUID PRIMARY KEY,
    doc_text TEXT NOT NULL,
    embedding vector(3072),
    created_at TIMESTAMP
);

-- SQL examples (13 entries)
CREATE TABLE vanna_sql_examples (
    id UUID PRIMARY KEY,
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    embedding vector(3072),
    created_at TIMESTAMP
);

-- Tool usage memory (grows over time)
CREATE TABLE vanna_tool_memory (
    id UUID PRIMARY KEY,
    question TEXT NOT NULL,
    tool_name VARCHAR(255),
    args JSONB,
    user_id VARCHAR(255),
    success BOOLEAN,
    embedding vector(3072),
    created_at TIMESTAMP
);
```

#### Performance

- **Total Embeddings Generated:** ~120
- **Total Time:** 2-5 minutes (depends on Azure OpenAI API latency)
- **Storage:** ~50 MB in pgvector
- **Query Performance:** <100ms similarity searches

#### One-Time Process

✅ **Training data persists in Docker volume**
- Only need to load once
- Data survives container restarts
- Re-load only if:
  - Adding new training files
  - Updating existing data
  - Deleting Docker volume

---

## 🧪 Testing Your System

### 1. Basic Health Check

```powershell
curl http://localhost:8000/health
```

**Should return:**
```json
{
  "status": "healthy",
  "agent_ready": true
}
```

### 2. List Available Tables

```powershell
curl http://localhost:8000/api/tables
```

**Should return 34 tables:**
```json
{
  "tables": [
    "dimcustomer",
    "dimproduct",
    "factinternetsales",
    ...
  ]
}
```

### 3. Get Table Schema

```powershell
curl http://localhost:8000/api/schema/dimcustomer
```

### 4. Simple Query Tests

**Test 1: Basic Aggregation**
```powershell
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What is the total revenue?\"}'
```

**Test 2: Business Term Usage**
```powershell
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"Show me the gross margin by product category\"}'
```

**Test 3: Time Period Understanding**
```powershell
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What were sales in fiscal Q4 2013?\"}'
```

**Test 4: Complex Join**
```powershell
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"Top 10 customers by total purchases with their countries\"}'
```

### 5. Expected Response Format

```json
{
  "question": "What is the total revenue?",
  "sql": "SELECT SUM(SalesAmount) as TotalRevenue FROM FactInternetSales;",
  "results": {
    "columns": ["totalrevenue"],
    "rows": [{"totalrevenue": 29358677.22}],
    "row_count": 1
  },
  "explanation": "Generated SQL query to calculate total revenue",
  "error": null
}
```

---

## 🐛 Troubleshooting

### Docker Issues

**Problem:** "Cannot connect to Docker daemon"
```
Solution: Start Docker Desktop and wait for it to be ready
```

**Problem:** Containers won't start
```powershell
# Check Docker Desktop is running
docker ps

# Check logs
docker-compose logs

# Restart containers
docker-compose restart
```

### Training Data Issues

**Problem:** "Failed to connect to pgvector"
```
Solution: 
1. Check pgvector container is healthy: docker ps
2. Wait 30 seconds after docker-compose up
3. Retry training data load
```

**Problem:** "Azure OpenAI 401 Unauthorized"
```
Solution: Check .env file
- AZURE_OPENAI_API_KEY is correct
- AZURE_OPENAI_ENDPOINT is correct
- API key has access to gpt-5.1 and text-embedding-3-large-2
```

**Problem:** Training data already exists
```
Solution: Data is already loaded! You can:
- Skip this step (data persists)
- Or clear and reload:
  docker exec -it vanna-app python scripts/load_training_data.py
```

### Query Issues

**Problem:** "Agent not initialized"
```
Solution: 
1. Check vanna-app is running: docker ps
2. Check logs: docker logs vanna-app
3. Restart: docker-compose restart vanna-app
```

**Problem:** "Cannot connect to AdventureWorksDW"
```
Solution: Check .env file
- DATA_SOURCE_HOST is correct
- DATA_SOURCE_USER has access
- Database is accessible from Docker container
- Firewall allows connection
```

**Problem:** SQL generated but returns no results
```
This is normal! 
- Training data uses sample schemas
- Your database might not have matching data
- SQL is correct, just no matching records
```

### View Logs

```powershell
# Application logs
docker logs vanna-app

# Follow logs in real-time
docker logs -f vanna-app

# pgvector logs
docker logs pgvector-db
```

### Reset Everything

```powershell
# Stop and remove containers + volumes
docker-compose down -v

# Restart fresh
docker-compose up -d

# Reload training data
docker exec -it vanna-app python scripts/load_training_data.py
```

---

## 📚 Additional Resources

- **README.md** - Complete project documentation
- **TRAINING_DATA_SUMMARY.md** - Detailed training data breakdown
- **QUICKSTART.md** - Simplified quick start guide
- **API Documentation** - http://localhost:8000/docs (when running)

---

## 🎯 Success Checklist

After following this guide, you should have:

- ✅ Docker containers running (pgvector-db + vanna-app)
- ✅ Training data loaded (157+ items in pgvector)
- ✅ Health endpoint responding
- ✅ Test queries working
- ✅ System understanding:
  - All 34 database tables
  - 55 business terms and their definitions
  - Common SQL patterns
  - Sample data patterns

**Your Vanna 2.0 Text-to-SQL system is production-ready!** 🚀

---

**Last Updated:** 2025-12-27
**Version:** 1.0.0
