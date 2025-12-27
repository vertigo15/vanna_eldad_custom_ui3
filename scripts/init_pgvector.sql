-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- DDL embeddings table
CREATE TABLE IF NOT EXISTS vanna_ddl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ddl_text TEXT NOT NULL,
    embedding vector(1536),  -- text-embedding-ada-002 dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documentation embeddings table
CREATE TABLE IF NOT EXISTS vanna_documentation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_text TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SQL examples embeddings table (question + SQL pairs)
CREATE TABLE IF NOT EXISTS vanna_sql_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    embedding vector(1536),  -- Embedding of the question
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tool usage memory table (for Vanna 2.0 AgentMemory)
CREATE TABLE IF NOT EXISTS vanna_tool_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    tool_name VARCHAR(255) NOT NULL,
    args JSONB NOT NULL,
    user_id VARCHAR(255),
    success BOOLEAN DEFAULT TRUE,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for similarity search
CREATE INDEX IF NOT EXISTS idx_ddl_embedding ON vanna_ddl 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_doc_embedding ON vanna_documentation 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_sql_embedding ON vanna_sql_examples 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_tool_memory_embedding ON vanna_tool_memory 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
