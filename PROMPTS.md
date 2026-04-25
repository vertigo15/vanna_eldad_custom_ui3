# Prompt Locations — Venna Test3

## Prompt 1 — Text-to-SQL (Data Query)

Located in `src/agent/vanna_agent.py`. Has **2 parts**:

| Part | Lines | Description |
|---|---|---|
| Static system instructions | 344–366 | Role, rules, language, security, error handling |
| Dynamic RAG context (appended) | 368–385 | DDL schema + business rules + SQL examples from pgvector |
| Conversation history (injected) | 130–146 | Last 2 Q&A turns from the current session |

The static part defines the SQL expert role and constraints. The dynamic part is retrieved at runtime from pgvector by embedding-similarity to the user's question.

---

## Prompt 2 — Insights / Analytics

Split across **2 files**:

| Part | File | Description |
|---|---|---|
| System message (1 line) | `src/agent/insight_service.py` line 33 | `"You are a senior data analyst specialized in finding actionable insights."` |
| User prompt template | `templates/insight_prompt.txt` | Full template: rules, confidence thresholds, dataset stats, output format |

The template is loaded from `templates/insight_prompt.txt` and filled with:
- Original user question
- Business rules (from pgvector documentation)
- Row count, column names
- Data sample (first 10 rows)
- Column statistics (min/max/mean/median for numeric, top values for categorical)

---

## Prompt 3 — Chart / Graph

Entirely inline in `src/main.py`. Two endpoints, each with a system + user prompt:

| Endpoint | Part | Lines | Description |
|---|---|---|---|
| `/api/generate-chart` | System prompt | 440–752 | Chart type selection, date consolidation, K/M/B number formatting, layout rules, ECharts examples |
| `/api/generate-chart` | User prompt | 773–794 | Column names, types, sample data, optional chart type override |
| `/api/enhance-chart` | System prompt | 890–957 | Refines an existing ECharts config with formatting and styling |
| `/api/enhance-chart` | User prompt | 960–982 | Current config + column info to enhance |

---

## Summary Map

```
SQL query prompt  → src/agent/vanna_agent.py        (2 parts: static + RAG)
Insights prompt   → src/agent/insight_service.py    (system message, 1 line)
                  + templates/insight_prompt.txt     (user prompt template)
Chart prompt      → src/main.py                     (inline, 2 endpoints × 2 parts each)
```
