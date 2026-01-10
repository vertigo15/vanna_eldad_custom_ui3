-- ============================================================================
-- Text-to-SQL Conversation History Schema
-- ============================================================================
-- Tracks complete query lifecycle: input → LLM → execution → insights → feedback
-- Enables conversation context, debugging, analytics, and ML training data

-- ============================================================================
-- Main Conversation Table
-- ============================================================================
CREATE TABLE txt2sql_conversation_sessions (
    -- Identity & Grouping
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,  -- Groups related queries in a conversation
    sequence_number INT NOT NULL,  -- Order within session (1, 2, 3, ...)
    parent_query_id UUID,  -- Reference to previous query if this is a follow-up
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Input
    natural_language_query TEXT NOT NULL,
    
    -- Context used
    dataset_id VARCHAR(255),  -- Which database/dataset was queried
    schema_context JSONB,  -- Snapshot of tables/columns available to LLM
    rag_context JSONB,  -- {ddl_count: 5, examples_count: 2, similarity_scores: [0.9, 0.85]}
    
    -- LLM outputs
    generated_sql TEXT,
    llm_model VARCHAR(100),
    llm_latency_ms INT,
    tokens_used INT,
    
    -- Execution
    execution_status VARCHAR(50),  -- success, error, timeout, syntax_error
    execution_time_ms INT,
    row_count INT,
    result_preview JSONB,  -- First 10 rows, max 1KB per row
    error_message TEXT,
    
    -- Feedback loop
    user_feedback VARCHAR(20),  -- thumbs_up, thumbs_down, edited
    corrected_sql TEXT,  -- If user fixed it
    feedback_notes TEXT,
    
    -- Constraints
    CONSTRAINT uq_session_sequence UNIQUE (session_id, sequence_number),
    CONSTRAINT fk_parent_query FOREIGN KEY (parent_query_id) 
        REFERENCES txt2sql_conversation_sessions(id) ON DELETE SET NULL,
    CONSTRAINT chk_execution_status CHECK (
        execution_status IN ('success', 'error', 'timeout', 'syntax_error', 'pending')
    ),
    CONSTRAINT chk_user_feedback CHECK (
        user_feedback IS NULL OR user_feedback IN ('thumbs_up', 'thumbs_down', 'edited')
    )
);

-- ============================================================================
-- Query Insights Table
-- ============================================================================
CREATE TABLE txt2sql_query_insights (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES txt2sql_conversation_sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Insight content
    insight_type VARCHAR(50) NOT NULL,  -- summary, finding, suggestion, chart
    content TEXT NOT NULL,
    metadata JSONB,  -- Chart configs, statistical data, etc.
    
    -- LLM tracking
    llm_model VARCHAR(100),
    llm_execution_time_ms INT,
    tokens_input INT,
    tokens_output INT,
    
    -- Constraints
    CONSTRAINT chk_insight_type CHECK (
        insight_type IN ('summary', 'finding', 'suggestion', 'chart', 'anomaly')
    )
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Session history retrieval (most common query)
CREATE INDEX idx_session_history 
    ON txt2sql_conversation_sessions(session_id, sequence_number);

-- User query history
CREATE INDEX idx_user_queries 
    ON txt2sql_conversation_sessions(user_id, created_at DESC);

-- Dataset analytics
CREATE INDEX idx_dataset_queries 
    ON txt2sql_conversation_sessions(dataset_id, created_at DESC);

-- Feedback analysis (only index when feedback exists)
CREATE INDEX idx_user_feedback 
    ON txt2sql_conversation_sessions(user_feedback) 
    WHERE user_feedback IS NOT NULL;

-- Failed queries for debugging
CREATE INDEX idx_failed_queries 
    ON txt2sql_conversation_sessions(execution_status) 
    WHERE execution_status != 'success';

-- Insights by query
CREATE INDEX idx_insights_by_query 
    ON txt2sql_query_insights(query_id, created_at);

-- Insights by type (for analytics)
CREATE INDEX idx_insights_by_type 
    ON txt2sql_query_insights(insight_type, created_at DESC);

-- ============================================================================
-- Helpful Views
-- ============================================================================

-- Recent conversations with all insights
CREATE VIEW v_recent_conversations AS
SELECT 
    cs.id,
    cs.session_id,
    cs.sequence_number,
    cs.user_id,
    cs.natural_language_query,
    cs.generated_sql,
    cs.execution_status,
    cs.row_count,
    cs.created_at,
    COUNT(qi.id) as insights_count,
    cs.llm_latency_ms + COALESCE(cs.execution_time_ms, 0) as total_time_ms
FROM txt2sql_conversation_sessions cs
LEFT JOIN txt2sql_query_insights qi ON cs.id = qi.query_id
GROUP BY cs.id
ORDER BY cs.created_at DESC;

-- Conversation threads (all queries in a session)
CREATE VIEW v_conversation_threads AS
SELECT 
    session_id,
    user_id,
    COUNT(*) as query_count,
    MIN(created_at) as started_at,
    MAX(created_at) as last_activity_at,
    SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) as successful_queries,
    SUM(CASE WHEN execution_status != 'success' THEN 1 ELSE 0 END) as failed_queries
FROM txt2sql_conversation_sessions
GROUP BY session_id, user_id;

-- Performance analytics
CREATE VIEW v_query_performance AS
SELECT 
    llm_model,
    DATE_TRUNC('day', created_at) as query_date,
    COUNT(*) as query_count,
    AVG(llm_latency_ms) as avg_llm_latency_ms,
    AVG(execution_time_ms) as avg_execution_time_ms,
    AVG(tokens_used) as avg_tokens_used,
    SUM(tokens_used) as total_tokens_used,
    COUNT(*) FILTER (WHERE execution_status = 'success') as success_count,
    COUNT(*) FILTER (WHERE execution_status != 'success') as error_count
FROM txt2sql_conversation_sessions
WHERE llm_latency_ms IS NOT NULL
GROUP BY llm_model, DATE_TRUNC('day', created_at);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Get conversation context (last N queries in session)
CREATE OR REPLACE FUNCTION get_conversation_context(
    p_session_id UUID,
    p_limit INT DEFAULT 5
)
RETURNS TABLE (
    sequence_number INT,
    natural_language_query TEXT,
    generated_sql TEXT,
    execution_status VARCHAR(50),
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cs.sequence_number,
        cs.natural_language_query,
        cs.generated_sql,
        cs.execution_status,
        cs.created_at
    FROM txt2sql_conversation_sessions cs
    WHERE cs.session_id = p_session_id
    ORDER BY cs.sequence_number DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Calculate next sequence number for session
CREATE OR REPLACE FUNCTION get_next_sequence_number(p_session_id UUID)
RETURNS INT AS $$
DECLARE
    max_seq INT;
BEGIN
    SELECT COALESCE(MAX(sequence_number), 0) + 1
    INTO max_seq
    FROM txt2sql_conversation_sessions
    WHERE session_id = p_session_id;
    
    RETURN max_seq;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE txt2sql_conversation_sessions IS 
'Complete query lifecycle tracking: input → LLM → execution → feedback. Enables conversation context, debugging, analytics, and ML training data.';

COMMENT ON COLUMN txt2sql_conversation_sessions.session_id IS 
'Groups related queries in a conversation. Multiple queries can share the same session_id for follow-up questions.';

COMMENT ON COLUMN txt2sql_conversation_sessions.sequence_number IS 
'Order of query within session (1, 2, 3...). Used with session_id for conversation flow.';

COMMENT ON COLUMN txt2sql_conversation_sessions.schema_context IS 
'JSONB snapshot of tables/columns available to LLM at query time. Enables reproduction of exact context even after schema changes.';

COMMENT ON COLUMN txt2sql_conversation_sessions.rag_context IS 
'Metadata about retrieved context: {ddl_count: 5, examples_count: 2, similarity_scores: [0.9, 0.85]}. Helps diagnose poor RAG retrieval.';

COMMENT ON COLUMN txt2sql_conversation_sessions.result_preview IS 
'First 10 rows of query results as JSONB. Max 1KB per row. Enough to verify correctness without storing massive datasets.';

COMMENT ON TABLE txt2sql_query_insights IS 
'Generated insights for queries: summaries, findings, suggestions, charts. Separate table to avoid bloating main table.';

COMMENT ON COLUMN txt2sql_query_insights.tokens_input IS 
'Input tokens sent to LLM for insight generation. Used for cost tracking.';

COMMENT ON COLUMN txt2sql_query_insights.tokens_output IS 
'Output tokens received from LLM. Combined with tokens_input for total cost calculation.';
