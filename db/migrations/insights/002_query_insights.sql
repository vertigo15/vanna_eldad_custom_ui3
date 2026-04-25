-- ============================================================================
-- Jeen Insights: insights_query_insights
-- ============================================================================
-- Per-query LLM-generated insights (summary / finding / suggestion / chart).
-- ============================================================================

CREATE TABLE IF NOT EXISTS insights_query_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES insights_conversation_sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),

    insight_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,

    llm_model VARCHAR(100),
    llm_execution_time_ms INT,
    tokens_input INT,
    tokens_output INT,

    CONSTRAINT chk_insights_query_insight_type CHECK (
        insight_type IN ('summary', 'finding', 'suggestion', 'chart', 'anomaly')
    )
);

CREATE INDEX IF NOT EXISTS idx_insights_query_insights_by_query
    ON insights_query_insights(query_id, created_at);

CREATE INDEX IF NOT EXISTS idx_insights_query_insights_by_type
    ON insights_query_insights(insight_type, created_at DESC);

COMMENT ON TABLE insights_query_insights IS
'Jeen Insights: LLM-generated insights for individual queries.';
