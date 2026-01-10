# Vanna 2.0 Agent Migration

This branch (`vanna2-agent-migration`) contains the migration to add **conversation history** support using Vanna 2.0 patterns.

## What's New

### ✨ Conversation History
- **Track conversations** across multiple queries using `conversation_id`
- **Context-aware responses** - The agent remembers previous questions and answers
- **Conversation management** - List, retrieve, and delete conversations per user

### 🗄️ New Components

#### 1. ConversationStore (`src/conversation/`)
- **PostgresConversationStore** - Stores conversation history in PostgreSQL
- Automatically creates conversations and messages tables
- User-scoped conversations for privacy
- Methods:
  - `save_message()` - Save user/assistant messages
  - `get_conversation()` - Retrieve full conversation
  - `list_conversations()` - List user's conversations
  - `get_recent_messages()` - Get last N messages for context

#### 2. Updated User Resolver (`src/agent/user_resolver.py`)
- Now compatible with Vanna 2.0's `UserResolver` interface
- Supports `RequestContext` with headers and metadata
- Fallback implementation if Vanna 2.0 not fully installed
- Adds `group_memberships` for future permission support

#### 3. New Main Application (`src/main_vanna2.py`)
- **Conversation-aware** `/api/query` endpoint
- Includes conversation history in LLM context (last 5 messages)
- Returns `conversation_id` in responses
- New endpoints:
  - `GET /api/conversations` - List conversations
  - `GET /api/conversations/{conversation_id}` - Get conversation details

## How It Works

### Conversation Flow

```
1. User asks: "Show me sales by month" (no conversation_id)
   → System generates new conversation_id
   → Saves user message
   → Generates SQL
   → Saves assistant response
   → Returns results + conversation_id

2. User asks: "Now filter for 2023" (with conversation_id from step 1)
   → System retrieves last 5 messages from conversation
   → Includes conversation history in LLM prompt
   → LLM understands "that" refers to previous query
   → Generates contextual SQL
   → Saves messages to same conversation
```

### Database Schema

Two new tables are created in `pgvector` database:

**conversations**
```sql
- id (VARCHAR PRIMARY KEY)
- user_id (VARCHAR)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- metadata (JSONB)
```

**conversation_messages**
```sql
- id (SERIAL PRIMARY KEY)
- conversation_id (VARCHAR, FK)
- role (VARCHAR: 'user' or 'assistant')
- content (TEXT)
- timestamp (TIMESTAMP)
- metadata (JSONB)
```

## API Changes

### Request Format (Updated)

```json
{
  "question": "Show me total sales",
  "conversation_id": "optional-uuid-here",
  "user_context": {}
}
```

### Response Format (Updated)

```json
{
  "question": "Show me total sales",
  "sql": "SELECT SUM(amount)...",
  "results": {...},
  "explanation": "Query executed successfully",
  "conversation_id": "abc-123-def",  // NEW
  "error": null
}
```

## Usage Examples

### Start a New Conversation

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me sales by month for 2023"
  }'
```

Response includes `conversation_id`:
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  ...
}
```

### Continue the Conversation

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Now show only Q1",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

The agent will understand "Now show only Q1" refers to the previous query.

### List Conversations

```bash
curl http://localhost:8000/api/conversations?user_id=default
```

### Get Conversation History

```bash
curl http://localhost:8000/api/conversations/550e8400-e29b-41d4-a716-446655440000?user_id=default
```

### Using Vanna 2.0 Agent (Full Version)

With `main_vanna2_full.py`, use Vanna's streaming endpoints:

```bash
# Streaming chat (Server-Sent Events)
curl -N -X POST http://localhost:8000/api/vanna/v2/chat_sse \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me total sales",
    "conversation_id": "optional-uuid",
    "metadata": {}
  }'
```

**Available Vanna Endpoints:**
- `POST /api/vanna/v2/chat_sse` - Streaming chat (SSE)
- `POST /api/vanna/v2/chat_poll` - Polling-based chat
- `GET /` - Web UI with `<vanna-chat>` component
- `GET /health` - Health check
- `GET /api/tables` - List tables
- `GET /api/schema/{table}` - Get table schema

## Running the Migrated Versions

### Three Options Available:

#### Option 1: Original (No Conversation History)
```bash
python -m uvicorn src.main:app --reload --port 8000
```
Uses custom orchestration, no conversation tracking.

#### Option 2: Conversation History (Custom Orchestration)
```bash
python -m uvicorn src.main_vanna2:app --reload --port 8000
```
Adds conversation history, but uses custom orchestration.

#### Option 3: Full Vanna 2.0 Agent ⭐ **RECOMMENDED**
```bash
python -m uvicorn src.main_vanna2_full:app --reload --port 8000
```
Full Vanna 2.0 integration with:
- `vanna.Agent` orchestration
- Streaming responses (SSE)
- Built-in chat routes: `/api/vanna/v2/chat_sse`
- Tool registry with permissions
- `<vanna-chat>` web component support

### Docker Deployment

Update `docker-compose.yml` to use the full agent:

```yaml
services:
  vanna-app:
    command: uvicorn src.main_vanna2_full:app --host 0.0.0.0 --port 8000
```

## Backward Compatibility

- ✅ **All existing endpoints still work** (`/api/query`, `/api/tables`, `/health`)
- ✅ **Existing clients** work without changes (conversation_id is optional)
- ✅ **If conversation_id not provided**, each query is independent (like before)
- ✅ **All existing functionality preserved** (RAG, tool memory, embeddings)

## What's Different from Full Vanna 2.0?

This implementation uses **Vanna 2.0 patterns** but doesn't fully migrate to Vanna's `Agent` class:

| Feature | This Branch | Full Vanna 2.0 Agent |
|---------|-------------|---------------------|
| Conversation History | ✅ Custom PostgreSQL | ✅ Built-in ConversationStore |
| User Resolver | ✅ Compatible interface | ✅ Native integration |
| LLM Service | ❌ Custom (not inherited) | ✅ Inherits from LlmService |
| Tool Registry | ❌ Custom tool wrapper | ✅ ToolRegistry with access control |
| Agent Orchestration | ❌ Custom | ✅ Vanna's Agent class |
| Streaming Responses | ❌ Not implemented | ✅ Server-Sent Events |
| Web UI Component | ❌ Custom UI | ✅ `<vanna-chat>` component |

## Full Migration Complete! ✅

All components have been migrated to Vanna 2.0:

1. ✅ **DONE:** Conversation store - PostgreSQL-based
2. ✅ **DONE:** User resolver - Compatible with Vanna 2.0 interface
3. ✅ **DONE:** LLM Service - Inherits from `vanna.core.llm.LlmService`
4. ✅ **DONE:** Tool Registry - Using Vanna's `ToolRegistry`
5. ✅ **DONE:** Full Vanna Agent - Using `vanna.Agent` class
6. ✅ **DONE:** Streaming support - Via Server-Sent Events
7. ✅ **DONE:** Web UI routes - Integrated `<vanna-chat>` endpoints

## Testing

### 1. Test Conversation Creation

```bash
# First question
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'
# Note the conversation_id in response
```

### 2. Test Conversation Context

```bash
# Follow-up question (use conversation_id from above)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the breakdown by month",
    "conversation_id": "<conversation-id-from-step-1>"
  }'
```

### 3. Test Conversation Retrieval

```bash
curl http://localhost:8000/api/conversations/<conversation-id>?user_id=default
```

## Benefits

✅ **Contextual conversations** - "Show me that data for last year" works  
✅ **User history** - Track all conversations per user  
✅ **Better UX** - Users can have natural multi-turn dialogues  
✅ **Backward compatible** - Existing code still works  
✅ **Database-backed** - Conversations persist across restarts  
✅ **Privacy-aware** - User-scoped conversations  

## Files Changed

### New Files
- `src/conversation/postgres_conversation_store.py` - Conversation storage
- `src/conversation/__init__.py` - Module exports
- `src/main_vanna2.py` - Conversation-aware application (custom orchestration)
- `src/main_vanna2_full.py` - **Full Vanna 2.0 Agent integration** ⭐
- `src/tools/vanna_sql_tool.py` - Vanna 2.0 compatible SQL tool
- `VANNA2_MIGRATION.md` - This file

### Modified Files
- `src/agent/user_resolver.py` - Compatible with Vanna 2.0 interface
- `src/agent/llm_service.py` - Inherits from Vanna's LlmService

### Unchanged (Still Works)
- `src/main.py` - Original application (still functional)
- `src/agent/vanna_agent.py` - Original agent
- `src/memory/pgvector_memory.py` - Agent memory
- All other existing files

## Merge Strategy

When ready to merge to `main`:

1. Test thoroughly on this branch
2. Update `docker-compose.yml` to use `main_vanna2.py`
3. Add database migration for conversation tables
4. Update documentation
5. Merge to main

Or keep both versions:
- `src/main.py` - Without conversation history (simpler)
- `src/main_vanna2.py` - With conversation history (advanced)
