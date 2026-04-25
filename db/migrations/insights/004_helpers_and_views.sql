-- ============================================================================
-- Jeen Insights: helper function + analytics views
-- ============================================================================

CREATE OR REPLACE FUNCTION insights_get_next_sequence_number(p_session_id UUID)
RETURNS INT AS $$
DECLARE
    max_seq INT;
BEGIN
    SELECT COALESCE(MAX(sequence_number), 0) + 1
    INTO max_seq
    FROM insights_conversation_sessions
    WHERE session_id = p_session_id;
    RETURN max_seq;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW v_insights_recent_conversations AS
SELECT
    cs.id,
    cs.session_id,
    cs.sequence_number,
    cs.user_id,
    cs.source_key,
    cs.natural_language_query,
    cs.generated_sql,
    cs.execution_status,
    cs.row_count,
    cs.created_at,
    COUNT(qi.id) AS insights_count,
    COALESCE(cs.llm_latency_ms, 0) + COALESCE(cs.execution_time_ms, 0) AS total_time_ms
FROM insights_conversation_sessions cs
LEFT JOIN insights_query_insights qi ON cs.id = qi.query_id
GROUP BY cs.id;

CREATE OR REPLACE VIEW v_insights_conversation_threads AS
SELECT
    session_id,
    user_id,
    source_key,
    COUNT(*) AS query_count,
    MIN(created_at) AS started_at,
    MAX(created_at) AS last_activity_at,
    SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) AS successful_queries,
    SUM(CASE WHEN execution_status != 'success' THEN 1 ELSE 0 END) AS failed_queries
FROM insights_conversation_sessions
GROUP BY session_id, user_id, source_key;

CREATE OR REPLACE VIEW v_insights_query_performance AS
SELECT
    source_key,
    llm_model,
    DATE_TRUNC('day', created_at) AS query_date,
    COUNT(*) AS query_count,
    AVG(llm_latency_ms) AS avg_llm_latency_ms,
    AVG(execution_time_ms) AS avg_execution_time_ms,
    AVG(tokens_used) AS avg_tokens_used,
    SUM(tokens_used) AS total_tokens_used,
    COUNT(*) FILTER (WHERE execution_status = 'success') AS success_count,
    COUNT(*) FILTER (WHERE execution_status != 'success') AS error_count
FROM insights_conversation_sessions
WHERE llm_latency_ms IS NOT NULL
GROUP BY source_key, llm_model, DATE_TRUNC('day', created_at);
