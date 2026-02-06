-- ============================================================================
-- Pinned Questions Table
-- ============================================================================
-- Allows users to pin favorite questions to the top of their history

CREATE TABLE IF NOT EXISTS user_pinned_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    pinned_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure a user can't pin the same question twice
    CONSTRAINT uq_user_question UNIQUE (user_id, question)
);

-- Index for quick lookup by user
CREATE INDEX IF NOT EXISTS idx_user_pinned 
    ON user_pinned_questions(user_id, pinned_at DESC);

-- Comments
COMMENT ON TABLE user_pinned_questions IS 
'Stores user-pinned questions that appear at the top of their question history.';

COMMENT ON COLUMN user_pinned_questions.question IS 
'The exact question text that was pinned. Must match natural_language_query from conversation sessions.';
