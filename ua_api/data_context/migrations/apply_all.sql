-- ============================================================
-- data_context — consolidated migrations (run once, in order)
-- Paste this whole file into the Supabase SQL editor and Run.
-- Non-destructive: creates a metadata table, adds column comments,
-- creates indexes. No analytics data is modified.
-- COMMENT/CREATE INDEX run via SET ROLE airflow_loader (table owner).
-- ============================================================

-- ===== 001_data_catalog_table.sql =====
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

-- ===== 002_column_comments.sql =====
-- Migration 002 — column comments (generated from the catalog)
-- Regenerate with: python -m data_context migrations emit
-- Run in the Supabase SQL editor. Safe / non-destructive.
-- COMMENT requires table ownership; the analytics tables are owned by
-- 'airflow_loader'. postgres is a member of it, so we assume the role.
SET ROLE airflow_loader;

-- nep_liftoffx_data_sample: Central activity fact table. One row per user activity event; a single user can have many rows. Used for engagement, retention, funnel and feature-usage analysis. user/company/traffic columns are denormalised copies from the user table for query convenience.
COMMENT ON TABLE nep_liftoffx_data_sample IS 'One row per activity-event slice. activity_id is NOT unique (~71,388 distinct ids across ~154,904 rows; an event is spread across multiple GA/sub-event rows), so there is no single-column primary key.';
COMMENT ON COLUMN nep_liftoffx_data_sample.last_active IS 'Ordinal rank of the user''s most recent active day.';
COMMENT ON COLUMN nep_liftoffx_data_sample.week_activity_number IS 'Week number relative to signup week.';
COMMENT ON COLUMN nep_liftoffx_data_sample.month_activity_number IS 'Month number relative to signup month.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_year_monthnumber_weekstart_order IS 'Numeric sort key for signup week.';
COMMENT ON COLUMN nep_liftoffx_data_sample.year_monthnumber_weekstart_order IS 'Numeric sort key for activity week.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_date IS 'Date the user signed up.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_month_name IS 'Short month name of signup month.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_month_number IS 'Numeric month of signup (as text).';
COMMENT ON COLUMN nep_liftoffx_data_sample.user_type_datekey IS 'Composite key for cohort grouping.';
COMMENT ON COLUMN nep_liftoffx_data_sample.userid IS 'Foreign key to user_id in the user table. NO underscore.';
COMMENT ON COLUMN nep_liftoffx_data_sample.user_email IS 'Email of the user (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.user_first_name IS 'User''s first name (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.user_last_name IS 'User''s last name (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.company_type IS 'User''s company type (denormalised). [enum: startup, msme]';
COMMENT ON COLUMN nep_liftoffx_data_sample.company_revenue_range IS 'User''s company revenue range (denormalised). [enum: above-5-crore, pre-revenue, 1-5-crore]';
COMMENT ON COLUMN nep_liftoffx_data_sample.created_at IS 'Date this activity record was created. (This table has NO created_datetime.)';
COMMENT ON COLUMN nep_liftoffx_data_sample.activity_id IS 'Unique identifier for this activity event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.activity_type IS 'Broad category of activity. Use ONLY these exact strings. Note the intentional typo ''jounrney_explore''. NEVER use ai_chat / mentor_session / live_event / resource_view. [enum: message, mentor, session, resource, visitors, repeat visitors, signup, jounrney_explore, introductory_video_reg_users]';
COMMENT ON COLUMN nep_liftoffx_data_sample.activity_tittle IS 'Specific name of the activity. NOTE intentional typo (double ''t'').';
COMMENT ON COLUMN nep_liftoffx_data_sample.conversation_id IS 'AI chat conversation ID (message activity only).';
COMMENT ON COLUMN nep_liftoffx_data_sample.conversation_parent_id IS 'Parent conversation ID for threaded chat.';
COMMENT ON COLUMN nep_liftoffx_data_sample.message_query IS 'User''s question sent to the AI assistant.';
COMMENT ON COLUMN nep_liftoffx_data_sample.message_query_id IS 'Unique ID for the message query.';
COMMENT ON COLUMN nep_liftoffx_data_sample.message_rating IS 'User rating of the AI response. Feedback-loop signal.';
COMMENT ON COLUMN nep_liftoffx_data_sample.message_rating_feedback IS 'Free-text feedback on the AI response. Feedback-loop signal.';
COMMENT ON COLUMN nep_liftoffx_data_sample.response_type IS 'Type of AI response generated. Vocabulary confirmed against live data. [enum: answer, clarification, regular, journey, new_conversation]';
COMMENT ON COLUMN nep_liftoffx_data_sample.response_content IS 'Full text of the AI response.';
COMMENT ON COLUMN nep_liftoffx_data_sample.response_timestamp IS 'Timestamp of the AI response (ISO 8601 UTC).';
COMMENT ON COLUMN nep_liftoffx_data_sample.response_flow_state IS 'Final state of the AI response pipeline. Vocabulary confirmed against live data. [enum: completed, journey_generated]';
COMMENT ON COLUMN nep_liftoffx_data_sample.response_metricsblob IS 'JSON blob with AI processing metrics.';
COMMENT ON COLUMN nep_liftoffx_data_sample.message_date IS 'Date of the AI chat message.';
COMMENT ON COLUMN nep_liftoffx_data_sample.session_rating IS 'Rating for a mentor session.';
COMMENT ON COLUMN nep_liftoffx_data_sample.mentor_rating IS 'Rating for the mentor.';
COMMENT ON COLUMN nep_liftoffx_data_sample.resources_rating IS 'Rating for resources.';
COMMENT ON COLUMN nep_liftoffx_data_sample.mentor_id IS 'ID of the mentor. Joins to user_id in the mentor table.';
COMMENT ON COLUMN nep_liftoffx_data_sample.mentor_name IS 'Name of the mentor.';
COMMENT ON COLUMN nep_liftoffx_data_sample.mentor_email IS 'Email of the mentor.';
COMMENT ON COLUMN nep_liftoffx_data_sample.connection_reason IS 'Reason for mentor connection.';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_id IS 'ID of live event attended.';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_date IS 'Date of the live event (free text in this table).';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_time IS 'Time of the live event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_source IS 'Source from which the user accessed the event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_speaker IS 'Speaker at the event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.event_gap_area IS 'Gap area covered by the event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.expert_session_topic IS 'Topic of the expert session.';
COMMENT ON COLUMN nep_liftoffx_data_sample.ga_session_id IS 'Google Analytics 4 session ID.';
COMMENT ON COLUMN nep_liftoffx_data_sample.ga_event_name IS 'GA4 event name (large open vocabulary; not enum-validated).';
COMMENT ON COLUMN nep_liftoffx_data_sample.ga_event_date IS 'Date of the GA4 event.';
COMMENT ON COLUMN nep_liftoffx_data_sample.user_type IS 'User classification (denormalised). [enum: Internal Users, External Users, Incomplete Profile]';
COMMENT ON COLUMN nep_liftoffx_data_sample.traffic_source_source IS 'UTM source (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.traffic_source_medium IS 'UTM medium (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.traffic_source_campaign IS 'UTM campaign name (denormalised).';
COMMENT ON COLUMN nep_liftoffx_data_sample.month_year IS 'Human-readable activity month-year label.';
COMMENT ON COLUMN nep_liftoffx_data_sample.month_year_order IS 'Sort key for month_year (YYYYMM as text).';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_month_year IS 'Human-readable signup month-year label.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_month_year_order IS 'Sort key for signup_month_year (YYYYMM as text).';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_year IS 'Year the user signed up.';
COMMENT ON COLUMN nep_liftoffx_data_sample.month_name IS 'Short name of activity month.';
COMMENT ON COLUMN nep_liftoffx_data_sample.month_number IS 'Numeric month of activity (as text).';
COMMENT ON COLUMN nep_liftoffx_data_sample.week_range IS 'Human-readable date range of activity week.';
COMMENT ON COLUMN nep_liftoffx_data_sample.signup_week_range IS 'Date range of signup week.';

-- nep_master_live_events_data: Live events and each participant''s attendance record. One row per participant per event. Use GROUP BY event_id for event-level metrics.
COMMENT ON TABLE nep_master_live_events_data IS 'One row per (event_id, participant) registration.';
COMMENT ON COLUMN nep_master_live_events_data.event_id IS 'Unique ID for the event.';
COMMENT ON COLUMN nep_master_live_events_data.event_title IS 'Full title of the event.';
COMMENT ON COLUMN nep_master_live_events_data.event_status IS 'Event lifecycle status. [enum: COMPLETED, OPEN]';
COMMENT ON COLUMN nep_master_live_events_data.country IS 'Country for the event.';
COMMENT ON COLUMN nep_master_live_events_data.provider IS 'Organisation that hosted the event.';
COMMENT ON COLUMN nep_master_live_events_data.organizer_id IS 'UUID of the organiser.';
COMMENT ON COLUMN nep_master_live_events_data.client_name IS 'Client program short code. [enum: WE, NEP]';
COMMENT ON COLUMN nep_master_live_events_data.description IS 'Full event description.';
COMMENT ON COLUMN nep_master_live_events_data.invite_type IS 'Invitation visibility type. [enum: gap, open]';
COMMENT ON COLUMN nep_master_live_events_data.zoom_meeting_id IS 'Zoom meeting ID.';
COMMENT ON COLUMN nep_master_live_events_data.participants_limit IS 'Maximum participants (stored as text).';
COMMENT ON COLUMN nep_master_live_events_data.start_datetime IS 'UTC start timestamp (ISO 8601).';
COMMENT ON COLUMN nep_master_live_events_data.start_date IS 'Date of event start. Supports TO_CHAR(start_date, ''YYYY-MM'').';
COMMENT ON COLUMN nep_master_live_events_data.end_datetime IS 'UTC end timestamp (ISO 8601).';
COMMENT ON COLUMN nep_master_live_events_data.language IS 'Language of the event.';
COMMENT ON COLUMN nep_master_live_events_data.program_key IS 'NEP program this event belongs to. [enum: liftoff-propel, liftoff, liftoff-spark]';
COMMENT ON COLUMN nep_master_live_events_data.gapkey IS 'Strategic gap area. [enum: AdvancedCustomerAcquisition, BusinessModelCanvas, CompetitiveStrategy, CustomerRetention, FounderDNA, GotoMarketStrategy, GrowthHacking, MarketAnalysisCustomerInsights, MetricsandAnalytics, PitchMastery, PivotPersevere, ProductIteration, ScalableBusinessModel, StartupFinancials]';
COMMENT ON COLUMN nep_master_live_events_data.topickey IS 'Specific topic key.';
COMMENT ON COLUMN nep_master_live_events_data.sessiontype IS 'Session format. [enum: expertSession, roundTable]';
COMMENT ON COLUMN nep_master_live_events_data.created_at IS 'Date when the event record was created.';
COMMENT ON COLUMN nep_master_live_events_data.updated_at IS 'Date of most recent event update.';
COMMENT ON COLUMN nep_master_live_events_data.speaker_name IS 'Full name of the speaker.';
COMMENT ON COLUMN nep_master_live_events_data.speaker_email IS 'Speaker''s email.';
COMMENT ON COLUMN nep_master_live_events_data.speaker_bio IS 'Speaker biography.';
COMMENT ON COLUMN nep_master_live_events_data.event_type IS 'Technical delivery type. [enum: meeting, webinar]';
COMMENT ON COLUMN nep_master_live_events_data.participant_id IS 'Unique ID for this registration (MongoDB ObjectId).';
COMMENT ON COLUMN nep_master_live_events_data.participant_status IS 'Attendance outcome. [enum: ATTENDED, NOSHOW, REGISTERED]';
COMMENT ON COLUMN nep_master_live_events_data.participant_created_at IS 'Timestamp when participant registered (ISO 8601).';
COMMENT ON COLUMN nep_master_live_events_data.participant_updated_at IS 'Timestamp of last participant update (ISO 8601).';
COMMENT ON COLUMN nep_master_live_events_data.metadata_id IS 'Internal metadata record ID.';
COMMENT ON COLUMN nep_master_live_events_data.metadata_topic IS 'Topic from Zoom metadata.';
COMMENT ON COLUMN nep_master_live_events_data.metadata_join_url IS 'Zoom join URL.';
COMMENT ON COLUMN nep_master_live_events_data.metadata_start_time IS 'Start time from Zoom metadata (ISO 8601).';
COMMENT ON COLUMN nep_master_live_events_data.metadata_registrant_id IS 'Zoom registrant ID.';
COMMENT ON COLUMN nep_master_live_events_data.participant_email IS 'Participant''s email.';
COMMENT ON COLUMN nep_master_live_events_data.participant_user_id IS 'UUID of participant. Joins to user_id in the user table.';
COMMENT ON COLUMN nep_master_live_events_data.participant_client_name IS 'Client program of participant.';
COMMENT ON COLUMN nep_master_live_events_data.participant_first_name IS 'Participant''s first name.';
COMMENT ON COLUMN nep_master_live_events_data.participant_last_name IS 'Participant''s last name.';
COMMENT ON COLUMN nep_master_live_events_data.particpant_country IS 'Participant''s country. NOTE intentional typo in column name (missing ''i'').';
COMMENT ON COLUMN nep_master_live_events_data.rating_user_response_value IS 'Session rating (1-5).';
COMMENT ON COLUMN nep_master_live_events_data.rating_user_response_text IS 'Text feedback from rating.';
COMMENT ON COLUMN nep_master_live_events_data.feedback_user_id IS 'User ID linked to rating.';
COMMENT ON COLUMN nep_master_live_events_data.organiser_name IS 'Organiser display name.';

-- nep_master_user_table_sample_data: Master user registry. One row per registered user. Contains identity, profile status, acquisition channel and role information. Primary table for all user-level analysis.
COMMENT ON TABLE nep_master_user_table_sample_data IS 'One row per registered user (user_id is unique).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_id IS 'Primary key. UUID for the user. Hub key joined by activity, events and mentor tables.';
COMMENT ON COLUMN nep_master_user_table_sample_data.login_status IS 'User''s login / profile completion status. [enum: completedprofile, verifiedphone, not_entered_otp]';
COMMENT ON COLUMN nep_master_user_table_sample_data.profile_status IS 'Status of the user''s profile setup. [enum: completedprofile]';
COMMENT ON COLUMN nep_master_user_table_sample_data.phone_status IS 'Phone OTP verification status. Vocabulary confirmed against live data. [enum: verifiedphone, not_entered_otp]';
COMMENT ON COLUMN nep_master_user_table_sample_data.activity_date IS 'Date when the user record was last active or created.';
COMMENT ON COLUMN nep_master_user_table_sample_data.created_datetime IS 'Full timestamp of user account creation.';
COMMENT ON COLUMN nep_master_user_table_sample_data.otp_verified_date IS 'Date phone OTP was verified.';
COMMENT ON COLUMN nep_master_user_table_sample_data.otp_verified_datetime IS 'Full timestamp of OTP verification.';
COMMENT ON COLUMN nep_master_user_table_sample_data.profile_user_id IS 'UUID of the user''s profile record (often same as user_id).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_uuid IS 'Alternate UUID used across some subsystems.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_email IS 'User''s registered email address.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_first_name IS 'User''s first name.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_last_name IS 'User''s last name.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_profile_status IS 'Account activation status. [enum: ACTIVE]';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_country_code IS 'Country dial code (stored as text).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_phone_number IS 'User''s phone number.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_preferred_language IS 'ISO 639-1 language code.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_profile_completion_date IS 'Date the user completed their profile.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_type IS 'Whether user is internal staff, external entrepreneur, or incomplete. [enum: Internal Users, External Users, Incomplete Profile]';
COMMENT ON COLUMN nep_master_user_table_sample_data.company_type IS 'Type of company the user is associated with. [enum: startup, msme]';
COMMENT ON COLUMN nep_master_user_table_sample_data.company_revenue_range IS 'Revenue range bracket. [enum: above-5-crore, pre-revenue, 1-5-crore]';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_type_datekey1 IS 'Composite key for cohort segmentation (date + user_type + company).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_type_datekey2 IS 'As datekey1 with traffic source appended.';
COMMENT ON COLUMN nep_master_user_table_sample_data.traffic_source_source IS 'Acquisition source (UTM source).';
COMMENT ON COLUMN nep_master_user_table_sample_data.traffic_source_medium IS 'Acquisition medium (UTM medium).';
COMMENT ON COLUMN nep_master_user_table_sample_data.traffic_source_campaign IS 'Acquisition campaign name (UTM campaign).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_profile_updated_date IS 'Most recent date the user profile was modified.';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_role IS 'Role assigned to the user. [enum: STUDENT]';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_beta_feature IS 'Beta feature flag (mostly null).';
COMMENT ON COLUMN nep_master_user_table_sample_data.user_language_proficiency IS 'Language proficiency data.';
COMMENT ON COLUMN nep_master_user_table_sample_data.message_user_id IS 'UUID for the messaging / AI chat system.';
COMMENT ON COLUMN nep_master_user_table_sample_data.se_me_re_user_id IS 'UUID for the Expert Sessions / Mentoring / Resources module.';
COMMENT ON COLUMN nep_master_user_table_sample_data.jc_user_id IS 'UUID for the Jobs / Connections module.';

-- nep_mentor_profiles_sample_data: Mentor profiles. One row per mentor. Contains professional background, expertise, location and account status.
COMMENT ON TABLE nep_mentor_profiles_sample_data IS 'One row per mentor × profile-attribute combination (the row is exploded across program / industry / stage / education / employment). Neither user_id nor _id is unique — ~1,515 distinct mentors across ~49,486 rows (~33 rows per mentor). ALWAYS count mentors with COUNT(DISTINCT user_id), never COUNT(*).';
COMMENT ON COLUMN nep_mentor_profiles_sample_data._id IS 'MongoDB ObjectId — primary profile identifier.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.user_id IS 'UUID of mentor''s user account. Joins to user_id in the user table.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.first_name IS 'Mentor''s first name.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.last_name IS 'Mentor''s last name.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.email IS 'Mentor''s email.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.title IS 'Professional title / designation.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.bio IS 'Full professional biography.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.user_status IS 'Account status. [enum: ACTIVE, PENDING]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.visibility IS 'Profile visibility. [enum: PUBLIC, INTERNAL]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.preferred_language IS 'ISO 639-1 language code.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.created_at IS 'Timestamp when profile was created.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.updated_at IS 'Timestamp of last profile update.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.deleted IS 'Soft-delete flag. false = active.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.company_type IS 'Company affiliation type. Vocabulary confirmed against live data. [enum: CONNECT, LIST]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.linkedin_url IS 'LinkedIn profile URL.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.profile_image_url IS 'Profile photo URL.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.country IS 'Country where the mentor is based.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.state IS 'State / province of the mentor.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.city IS 'City of the mentor.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.role IS 'System role. Always MENTOR in this table. [enum: MENTOR]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.mentor_type IS 'Type of mentor engagement. [enum: MENTOR, EXPERT, SERVICE_PROVIDER]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.program IS 'NEP program(s) the mentor is associated with. Column is `program`, NOT `program_key`. [enum: ignite, liftoff-spark, liftoff-propel, liftoff, activate, fop, bootcamp, SMB, Ignite-self-serve, foundational, advanced, test]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.language_known IS 'Languages the mentor knows.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.stage_id IS 'Stage ID (stored as text).';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.stage_name IS 'Startup stage the mentor advises on. [enum: Pre Idea Stage, Idea Stage, Early Stage, Growth Stage, Traction Stage, Scale Stage, Demo Stage]';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.industry_id IS 'Industry ID (stored as text).';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.industry_name IS 'Industry sector.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.degree IS 'Highest educational degree.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.institute_name IS 'Educational institution.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.edu_start_date IS 'Education start date (free text, e.g. "September 2010").';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.graduation_date IS 'Graduation date (free text).';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.employer_name IS 'Current / recent employer.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.employment_sector IS 'Job title / role at employer.';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.emp_start_date IS 'Employment start date (free text).';
COMMENT ON COLUMN nep_mentor_profiles_sample_data.emp_end_date IS 'Employment end date (free text).';

RESET ROLE;

-- ===== 003_join_key_indexes.sql =====
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
