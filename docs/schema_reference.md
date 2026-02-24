# NEP User Analytics — Schema Reference

> **Purpose:** This document describes every column in all four Supabase tables. Use it as the primary reference when writing SQL queries to answer user questions about the NEP (National Entrepreneurship Program) platform.

---

## Table of Contents

1. [nep_master_user_table_sample_data](#1-nep_master_user_table_sample_data)
2. [nep_master_live_events_data](#2-nep_master_live_events_data)
3. [nep_liftoffx_data_sample](#3-nep_liftoffx_data_sample)
4. [nep_mentor_profiles_sample_data](#4-nep_mentor_profiles_sample_data)
5. [Table Relationships](#5-table-relationships)
6. [Common Query Patterns](#6-common-query-patterns)

---

## 1. `nep_master_user_table_sample_data`

**Description:** Master user registry. One row per registered user. Contains identity, profile status, acquisition channel, and role information. This is the primary table for user-level analysis.

| Column | Type | Description | Sample Values |
|--------|------|-------------|---------------|
| `user_id` | VARCHAR | Primary identifier for the user (UUID). Links to `se_me_re_user_id`, `message_user_id`, `jc_user_id`. | `582c9145-afe4-4370-8426-a9b7d8ef3c82` |
| `login_status` | VARCHAR | The user's current login/profile completion status. | `completedprofile` |
| `profile_status` | VARCHAR | Status of the user's profile setup. Usually matches `login_status`. | `completedprofile` |
| `phone_status` | VARCHAR | Whether the user's phone number has been OTP-verified. | `verifiedphone`, `NULL` |
| `activity_date` | VARCHAR | Date when the user record was last active or created (YYYY-MM-DD). | `2025-09-30`, `2025-10-01` |
| `created_datetime` | VARCHAR | Full timestamp of user account creation. | `2025-09-30 06:02:09.88` |
| `otp_verified_date` | VARCHAR | Date phone OTP was verified (YYYY-MM-DD). | `2025-09-30` |
| `otp_verified_datetime` | VARCHAR | Full timestamp of OTP verification. | `2025-09-30 06:02:09.88` |
| `profile_user_id` | VARCHAR | UUID of the user's profile record (often same as `user_id`). | `582c9145-afe4-4370-8426-a9b7d8ef3c82` |
| `user_uuid` | VARCHAR | Alternate UUID for the user, used across some subsystems. | `de8d009d-0ebe-427a-ab0d-3b2bd47282f3` |
| `user_email` | VARCHAR | User's registered email address. | `shashi.kiran@wadhwanifoundation.org` |
| `user_first_name` | VARCHAR | User's first name. | `Shashi` |
| `user_last_name` | VARCHAR | User's last name. | `Kiran` |
| `user_profile_status` | VARCHAR | Account activation status. | `ACTIVE`, `INACTIVE` |
| `user_country_code` | BIGINT | Country dial code (stored as number without `+`). | `91` (India) |
| `user_phone_number` | BIGINT | User's phone number (without country code). | `9880052168` |
| `user_preferred_language` | VARCHAR | ISO 639-1 language code for user's preferred language. | `en` (English), `kn` (Kannada), `hi` (Hindi) |
| `user_profile_completion_date` | VARCHAR | Date the user completed their profile (YYYY-MM-DD). | `2025-09-30` |
| `user_type` | VARCHAR | Whether the user is internal (Wadhwani staff) or external (entrepreneur). | `Internal Users`, `External Users` |
| `company_type` | VARCHAR | Type of company the user is associated with. | `startup`, `msme`, `NULL` |
| `company_revenue_range` | VARCHAR | Revenue range bracket for the user's company. | `above-5-crore`, `pre-revenue`, `NULL` |
| `user_type_datekey1` | VARCHAR | Composite key: `activity_date + user_type + company_type + company_revenue_range`. Used for cohort segmentation. | `2025-09-30Internal Usersstartupabove-5-crore` |
| `user_type_datekey2` | VARCHAR | Same as `user_type_datekey1` with traffic source appended. Used for acquisition cohort analysis. | `2025-09-30Internal Usersstartupabove-5-croreWAleaflet` |
| `traffic_source_source` | VARCHAR | Acquisition source (UTM source). | `WA` (WhatsApp), `meta`, `EEPC`, `NULL` |
| `traffic_source_medium` | VARCHAR | Acquisition medium (UTM medium). | `leaflet`, `social`, `Emailer`, `NULL` |
| `traffic_source_campaign` | VARCHAR | Acquisition campaign name (UTM campaign). | `test_campaign`, `NULL` |
| `user_profile_updated_date` | VARCHAR | Most recent date the user profile was modified (YYYY-MM-DD). | `2026-01-30` |
| `user_role` | VARCHAR | Role assigned to the user within the platform. | `STUDENT` |
| `user_beta_feature` | DOUBLE PRECISION | Flag or identifier for beta feature access (mostly null). | `NULL` |
| `user_language_proficiency` | DOUBLE PRECISION | Proficiency level in a language (mostly null in sample). | `NULL` |
| `message_user_id` | VARCHAR | UUID used to link to the messaging/AI chat system. Matches `user_id` when the user has used chat features. | `582c9145-afe4-4370-8426-a9b7d8ef3c82` |
| `se_me_re_user_id` | VARCHAR | UUID used to link to the SE/ME/RE (Expert Sessions, Mentoring, Resources) module. | `582c9145-afe4-4370-8426-a9b7d8ef3c82` |
| `jc_user_id` | VARCHAR | UUID used to link to the Jobs/Connections module. | `582c9145-afe4-4370-8426-a9b7d8ef3c82`, `NULL` |

---

## 2. `nep_master_live_events_data`

**Description:** Tracks live events (webinars, round tables, expert sessions) and each participant's attendance record. One row per **participant per event** — the same event appears multiple times (once per attendee). Use `GROUP BY event_id` when querying event-level metrics.

| Column | Type | Description | Sample Values |
|--------|------|-------------|---------------|
| `event_id` | VARCHAR | Unique MongoDB ObjectId for the event. | `68edcb24587478ed3b44e3b6` |
| `event_title` | VARCHAR | Full title of the event. May include a "Topic:" prefix. | `Topic: Growth Hacking 101: Driving Startup Growth Creatively` |
| `event_status` | VARCHAR | Current lifecycle status of the event. | `COMPLETED`, `UPCOMING`, `CANCELLED` |
| `country` | DOUBLE PRECISION | Country associated with the event (often null). | `NULL` |
| `provider` | VARCHAR | Organisation that hosted/provided the event. | `Wadhwani` |
| `organizer_id` | VARCHAR | UUID of the internal organiser who created the event. | `09615abe-825d-42f2-bd83-849427c70cae` |
| `client_name` | VARCHAR | Short code for the client program under which the event runs. | `WE` (Wadhwani Ecosystem), `NEP` |
| `description` | TEXT | Full-text description of the event including speaker bio. | Long paragraph text |
| `invite_type` | VARCHAR | Invitation visibility/access type. | `gap` (gap area session), `open` |
| `zoom_meeting_id` | BIGINT | Zoom meeting ID for the event. Used to join/track sessions. | `86419433672` |
| `participants_limit` | BIGINT | Maximum number of participants allowed. | `500` |
| `start_datetime` | VARCHAR | UTC start timestamp of the event (ISO 8601). | `2025-12-19T09:30:00Z` |
| `start_date` | VARCHAR | Date portion of the event start (YYYY-MM-DD). | `2025-12-19` |
| `end_datetime` | VARCHAR | UTC end timestamp of the event (ISO 8601). | `2025-12-19T11:00:00Z` |
| `language` | VARCHAR | Language in which the event is conducted. | `en` |
| `program_key` | VARCHAR | The NEP program this event belongs to. | `liftoff-propel`, `liftoff-spark`, `ignite` |
| `gapkey` | VARCHAR | The strategic "gap area" the event addresses. | `GrowthHacking`, `Finance`, `Marketing` |
| `topickey` | VARCHAR | Specific topic key within the gap area. | `GrowthHacking101`, `FinancialPlanning` |
| `sessiontype` | VARCHAR | Type of session format. | `roundTable`, `workshop`, `masterclass` |
| `created_at` | VARCHAR | Timestamp when the event record was created. | `2025-10-14` |
| `updated_at` | VARCHAR | Timestamp of the most recent event record update. | `2025-12-19` |
| `speaker_name` | VARCHAR | Full name of the event speaker. | `Neetu  bansal` |
| `speaker_email` | VARCHAR | Email address of the event speaker. | `neetu@businesskarya.com` |
| `speaker_bio` | DOUBLE PRECISION | Speaker biography (stored separately; NULL in this dataset). | `NULL` |
| `event_type` | VARCHAR | Technical delivery type. | `meeting` (Zoom meeting), `webinar` |
| `participant_id` | VARCHAR | Unique MongoDB ObjectId identifying this participant's registration record. | `6940c7423f94c24fd2eaab07` |
| `participant_status` | VARCHAR | Attendance outcome for this participant. | `NOSHOW`, `ATTENDED`, `REGISTERED` |
| `participant_created_at` | VARCHAR | Timestamp when the participant registered for the event. | `2025-12-16T02:43:14.713000Z` |
| `participant_updated_at` | VARCHAR | Timestamp when the participant record was last updated. | `2025-12-19T11:12:08.637000Z` |
| `metadata_id` | DOUBLE PRECISION | Internal metadata record ID (often null). | `NULL` |
| `metadata_topic` | VARCHAR | Topic string from the Zoom meeting metadata. | `Topic: Growth Hacking 101: ...` |
| `metadata_join_url` | VARCHAR | Full Zoom join URL for the participant. | `https://us06web.zoom.us/w/...` |
| `metadata_start_time` | VARCHAR | Start time from Zoom's metadata (UTC). | `2025-12-19T09:30:00Z` |
| `metadata_registrant_id` | VARCHAR | Zoom-assigned registrant ID for the participant. | `Qsv5zR9XRjCO8jk9anfqAA` |
| `participant_email` | VARCHAR | Email of the participant. Use to join with user tables. | `gk662266@gmail.com` |
| `participant_user_id` | VARCHAR | UUID of the participant (joins to `user_id` in user table). | `ae7d5fa4-6094-4462-8d77-10db48ce4e5c` |
| `participant_client_name` | VARCHAR | Client program the participant belongs to. | `NEP` |
| `participant_first_name` | VARCHAR | Participant's first name. | `Golu kumar` |
| `participant_last_name` | VARCHAR | Participant's last name. | `Baitha` |
| `particpant_country` | VARCHAR | Country of the participant *(note: typo in original — missing 'i')*. | `India`, `NULL` |
| `rating_user_response_value` | DOUBLE PRECISION | Numeric session rating given by the participant (1–5 scale). | `NULL` (mostly unpopulated) |
| `rating_user_response_text` | DOUBLE PRECISION | Text feedback from participant's rating (mostly null in dataset). | `NULL` |
| `feedback_user_id` | DOUBLE PRECISION | User ID linked to rating feedback (mostly null). | `NULL` |
| `organiser_name` | DOUBLE PRECISION | Organiser display name (mostly null, use `organizer_id`). | `NULL` |

---

## 3. `nep_liftoffx_data_sample`

**Description:** The central activity fact table. One row per **user activity event** (e.g. a page view, a chat message, a mentor session, a live event attendance). A single user can have many rows. Used for engagement, retention, funnel, and feature usage analysis. Includes data from GA4 (Google Analytics), AI chat interactions, mentor sessions, and live events.

| Column | Type | Description | Sample Values |
|--------|------|-------------|---------------|
| `last_active` | BIGINT | Ordinal rank of the user's most recent active day (1 = most recent week). | `1` |
| `week_activity_number` | BIGINT | Week number of activity relative to the user's signup week (1 = first week active). | `1`, `2`, `5` |
| `month_activity_number` | BIGINT | Month number of activity relative to the user's signup month (1 = first month). | `1`, `2` |
| `signup_year_monthnumber_weekstart_order` | BIGINT | Numeric sort key for the user's signup week (YYYYMMWW format for ordering). | `21`, `20` |
| `year_monthnumber_weekstart_order` | BIGINT | Numeric sort key for the activity week (for time-series ordering). | `21`, `20` |
| `signup_date` | VARCHAR | Date the user signed up (YYYY-MM-DD). | `2026-02-17`, `2025-10-03` |
| `signup_month_name` | VARCHAR | Short month name of the signup month. | `Feb`, `Oct` |
| `signup_month_number` | BIGINT | Numeric month of signup (1–12). | `2`, `10` |
| `user_type_datekey` | VARCHAR | Composite key: `signup_date + user_type + company_type + company_revenue_range`. Used for cohort grouping. | `2026-02-17External Usersmsmepre-revenue` |
| `userid` | VARCHAR | UUID of the user performing the activity. Joins to `user_id` in the user table. | `5b035997-cb86-4cba-83df-a9650c33613e` |
| `user_email` | VARCHAR | Email of the user. | `gunasharmi2007@gmail.com` |
| `user_first_name` | VARCHAR | User's first name. | `Sharmishta` |
| `user_last_name` | VARCHAR | User's last name. | `G` |
| `company_type` | VARCHAR | User's company type at time of activity. | `msme`, `startup`, `NULL` |
| `company_revenue_range` | VARCHAR | User's company revenue range. | `pre-revenue`, `above-5-crore`, `NULL` |
| `created_datetime` | VARCHAR | Full timestamp of user account creation. Format: `YYYY-MM-DD HH:MM:SS`. Use this column for date range filters on registration date. | `2025-09-30 06:02:09.88` |
| `activity_id` | VARCHAR | Unique identifier for this specific activity event (composite string). | `17713075002083751771307441` |
| `activity_type` | VARCHAR | Broad category of the activity. | `visitors`, `ai_chat`, `mentor_session`, `live_event`, `resource_view` |
| `activity_tittle` | VARCHAR | Specific name of the activity *(note: typo in original — double 't')*. Maps to GA4 event names for visitor events. | `homepage_landed`, `onboarding_skip_clicked`, `page_view`, `profile_change_language_clicked` |
| `conversation_id` | VARCHAR | ID of the AI chat conversation (populated only for `ai_chat` activity type). | `conv-abc123`, `NULL` |
| `conversation_parent_id` | DOUBLE PRECISION | Parent conversation ID for threaded chat (null if top-level). | `NULL` |
| `message_query` | VARCHAR | The user's question/message sent to the AI assistant. | `NULL` (only for ai_chat rows) |
| `message_query_id` | VARCHAR | Unique ID for the specific message query. | `NULL` |
| `message_rating` | DOUBLE PRECISION | User rating of the AI response (1–5). | `NULL` |
| `message_rating_feedback` | DOUBLE PRECISION | Free-text feedback on the AI response. | `NULL` |
| `response_type` | VARCHAR | Type of AI response generated. | `answer`, `clarification`, `NULL` |
| `response_content` | TEXT | Full text of the AI assistant's response. | Long text, `NULL` |
| `response_timestamp` | VARCHAR | Timestamp of the AI response (ISO 8601 UTC). | `2026-02-17T04:56:01.734000` |
| `response_flow_state` | VARCHAR | Final state of the AI response pipeline. | `completed`, `NULL` |
| `response_metricsblob` | VARCHAR | JSON blob with AI processing metrics (base64 encoded). Contains `processing_time`, `total_agents`, `total_tokens`, `sources_found`. | `{"blob": "eyJ...", "format": "application/json"}` |
| `message_date` | VARCHAR | Date of the AI chat message (YYYY-MM-DD). | `2026-02-17`, `NULL` |
| `session_rating` | DOUBLE PRECISION | Rating given by user for a mentor session (1–5). Populated only for mentor_session rows. | `NULL` |
| `mentor_rating` | DOUBLE PRECISION | Rating specifically for the mentor's performance. | `NULL` |
| `resources_rating` | DOUBLE PRECISION | Rating for resources shared during a session. | `NULL` |
| `mentor_id` | DOUBLE PRECISION | ID of the mentor involved in the session. Joins to `user_id` in mentor profiles table. | `NULL` |
| `mentor_name` | DOUBLE PRECISION | Name of the mentor (NULL in current sample). | `NULL` |
| `mentor_email` | DOUBLE PRECISION | Email of the mentor (NULL in current sample). | `NULL` |
| `connection_reason` | DOUBLE PRECISION | Reason the user connected with the mentor. | `NULL` |
| `event_id` | DOUBLE PRECISION | ID of the live event attended. Joins to `event_id` in live events table. | `NULL` |
| `event_date` | DOUBLE PRECISION | Date of the live event attended. | `NULL` |
| `event_time` | DOUBLE PRECISION | Time of the live event. | `NULL` |
| `event_source` | DOUBLE PRECISION | Source from which the user accessed the event. | `NULL` |
| `event_speaker` | DOUBLE PRECISION | Speaker at the event. | `NULL` |
| `event_gap_area` | DOUBLE PRECISION | Gap area covered by the event. | `NULL` |
| `expert_session_topic` | DOUBLE PRECISION | Topic of the expert session. | `NULL` |
| `ga_session_id` | DOUBLE PRECISION | Google Analytics 4 session ID. Groups all events in a single browser session. | `1771307441.0` |
| `ga_event_name` | VARCHAR | GA4 event name tracking specific user actions on the platform. | `homepage_landed`, `onboarding_skip_clicked`, `page_view`, `profile_change_language_clicked` |
| `ga_event_date` | VARCHAR | Date of the GA4 event (YYYY-MM-DD). | `2026-02-17` |
| `user_type` | VARCHAR | User classification (Internal staff or External entrepreneur). | `External Users`, `Internal Users` |
| `traffic_source_source` | VARCHAR | UTM source for the session acquisition. | `EEPC`, `ACIC BMU`, `NULL` |
| `traffic_source_medium` | VARCHAR | UTM medium for the session. | `Emailer`, `Email`, `NULL` |
| `traffic_source_campaign` | VARCHAR | UTM campaign name. | `EMAIL_CAMPAIGN_2025_04_11...`, `NULL` |
| `month_year` | VARCHAR | Human-readable month-year label for the activity. | `Feb 2026` |
| `month_year_order` | BIGINT | Numeric sort key for `month_year` (YYYYMM). | `202602`, `202510` |
| `signup_month_year` | VARCHAR | Human-readable month-year label for the user's signup month. | `Feb 2026`, `Oct 2025` |
| `signup_month_year_order` | BIGINT | Numeric sort key for `signup_month_year` (YYYYMM). | `202602`, `202510` |
| `signup_year` | BIGINT | Year the user signed up. | `2026`, `2025` |
| `month_name` | VARCHAR | Short name of the activity month. | `Feb`, `Oct` |
| `month_number` | BIGINT | Numeric month of the activity (1–12). | `2`, `10` |
| `week_range` | VARCHAR | Human-readable date range of the activity week. | `16 Feb - 22 Feb` |
| `signup_week_range` | VARCHAR | Human-readable date range of the user's signup week. | `16 Feb - 22 Feb`, `6 Oct - 12 Oct` |

---

## 4. `nep_mentor_profiles_sample_data`

**Description:** Profile records for mentors on the NEP platform. One row per mentor. Contains professional background, expertise areas, educational history, and employment details. Use this table to analyse mentor supply, filter by industry/stage expertise, or join with session data.

| Column | Type | Description | Sample Values |
|--------|------|-------------|---------------|
| `_id` | VARCHAR | MongoDB ObjectId — primary identifier for the mentor profile document. | `621385eaf83f050013d6bc04` |
| `user_id` | VARCHAR | UUID of the mentor's user account. Joins to `user_id` in the user table and `mentor_id` in the activity table. | `07ec5fd4-a107-4e6b-9225-0907308f19cd` |
| `first_name` | VARCHAR | Mentor's first name. | `Neetu`, `Rajesh` |
| `last_name` | VARCHAR | Mentor's last name. | `Bansal`, `Kumar` |
| `email` | VARCHAR | Mentor's email address. | `mentor-ptest1@yopmail.com` |
| `title` | VARCHAR | Professional title or designation of the mentor. | `Business Consultant at Biz Virtue Business Services LLC`, `CEO at EPIC TBI` |
| `bio` | TEXT | Full professional biography of the mentor. Used in event descriptions and profile pages. | Long paragraph text |
| `user_status` | VARCHAR | Account status of the mentor. | `ACTIVE`, `PENDING` |
| `visibility` | VARCHAR | Who can see the mentor's profile. | `PUBLIC` (visible to all users), `INTERNAL` (Wadhwani staff only) |
| `preferred_language` | VARCHAR | ISO 639-1 language code for the mentor's preferred language. | `en`, `es`, `pt` |
| `created_at` | VARCHAR | Timestamp when the mentor profile was created. | `2022-02-21 12:30:34.129` |
| `updated_at` | VARCHAR | Timestamp of the last profile update. | `2022-11-30 14:40:53.224` |
| `deleted` | BOOLEAN | Soft-delete flag. `false` = active; `true` = deleted/deactivated. | `false` |
| `company_type` | VARCHAR | Type of company affiliation for the mentor. | `CONNECT` (part of Wadhwani Connect network), `NULL` |
| `linkedin_url` | TEXT | LinkedIn profile URL of the mentor. | `https://in.linkedin.com/` |
| `profile_image_url` | VARCHAR | URL of the mentor's profile photo (hosted on Azure Blob Storage). | `https://wefileserviceprod.blob.core.windows.net/profile-images/...` |
| `country` | VARCHAR | Country where the mentor is based. | `India`, `Nigeria`, `Mexico`, `Brasil` |
| `state` | VARCHAR | State/province of the mentor's location. | `Karnataka`, `Maharashtra`, `Telangana` |
| `city` | VARCHAR | City of the mentor's location. | `Bangalore`, `Mumbai`, `Hyderabad` |
| `role` | VARCHAR | System role assigned to this user. Always `MENTOR` in this table. | `MENTOR` |
| `mentor_type` | VARCHAR | Type of mentor engagement. | `MENTOR` (regular mentoring), `EXPERT` (expert/guest sessions only) |
| `program` | VARCHAR | NEP program(s) the mentor is associated with. | `ignite`, `liftoff-spark`, `liftoff`, `liftoff-propel` |
| `language_known` | DOUBLE PRECISION | Languages the mentor is proficient in (stored as ID, mostly null in dataset). | `NULL` |
| `stage_id` | BIGINT | Numeric ID of the startup stage the mentor specialises in. Joins to `stage_name`. | `1`, `2`, `3`, `4`, `5` |
| `stage_name` | VARCHAR | Human-readable startup stage the mentor can advise on. | `Pre Idea Stage`, `Idea Stage`, `Early Stage`, `Growth Stage`, `Demo Stage` |
| `industry_id` | DOUBLE PRECISION | Numeric ID of the industry vertical the mentor covers. Joins to `industry_name`. | `1.0`, `15.0`, `16.0` |
| `industry_name` | VARCHAR | Industry sector the mentor specialises in. | `Services`, `Real Estate & Housing`, `Gaming`, `Mobility`, `FinTech` |
| `degree` | VARCHAR | Highest educational degree earned by the mentor. | `Doctor of Philosophy - PhD, Computer Science`, `Bachelor of Engineering (B.E.)` |
| `institute_name` | VARCHAR | Name of the educational institution where the degree was earned. | `MJRP University - India`, `Bangalore University` |
| `edu_start_date` | VARCHAR | Start date of the educational programme (free text). | `September 2010`, `January 1999` |
| `graduation_date` | VARCHAR | Graduation/completion date of the educational programme (free text). | `March 2017`, `December 2002` |
| `employer_name` | VARCHAR | Current or most recent employer's name. | `BPCCS-BCA`, `Freelance` |
| `employment_sector` | VARCHAR | Job title or role at the employer. | `Lecturer`, `Associate Professor`, `Startup Mentor` |
| `emp_start_date` | VARCHAR | Employment start date (free text). | `June 2005`, `January 2020` |
| `emp_end_date` | VARCHAR | Employment end date (free text; NULL if currently employed). | `June 2008`, `NULL` |

---

## 5. Table Relationships

```
nep_master_user_table_sample_data
  └── user_id ──────────────────────────────────────────────────────────────────────────┐
        ├── se_me_re_user_id (same column, alias for expert/mentor/resource module)      │
        ├── message_user_id  (same column, alias for AI chat module)                    │
        └── jc_user_id       (same column, alias for Jobs/Connections module)            │
                                                                                         │
nep_master_live_events_data                                                              │
  └── participant_user_id ── joins to ─► user_id ◄───────────────────────────────────── ┘
  └── participant_email   ── joins to ─► user_email (fallback if UUID unavailable)

nep_liftoffx_data_sample (activity fact table)
  └── userid      ── joins to ─► user_id in nep_master_user_table_sample_data
  └── event_id    ── joins to ─► event_id in nep_master_live_events_data
  └── mentor_id   ── joins to ─► user_id in nep_mentor_profiles_sample_data

nep_mentor_profiles_sample_data
  └── user_id     ── joins to ─► user_id in nep_master_user_table_sample_data
```

---

## 6. Common Query Patterns

### Count total registered users by type
```sql
SELECT user_type, COUNT(*) AS user_count
FROM nep_master_user_table_sample_data
GROUP BY user_type
ORDER BY user_count DESC;
```

### Count users by acquisition source
```sql
SELECT traffic_source_source, traffic_source_medium, COUNT(*) AS users
FROM nep_master_user_table_sample_data
WHERE traffic_source_source IS NOT NULL
GROUP BY traffic_source_source, traffic_source_medium
ORDER BY users DESC;
```

### List completed events with attendance counts
```sql
SELECT
  event_id,
  event_title,
  start_date,
  program_key,
  sessiontype,
  COUNT(*) AS registrations,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END) AS attended,
  SUM(CASE WHEN participant_status = 'NOSHOW' THEN 1 ELSE 0 END) AS no_shows
FROM nep_master_live_events_data
WHERE event_status = 'COMPLETED'
GROUP BY event_id, event_title, start_date, program_key, sessiontype
ORDER BY start_date DESC;
```

### Get weekly active users
```sql
SELECT week_range, COUNT(DISTINCT userid) AS weekly_active_users
FROM nep_liftoffx_data_sample
GROUP BY week_range, month_year_order
ORDER BY month_year_order ASC;
```

### Find top GA4 events (user actions on platform)
```sql
SELECT ga_event_name, COUNT(*) AS occurrences
FROM nep_liftoffx_data_sample
WHERE ga_event_name IS NOT NULL
GROUP BY ga_event_name
ORDER BY occurrences DESC;
```

### List mentors by industry and stage
```sql
SELECT
  first_name, last_name, email,
  industry_name, stage_name,
  country, mentor_type, user_status
FROM nep_mentor_profiles_sample_data
WHERE user_status = 'ACTIVE'
  AND deleted = false
ORDER BY industry_name, stage_name;
```

### Join users with their activity events
```sql
SELECT
  u.user_email, u.user_type, u.company_type,
  a.activity_type, a.activity_tittle, a.ga_event_date
FROM nep_master_user_table_sample_data u
JOIN nep_liftoffx_data_sample a ON u.user_id = a.userid
ORDER BY a.ga_event_date DESC;
```

### Show event attendance for a specific program
```sql
SELECT
  e.event_title,
  e.start_date,
  e.gapkey,
  e.topickey,
  e.participant_status,
  COUNT(*) AS count
FROM nep_master_live_events_data e
WHERE e.program_key = 'liftoff-propel'
GROUP BY e.event_title, e.start_date, e.gapkey, e.topickey, e.participant_status
ORDER BY e.start_date DESC;
```
