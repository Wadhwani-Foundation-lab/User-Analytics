-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- Chat sessions table (one row per conversation thread)
CREATE TABLE IF NOT EXISTS nep_chat_sessions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Individual messages within a session
CREATE TABLE IF NOT EXISTS nep_chat_messages (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    UUID REFERENCES nep_chat_sessions(id) ON DELETE CASCADE,
  role          TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content       TEXT NOT NULL,
  response_type TEXT,
  chart_config  JSONB,
  table_data    JSONB,
  sql_used      TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON nep_chat_messages(session_id);
