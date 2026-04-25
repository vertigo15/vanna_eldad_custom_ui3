# Jeen Insights

A multi-connection, natural-language analytics application powered by Azure
OpenAI. Jeen Insights reads curated metadata (tables, columns, relationships,
business terms, knowledge pairs) directly from the shared Jeen metadata
database and lets a user ask questions against any registered connection.

> **Note:** the repository directory is still named `venna_test3` for legacy
> reasons; the application itself, container names, and all user-facing
> branding are **Jeen Insights**.

## Features

- 🤖 **Azure OpenAI agent** — GPT model orchestrates SELECT-only SQL execution.
- 🔌 **Multi-connection** — pick any active connection from
  `public.metadata_sources`. Each connection has its own curated metadata.
- 📚 **No RAG / no embeddings** — curated metadata from Schema Modeler is
  injected directly into the system prompt at every turn.
- 🐘 **Shared Jeen metadata DB** — Jeen Insights writes only to tables with the
  `insights_` prefix and reads from `metadata_*` / `knowledge_pairs`.
- 🐳 **Docker-first** — `docker-compose up -d` brings up the API + UI.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            Docker Compose                                 │
│  ┌──────────────────┐         ┌────────────────────┐                      │
│  │ jeen-insights-ui │────────▶│ jeen-insights-api  │                      │
│  │   (Flask UI)     │         │ (FastAPI agent)    │                      │
│  │   :8501          │         │   :8001            │                      │
│  └──────────────────┘         └────────┬───────────┘                      │
│                                        │                                  │
│                                        ▼                                  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ Azure OpenAI (gpt-5.1)                                              │  │
│  │ Shared metadata DB (jeen_data_metadata_dev) — read curated metadata │  │
│  │   + insights_* operational tables (sessions / insights / pins)      │  │
│  │ Per-connection PostgreSQL data sources (resolved at runtime)        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker Desktop
- Azure OpenAI API access
- A Jeen metadata DB with at least one row in `public.metadata_sources` and
  the curated `metadata_tables` / `metadata_columns` / `metadata_relationships`
  / `knowledge_pairs` / `metadata_business_terms` rows for that connection
  (use Schema Modeler to set them up).

### 1. Configure environment

Copy `.env` and set:

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.1

METADATA_DB_HOST=jeen-pg-dev-weu.postgres.database.azure.com
METADATA_DB_PORT=5432
METADATA_DB_NAME=jeen_data_metadata_dev
METADATA_DB_USER=jeen_pg_dev_admin
METADATA_DB_PASSWORD=<rotate>
METADATA_DB_SSL=true
```

### 2. Start the stack

```bash
docker-compose up -d --build
```

### 3. Apply the operational migrations (once)

```bash
docker exec jeen-insights-api python scripts/run_insights_migrations.py
```

This creates `insights_conversation_sessions`, `insights_query_insights`,
`insights_pinned_questions`, plus helpers and views. All migrations are
idempotent and only add **new** tables — they never touch existing ones.

### 4. Open the UI

http://localhost:8501

Pick a connection from the dropdown in the top bar and ask a question.

## API surface

| Method | Endpoint                                          | Notes                                                  |
|--------|---------------------------------------------------|--------------------------------------------------------|
| GET    | `/api/connections`                                | List active connections (no secrets).                  |
| GET    | `/api/connections/{source_key}`                   | Connection details + metadata row counts.              |
| POST   | `/api/connections/{source_key}/refresh-metadata`  | Invalidate the metadata loader cache for a source.     |
| POST   | `/api/query`                                      | Body: `{question, connection, session_id?}`.           |
| GET    | `/api/tables?connection=<source_key>`             | List tables on the chosen data source.                 |
| GET    | `/api/schema/{table}?connection=<source_key>`     | Column-level schema.                                   |
| POST   | `/api/generate-insights`                          | Body must include `connection` + `dataset` + `question`.|
| POST   | `/api/generate-chart` / `/api/enhance-chart`      | Same: `connection` is required.                        |
| POST   | `/api/feedback`                                   | Records `thumbs_up` / `thumbs_down` / `edited`.        |
| GET    | `/api/conversation/{session_id}`                  | Conversation history with insights.                    |
| GET/POST | `/api/user/recent-questions` / `…/pin-question` | Per-(user, connection) history.                        |

Every endpoint that operates on a dataset requires the `connection` parameter
(the `source_key` from `metadata_sources`). Requests without it return 400.

## What the agent does on every question

1. Resolve the active `source_key` and load the per-connection metadata bundle
   (six SQL queries against `metadata_*` / `knowledge_pairs` / 
   `metadata_business_terms`).
2. `str.format` the metadata into `src/agent/prompts/jeen_insights_system.md`.
3. Replay the last two Q&As from `insights_conversation_sessions` for
   short-term context.
4. Call Azure OpenAI with the `run_sql` tool schema bound to the connection's
   `PostgresSqlRunner`.
5. Execute the SQL, log the full lifecycle (LLM tokens / latency / row count)
   to `insights_conversation_sessions` partitioned by `source_key`.

## Project layout

```
venna_test3/                       (repo dir, kept for now)
├── docker-compose.yml             jeen-insights-api + jeen-insights-ui
├── Dockerfile / Dockerfile.ui
├── .env                           METADATA_DB_* + AZURE_OPENAI_*
├── requirements.txt
├── db/migrations/insights/        New idempotent migrations (CREATE IF NOT EXISTS)
│   ├── 001_conversation_sessions.sql
│   ├── 002_query_insights.sql
│   ├── 003_pinned_questions.sql
│   └── 004_helpers_and_views.sql
├── db/migrations/_legacy/         Kept for history, NOT applied
├── scripts/run_insights_migrations.py
├── src/
│   ├── config.py                  Settings: AZURE_OPENAI_* + METADATA_DB_*
│   ├── main.py                    FastAPI app + AgentRegistry lifespan
│   ├── ui_app.py                  Flask proxy → FastAPI
│   ├── agent/
│   │   ├── jeen_insights_agent.py JeenInsightsAgent + AgentRegistry
│   │   ├── conversation_history.py
│   │   ├── llm_service.py
│   │   ├── insight_service.py
│   │   ├── profiling_service.py
│   │   ├── sweetviz_service.py
│   │   ├── user_resolver.py
│   │   └── prompts/jeen_insights_system.md
│   ├── connections/connection_service.py
│   ├── metadata/
│   │   ├── metadata_db.py
│   │   └── metadata_loader.py
│   ├── tools/sql_tool.py          Per-connection PostgresSqlRunner
│   ├── templates/index.html       Connection selector + main UI
│   └── static/                    script.js / style.css / chart-feature / insights / profiling
```

## Roadmap

- Connection types beyond Postgres (currently returns 501 for Snowflake /
  PowerBI / etc.).
- Encrypted secrets at rest in `metadata_sources`.

## License

MIT
