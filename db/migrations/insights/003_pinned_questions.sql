-- ============================================================================
-- Jeen Insights: insights_pinned_questions
-- ============================================================================
-- Per-(user, connection) pinned questions surfaced in the UI sidebar.
-- ============================================================================

CREATE TABLE IF NOT EXISTS insights_pinned_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    source_key VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    pinned_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_insights_user_source_question UNIQUE (user_id, source_key, question)
);

CREATE INDEX IF NOT EXISTS idx_insights_pinned_user_source
    ON insights_pinned_questions(user_id, source_key, pinned_at DESC);

COMMENT ON TABLE insights_pinned_questions IS
'Jeen Insights: questions a user pinned for a specific connection (source_key).';
