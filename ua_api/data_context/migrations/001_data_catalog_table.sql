-- Migration 001 — data provenance / freshness catalog
-- Run this once in the Supabase SQL editor.
--
-- Records, per analytics table, when it was last loaded, how many rows, from
-- which source file/checksum, and the load outcome. Powers freshness checks
-- and the future provenance footer ("data as of ...").

CREATE TABLE IF NOT EXISTS nep_data_catalog (
  table_name       TEXT PRIMARY KEY,
  row_count        BIGINT,
  source_file      TEXT,
  source_checksum  TEXT,
  last_loaded_at   TIMESTAMPTZ,
  load_status      TEXT,          -- 'success' | 'failed' | 'partial'
  loaded_by        TEXT,
  notes            TEXT,
  updated_at       TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE nep_data_catalog IS
  'Load provenance and freshness metadata for NEP analytics tables. Maintained by the data_context module.';

-- The freshness backfill writes to this table via PostgREST as service_role;
-- the health endpoint reads it. Grant the Supabase API roles accordingly.
GRANT SELECT, INSERT, UPDATE ON nep_data_catalog TO service_role;
GRANT SELECT ON nep_data_catalog TO authenticated, anon;
