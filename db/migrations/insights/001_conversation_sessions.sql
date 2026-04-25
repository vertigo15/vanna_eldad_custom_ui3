-- ============================================================================
-- Jeen Insights: insights_conversation_sessions
-- ============================================================================
-- Tracks complete query lifecycle (input -> LLM -> execution -> feedback) per
-- connection. `source_key` matches public.metadata_sources.source_key.
--
-- Idempotent. Safe to run on the shared metadata DB without affecting other
-- tables.
-- ============================================================================

CREATE TABLE IF NOT EXISTS insights_conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    source_key VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,
    sequence_number INT NOT NULL,
    parent_query_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Input
    natural_language_query TEXT NOT NULL,

    -- Context used
    dataset_id VARCHAR(255),
    schema_context JSONB,
    rag_context JSONB,

    -- LLM outputs
    generated_sql TEXT,
    llm_model VARCHAR(100),
    llm_latency_ms INT,
    tokens_used INT,

    -- Execution
    execution_status VARCHAR(50),
    execution_time_ms INT,
    row_count INT,
    result_preview JSONB,
    error_message TEXT,

    -- Feedback loop
    user_feedback VARCHAR(20),
    corrected_sql TEXT,
    feedback_notes TEXT,

    CONSTRAINT uq_insights_session_sequence UNIQUE (session_id, sequence_number),
    CONSTRAINT fk_insights_parent_query FOREIGN KEY (parent_query_id)
        REFERENCES insights_conversation_sessions(id) ON DELETE SET NULL,
    CONSTRAINT chk_insights_execution_status CHECK (
        execution_status IN ('success', 'error', 'timeout', 'syntax_error', 'pending')
    ),
    CONSTRAINT chk_insights_user_feedback CHECK (
        user_feedback IS NULL OR user_feedback IN ('thumbs_up', 'thumbs_down', 'edited')
    )
);

CREATE INDEX IF NOT EXISTS idx_insights_session_history
    ON insights_conversation_sessions(session_id, sequence_number);

CREATE INDEX IF NOT EXISTS idx_insights_user_queries
    ON insights_conversation_sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_insights_source_queries
    ON insights_conversation_sessions(source_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_insights_user_feedback
    ON insights_conversation_sessions(user_feedback)
    WHERE user_feedback IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_insights_failed_queries
    ON insights_conversation_sessions(execution_status)
    WHERE execution_status != 'success';

COMMENT ON TABLE insights_conversation_sessions IS
'Jeen Insights: complete query lifecycle tracking, partitioned by source_key (active connection).';
