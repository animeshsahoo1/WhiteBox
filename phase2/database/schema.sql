-- Phase 2 Database Schema
-- PostgreSQL 14+

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

------------------------------------------------------------
-- Conversation Memory Table
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    user_query TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    context_json JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_convo_user_id 
    ON conversation_turns (user_id);

CREATE INDEX IF NOT EXISTS idx_convo_timestamp 
    ON conversation_turns (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_convo_user_timestamp 
    ON conversation_turns (user_id, timestamp DESC);

------------------------------------------------------------
-- Session Summaries
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    turns_covered INT[] NOT NULL,
    key_strategies TEXT[],
    decisions_made JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_summary_user_id 
    ON conversation_summaries (user_id);

CREATE INDEX IF NOT EXISTS idx_summary_created_at 
    ON conversation_summaries (created_at DESC);

------------------------------------------------------------
-- User Profiles (for personalization)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    preferred_risk_tier VARCHAR(50),
    favorite_strategies TEXT[],
    typical_query_types TEXT[],
    interaction_stats JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_profiles_last_active 
    ON user_profiles (last_active DESC);

------------------------------------------------------------
-- Strategy Feedback (optional - for learning)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    strategy_id UUID NOT NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    feedback_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_feedback_strategy_id 
    ON strategy_feedback (strategy_id);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id 
    ON strategy_feedback (user_id);

------------------------------------------------------------
-- Comments
------------------------------------------------------------
COMMENT ON TABLE conversation_turns IS 'Stores all user-orchestrator conversation exchanges';
COMMENT ON TABLE conversation_summaries IS 'Auto-generated summaries of conversation sessions';
COMMENT ON TABLE user_profiles IS 'User preferences and interaction patterns';
COMMENT ON TABLE strategy_feedback IS 'User feedback on recommended strategies';