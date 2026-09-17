-- Migration 003 — join-key & primary-key indexes (generated from the catalog)
-- Regenerate with: python -m data_context migrations emit
-- Run in the Supabase SQL editor. Safe / non-destructive.
-- CREATE INDEX requires table ownership; assume the owner role.
SET ROLE airflow_loader;

-- nep_liftoffx_data_sample foreign keys
CREATE INDEX IF NOT EXISTS idx_nep_liftoffx_data_sample_userid ON nep_liftoffx_data_sample (userid);
CREATE INDEX IF NOT EXISTS idx_nep_master_user_table_sample_data_user_id ON nep_master_user_table_sample_data (user_id);
CREATE INDEX IF NOT EXISTS idx_nep_liftoffx_data_sample_mentor_id ON nep_liftoffx_data_sample (mentor_id);
CREATE INDEX IF NOT EXISTS idx_nep_mentor_profiles_sample_data_user_id ON nep_mentor_profiles_sample_data (user_id);

-- nep_master_live_events_data foreign keys
CREATE INDEX IF NOT EXISTS idx_nep_master_live_events_data_participant_user_id ON nep_master_live_events_data (participant_user_id);

-- nep_master_user_table_sample_data primary key

-- nep_mentor_profiles_sample_data foreign keys

RESET ROLE;
