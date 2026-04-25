# Legacy migrations (Vanna era)

These files were used when Jeen Insights ran against a **local pgvector**
container with `vanna_*` / `txt2sql_*` / `user_pinned_questions` tables for
RAG and conversation history.

They are kept here only as historical reference. Do **not** apply them — the
new system uses:

- Curated metadata read at prompt time from the shared metadata DB
  (`metadata_tables`, `metadata_columns`, `metadata_relationships`,
  `metadata_sources`, `knowledge_pairs`, `metadata_business_terms`).
- Operational tables under the `insights_` prefix: see
  `db/migrations/insights/*.sql`.

Run the new migrations with:

```bash
docker exec jeen-insights-api python scripts/run_insights_migrations.py
```
