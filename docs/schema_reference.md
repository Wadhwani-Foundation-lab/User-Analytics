# NEP User Analytics — Schema Reference

> **Purpose:** This document describes every column in all four Supabase tables.
> Use it as the **authoritative** reference when writing SQL queries.
> All types shown below are the **actual database types** verified via `information_schema.columns`.

---

## 1. `nep_master_user_table_sample_data`

> Master user registry. One row per registered user. Contains identity, profile status, acquisition channel, and role information. This is the primary table for all user-level analysis.

| Column | DB Type | Description | Sample Values |
|--------|---------|-------------|---------------|
| `user_id` | TEXT | **Primary key.** UUID for the user. Links to `userid` in activity table, `participant_user_id` in events table, `user_id` in mentor table. | `582c9145-afe4-4370-8426-a9b7d8ef3c82` |
| `login_status` | TEXT | User's login/profile completion status. | `completedprofile`, `verifiedphone`, `not_entered_otp` |
| `profile_status` | TEXT | Status of the user's profile setup. | `completedprofile` |
| `phone_status` | TEXT | Phone OTP verification status. | `verifiedphone`, `NULL` |
| `activity_date` | **DATE** | Date when user record was last active or created. | `2025-09-30` |
| `created_datetime` | **TIMESTAMP** | Full timestamp of user account creation. | `2025-09-30 06:02:09.88` |
| `otp_verified_date` | **DATE** | Date phone OTP was verified. | `2025-09-30` |
| `otp_verified_datetime` | **TIMESTAMP** | Full timestamp of OTP verification. | `2025-09-30 06:02:09.88` |
| `profile_user_id` | TEXT | UUID of the user's profile record (often same as `user_id`). | UUID |
| `user_uuid` | TEXT | Alternate UUID used across some subsystems. | UUID |
| `user_email` | TEXT | User's registered email address. | `shashi.kiran@wadhwanifoundation.org` |
| `user_first_name` | TEXT | User's first name. | `Shashi` |
| `user_last_name` | TEXT | User's last name. | `Kiran` |
| `user_profile_status` | TEXT | Account activation status. | `ACTIVE` |
| `user_country_code` | TEXT | Country dial code (stored as text). | `91` |
| `user_phone_number` | TEXT | User's phone number. | `9880052168` |
| `user_preferred_language` | TEXT | ISO 639-1 language code. | `en`, `kn`, `hi` |
| `user_profile_completion_date` | **DATE** | Date the user completed their profile. | `2025-09-30` |
| `user_type` | TEXT | Whether user is internal staff, external entrepreneur, or incomplete. | `Internal Users`, `External Users`, `Incomplete Profile` |
| `company_type` | TEXT | Type of company the user is associated with. | `startup`, `msme`, `NULL` |
| `company_revenue_range` | TEXT | Revenue range bracket. | `above-5-crore`, `pre-revenue`, `1-5-crore`, `NULL` |
| `user_type_datekey1` | TEXT | Composite key for cohort segmentation. | `2025-09-30Internal Usersstartupabove-5-crore` |
| `user_type_datekey2` | TEXT | Same with traffic source appended. | `2025-09-30Internal Usersstartupabove-5-croreWAleaflet` |
| `traffic_source_source` | TEXT | Acquisition source (UTM source). | `WA`, `meta`, `EEPC`, `DevX`, `NULL` |
| `traffic_source_medium` | TEXT | Acquisition medium (UTM medium). | `leaflet`, `social`, `Emailer`, `Email`, `NULL` |
| `traffic_source_campaign` | TEXT | Acquisition campaign name (UTM campaign). | `test_campaign`, `NULL` |
| `user_profile_updated_date` | **DATE** | Most recent date the user profile was modified. | `2026-01-30` |
| `user_role` | TEXT | Role assigned to the user. | `STUDENT` |
| `user_beta_feature` | TEXT | Beta feature flag (mostly null). | `NULL` |
| `user_language_proficiency` | JSONB | Language proficiency data. | `NULL` |
| `message_user_id` | TEXT | UUID for messaging/AI chat system. | UUID or `NULL` |
| `se_me_re_user_id` | TEXT | UUID for Expert Sessions/Mentoring/Resources module. | UUID or `NULL` |
| `jc_user_id` | TEXT | UUID for Jobs/Connections module. | UUID or `NULL` |

---

## 2. `nep_liftoffx_data_sample`

> Central activity fact table. One row per **user activity event**. A single user can have many rows. Used for engagement, retention, funnel, and feature usage analysis.

**IMPORTANT NOTES:**
- This table does NOT have a column called `created_datetime`. It has `created_at` (DATE).
- This table DOES have `company_type`, `company_revenue_range`, `user_type`, `traffic_source_source`, `traffic_source_medium`, `traffic_source_campaign` — these are duplicated from the user table for convenience.
- Foreign key to users: `userid` (no underscore!)

| Column | DB Type | Description | Sample Values |
|--------|---------|-------------|---------------|
| `last_active` | BIGINT | Ordinal rank of user's most recent active day. | `1` |
| `week_activity_number` | BIGINT | Week number relative to signup week. | `1`, `2`, `5` |
| `month_activity_number` | BIGINT | Month number relative to signup month. | `1`, `2` |
| `signup_year_monthnumber_weekstart_order` | BIGINT | Numeric sort key for signup week. | `21`, `20` |
| `year_monthnumber_weekstart_order` | BIGINT | Numeric sort key for activity week. | `21`, `20` |
| `signup_date` | **DATE** | Date the user signed up. | `2026-02-17`, `2025-10-03` |
| `signup_month_name` | TEXT | Short month name of signup month. | `Feb`, `Oct` |
| `signup_month_number` | TEXT | Numeric month of signup (as text). | `2`, `10` |
| `user_type_datekey` | TEXT | Composite key for cohort grouping. | `2026-02-17External Usersmsmepre-revenue` |
| `userid` | TEXT | **Foreign key** to `user_id` in user table. **No underscore!** | UUID |
| `user_email` | TEXT | Email of the user. | `gunasharmi2007@gmail.com` |
| `user_first_name` | TEXT | User's first name. | `Sharmishta` |
| `user_last_name` | TEXT | User's last name. | `G` |
| `company_type` | TEXT | User's company type. Same values as user table. | `msme`, `startup`, `NULL` |
| `company_revenue_range` | TEXT | User's company revenue range. Same values as user table. | `pre-revenue`, `above-5-crore`, `1-5-crore`, `NULL` |
| `created_at` | **DATE** | Date this activity record was created. | `2025-09-30`, `2025-10-01` |
| `activity_id` | TEXT | Unique identifier for this activity event. | `17713075002083751771307441` |
| `activity_type` | TEXT | **Broad category of activity.** See exact values table below. | `message`, `visitors`, `mentor` |
| `activity_tittle` | TEXT | Specific name of the activity *(note: typo — double 't')*. | `homepage_landed`, `page_view` |
| `conversation_id` | TEXT | AI chat conversation ID (only for message activity). | `conv-abc123`, `NULL` |
| `conversation_parent_id` | TEXT | Parent conversation ID for threaded chat. | `NULL` |
| `message_query` | TEXT | User's question sent to AI assistant. | text or `NULL` |
| `message_query_id` | TEXT | Unique ID for the message query. | `NULL` |
| `message_rating` | TEXT | User rating of the AI response. | `NULL` |
| `message_rating_feedback` | TEXT | Free-text feedback on AI response. | `NULL` |
| `response_type` | TEXT | Type of AI response generated. | `answer`, `clarification`, `NULL` |
| `response_content` | TEXT | Full text of AI response. | text or `NULL` |
| `response_timestamp` | TEXT | Timestamp of AI response (ISO 8601 UTC). | `2026-02-17T04:56:01.734000` |
| `response_flow_state` | TEXT | Final state of AI response pipeline. | `completed`, `NULL` |
| `response_metricsblob` | TEXT | JSON blob with AI processing metrics. | JSON string or `NULL` |
| `message_date` | **DATE** | Date of the AI chat message. | `2026-02-17`, `NULL` |
| `session_rating` | TEXT | Rating for a mentor session. | `NULL` |
| `mentor_rating` | TEXT | Rating for the mentor. | `NULL` |
| `resources_rating` | TEXT | Rating for resources. | `NULL` |
| `mentor_id` | TEXT | ID of the mentor. Joins to `user_id` in mentor table. | UUID or `NULL` |
| `mentor_name` | TEXT | Name of the mentor. | `NULL` |
| `mentor_email` | TEXT | Email of the mentor. | `NULL` |
| `connection_reason` | TEXT | Reason for mentor connection. | `NULL` |
| `event_id` | TEXT | ID of live event attended. | `NULL` |
| `event_date` | TEXT | Date of the live event. | `NULL` |
| `event_time` | TEXT | Time of the live event. | `NULL` |
| `event_source` | TEXT | Source from which user accessed event. | `NULL` |
| `event_speaker` | TEXT | Speaker at the event. | `NULL` |
| `event_gap_area` | TEXT | Gap area covered by the event. | `NULL` |
| `expert_session_topic` | TEXT | Topic of expert session. | `NULL` |
| `ga_session_id` | TEXT | Google Analytics 4 session ID. | `1771307441` |
| `ga_event_name` | TEXT | GA4 event name. See full list in Section 6. | `homepage_landed`, `page_view` |
| `ga_event_date` | **DATE** | Date of the GA4 event. Actual DATE type. | `2026-02-17` |
| `user_type` | TEXT | User classification. Same as user table. | `External Users`, `Internal Users` |
| `traffic_source_source` | TEXT | UTM source. Same as user table. | `EEPC`, `meta`, `NULL` |
| `traffic_source_medium` | TEXT | UTM medium. Same as user table. | `Emailer`, `Email`, `social`, `NULL` |
| `traffic_source_campaign` | TEXT | UTM campaign name. Same as user table. | campaign name or `NULL` |
| `month_year` | TEXT | Human-readable month-year label. | `Feb 2026`, `Oct 2025` |
| `month_year_order` | TEXT | Sort key for `month_year` (YYYYMM as text). | `202602`, `202510` |
| `signup_month_year` | TEXT | Human-readable signup month-year label. | `Feb 2026`, `Oct 2025` |
| `signup_month_year_order` | TEXT | Sort key for `signup_month_year` (YYYYMM as text). | `202602`, `202510` |
| `signup_year` | INTEGER | Year the user signed up. | `2026`, `2025` |
| `month_name` | TEXT | Short name of activity month. | `Feb`, `Oct` |
| `month_number` | TEXT | Numeric month of activity (as text). | `2`, `10` |
| `week_range` | TEXT | Human-readable date range of activity week. | `16 Feb - 22 Feb` |
| `signup_week_range` | TEXT | Date range of signup week. | `16 Feb - 22 Feb` |

### Exact `activity_type` Values (use ONLY these)

| Value | Meaning |
|-------|---------|
| `'message'` | AI chat — user asked a question |
| `'mentor'` | Mentor session interaction |
| `'session'` | Live event / webinar attendance |
| `'resource'` | Resource / content view |
| `'visitors'` | Anonymous site visit |
| `'repeat visitors'` | Return site visit |
| `'signup'` | New user registration event |
| `'jounrney_explore'` | Journey / learning path click (typo in DB) |
| `'introductory_video_reg_users'` | Introductory video view |

**NEVER** use `'ai_chat'`, `'mentor_session'`, `'live_event'`, or `'resource_view'` — these do NOT exist.

---

## 3. `nep_master_live_events_data`

> Tracks live events and each participant's attendance record. One row per **participant per event**. Use `GROUP BY event_id` for event-level metrics.

| Column | DB Type | Description | Sample Values |
|--------|---------|-------------|---------------|
| `event_id` | TEXT | Unique ID for the event. | `68edcb24587478ed3b44e3b6` |
| `event_title` | TEXT | Full title of the event. | `Topic: Growth Hacking 101: ...` |
| `event_status` | TEXT | Event lifecycle status. **Exact values: `COMPLETED`, `OPEN`**. | `COMPLETED`, `OPEN` |
| `country` | TEXT | Country for the event. | `NULL` |
| `provider` | TEXT | Organisation that hosted the event. | `Wadhwani` |
| `organizer_id` | TEXT | UUID of the organiser. | UUID |
| `client_name` | TEXT | Client program short code. | `WE`, `NEP` |
| `description` | TEXT | Full event description. | Long text |
| `invite_type` | TEXT | Invitation visibility type. | `gap`, `open` |
| `zoom_meeting_id` | TEXT | Zoom meeting ID. | `86419433672` |
| `participants_limit` | TEXT | Maximum participants (stored as text). | `500` |
| `start_datetime` | TEXT | UTC start timestamp (ISO 8601). | `2025-12-19T09:30:00Z` |
| `start_date` | **DATE** | Date of event start. | `2025-12-19` |
| `end_datetime` | TEXT | UTC end timestamp. | `2025-12-19T11:00:00Z` |
| `language` | TEXT | Language of the event. | `en` |
| `program_key` | TEXT | NEP program this event belongs to. **Exact values: `liftoff-propel`, `liftoff`, `liftoff-spark`**. | `liftoff-propel` |
| `gapkey` | TEXT | Strategic gap area. See full list in Section 6. | `GrowthHacking`, `StartupFinancials` |
| `topickey` | TEXT | Specific topic key. | `GrowthHacking101` |
| `sessiontype` | TEXT | Session format. **Exact values: `expertSession`, `roundTable`**. | `expertSession`, `roundTable` |
| `created_at` | **DATE** | Date when event record was created. | `2025-10-14` |
| `updated_at` | **DATE** | Date of most recent event update. | `2025-12-19` |
| `speaker_name` | TEXT | Full name of the speaker. | `Neetu  bansal` |
| `speaker_email` | TEXT | Speaker's email. | `neetu@businesskarya.com` |
| `speaker_bio` | TEXT | Speaker biography. | `NULL` |
| `event_type` | TEXT | Technical delivery type. | `meeting`, `webinar` |
| `participant_id` | TEXT | Unique ID for this registration. | MongoDB ObjectId |
| `participant_status` | TEXT | Attendance outcome. **Exact values: `ATTENDED`, `NOSHOW`, `REGISTERED`**. | `ATTENDED` |
| `participant_created_at` | TEXT | Timestamp when participant registered. | ISO 8601 |
| `participant_updated_at` | TEXT | Timestamp of last participant update. | ISO 8601 |
| `metadata_id` | TEXT | Internal metadata record ID. | `NULL` |
| `metadata_topic` | TEXT | Topic from Zoom metadata. | `Topic: Growth Hacking 101: ...` |
| `metadata_join_url` | TEXT | Zoom join URL. | URL |
| `metadata_start_time` | TEXT | Start time from Zoom metadata. | ISO 8601 |
| `metadata_registrant_id` | TEXT | Zoom registrant ID. | `Qsv5zR9XRjCO8jk9anfqAA` |
| `participant_email` | TEXT | Participant's email. | `gk662266@gmail.com` |
| `participant_user_id` | TEXT | UUID of participant. **Joins to `user_id` in user table.** | UUID |
| `participant_client_name` | TEXT | Client program of participant. | `NEP` |
| `participant_first_name` | TEXT | Participant's first name. | `Golu kumar` |
| `participant_last_name` | TEXT | Participant's last name. | `Baitha` |
| `particpant_country` | TEXT | Participant's country *(typo: missing 'i')*. | `India`, `NULL` |
| `rating_user_response_value` | INTEGER | Session rating (1–5). | `NULL` |
| `rating_user_response_text` | TEXT | Text feedback from rating. | `NULL` |
| `feedback_user_id` | TEXT | User ID linked to rating. | `NULL` |
| `organiser_name` | TEXT | Organiser display name. | `NULL` |

---

## 4. `nep_mentor_profiles_sample_data`

> Mentor profiles. One row per mentor. Contains professional background, expertise, and account status.

| Column | DB Type | Description | Sample Values |
|--------|---------|-------------|---------------|
| `_id` | TEXT | MongoDB ObjectId — primary profile identifier. | `621385eaf83f050013d6bc04` |
| `user_id` | TEXT | UUID of mentor's user account. **Joins to `user_id` in user table.** | UUID |
| `first_name` | TEXT | Mentor's first name. | `Neetu`, `Rajesh` |
| `last_name` | TEXT | Mentor's last name. | `Bansal`, `Kumar` |
| `email` | TEXT | Mentor's email. | `mentor-ptest1@yopmail.com` |
| `title` | TEXT | Professional title/designation. | `Business Consultant at Biz Virtue` |
| `bio` | TEXT | Full professional biography. | Long text |
| `user_status` | TEXT | Account status. **Exact values: `ACTIVE`, `PENDING`**. | `ACTIVE` |
| `visibility` | TEXT | Profile visibility. | `PUBLIC`, `INTERNAL` |
| `preferred_language` | TEXT | ISO 639-1 language code. | `en`, `es`, `pt` |
| `created_at` | **TIMESTAMP** | Timestamp when profile was created. | `2022-02-21 12:30:34.129` |
| `updated_at` | **TIMESTAMP** | Timestamp of last profile update. | `2022-11-30 14:40:53.224` |
| `deleted` | BOOLEAN | Soft-delete flag. `false` = active. | `false`, `true` |
| `company_type` | TEXT | Company affiliation type. | `CONNECT`, `NULL` |
| `linkedin_url` | TEXT | LinkedIn profile URL. | URL |
| `profile_image_url` | TEXT | Profile photo URL. | URL |
| `country` | TEXT | Country where mentor is based. | `India`, `Nigeria`, `Mexico` |
| `state` | TEXT | State/province of mentor. | `Karnataka`, `Maharashtra` |
| `city` | TEXT | City of mentor. | `Bangalore`, `Mumbai` |
| `role` | TEXT | System role. Always `MENTOR` here. | `MENTOR` |
| `mentor_type` | TEXT | Type of mentor engagement. **Exact values: `MENTOR`, `EXPERT`, `SERVICE_PROVIDER`**. | `MENTOR` |
| `program` | TEXT | NEP program(s) the mentor is associated with. **Note: column is `program` (not `program_key`).** | `ignite`, `liftoff-spark`, `liftoff-propel`, `liftoff`, `activate`, `fop`, `bootcamp`, `SMB`, `Ignite-self-serve`, `foundational`, `advanced`, `test` |
| `language_known` | TEXT | Languages the mentor knows. | `NULL` |
| `stage_id` | TEXT | Stage ID (stored as text). | `1`, `2`, `3`, `4`, `5` |
| `stage_name` | TEXT | Startup stage the mentor advises on. **Exact values: `Pre Idea Stage`, `Idea Stage`, `Early Stage`, `Growth Stage`, `Traction Stage`, `Scale Stage`, `Demo Stage`**. | `Early Stage` |
| `industry_id` | TEXT | Industry ID (stored as text). | `1`, `15` |
| `industry_name` | TEXT | Industry sector. | `Services`, `FinTech`, `Gaming`, `Real Estate & Housing`, `Mobility` |
| `degree` | TEXT | Highest educational degree. | `Doctor of Philosophy - PhD, Computer Science` |
| `institute_name` | TEXT | Educational institution. | `Bangalore University` |
| `edu_start_date` | TEXT | Education start date (free text). | `September 2010` |
| `graduation_date` | TEXT | Graduation date (free text). | `March 2017` |
| `employer_name` | TEXT | Current/recent employer. | `BPCCS-BCA`, `Freelance` |
| `employment_sector` | TEXT | Job title/role at employer. | `Lecturer`, `Startup Mentor` |
| `emp_start_date` | TEXT | Employment start date (free text). | `June 2005` |
| `emp_end_date` | TEXT | Employment end date. | `June 2008`, `NULL` |

---

## 5. Table Relationships

```
nep_master_user_table_sample_data
  └── user_id (PK) ──────────────────────────────────────────────┐
        ├── se_me_re_user_id (alias for expert/mentor/resource)  │
        ├── message_user_id  (alias for AI chat)                 │
        └── jc_user_id       (alias for Jobs/Connections)        │
                                                                  │
nep_liftoffx_data_sample (activity fact table)                   │
  └── userid (FK, NO underscore) ─► user_id ◄────────────────────┘
  └── mentor_id ─► user_id in nep_mentor_profiles_sample_data

nep_master_live_events_data
  └── participant_user_id (FK) ─► user_id in user table

nep_mentor_profiles_sample_data
  └── user_id (FK) ─► user_id in user table
```

### JOIN Keys Quick Reference

| From Table | FK Column | To Table | PK Column |
|------------|-----------|----------|-----------|
| `nep_liftoffx_data_sample` | `userid` | `nep_master_user_table_sample_data` | `user_id` |
| `nep_master_live_events_data` | `participant_user_id` | `nep_master_user_table_sample_data` | `user_id` |
| `nep_mentor_profiles_sample_data` | `user_id` | `nep_master_user_table_sample_data` | `user_id` |
| `nep_liftoffx_data_sample` | `mentor_id` | `nep_mentor_profiles_sample_data` | `user_id` |

---

## 6. Reference Values

### `gapkey` values (live events)
`AdvancedCustomerAcquisition`, `BusinessModelCanvas`, `CompetitiveStrategy`, `CustomerRetention`, `FounderDNA`, `GotoMarketStrategy`, `GrowthHacking`, `MarketAnalysisCustomerInsights`, `MetricsandAnalytics`, `PitchMastery`, `PivotPersevere`, `ProductIteration`, `ScalableBusinessModel`, `StartupFinancials`

### `ga_event_name` values (activity table)
`chat_item_delete_clicked`, `chat_item_selected`, `chat_main_tab_clicked`, `chat_rating_submitted`, `chat_sidebar_toggle_clicked`, `chat_step_selected`, `chat_step_tab_clicked`, `chat_tab_clicked`, `chat_tab_close_clicked`, `Clicked on a Resource`, `Clicked on About Us`, `Clicked on Apply`, `Clicked on Conversation History`, `Clicked on Guided Questions`, `Clicked on Hire`, `Clicked on Mic`, `Clicked on Programs`, `Clicked on related question`, `Clicked on Sticky section - Mentor`, `Clicked on Sticky section - Resources`, `Clicked on Sticky section - Sessions`, `Clicked on Video inside response`, `Clicked on View Details`, `Clicked on View Profile`, `dropdown_tab_item_clicked`, `event_cta_button_clicked`, `home_button`, `homepage_landed`, `insight_card_clicked`, `introductory_video_clicked`, `journey_step_explore_clicked`, `lfx_ai_assistant_card_clicked`, `lfx_expert_insight_video_clicked`, `Loaded Login Page`, `loader_tab_clicked`, `mentor_profile_back_clicked`, `mentor_profile_page_landed`, `mentor_profile_send_request_clicked`, `mentors_tab_clicked`, `mentors_view_profile_clicked`, `navigation_tab_clicked`, `new_response_back_button_clicked`, `onboarding_back_clicked`, `onboarding_i_understand_clicked`, `onboarding_next_clicked`, `onboarding_skip_clicked`, `otp_verification_success`, `page_view`, `popup_mentors_tab_clicked`, `popup_resources_tab_clicked`, `popup_sessions_tab_clicked`, `popup_tab_clicked`, `popup_tab_switched`, `profile_change_language_clicked`, `profile_dropdown_opened`, `profile_logout_clicked`, `recent_chat_clicked`, `Register Sessions`, `resend_otp_success`, `resources_tab_clicked`, `send_otp_button_clicked`, `Sent Request`, `session_start`, `sessions_register_clicked`, `sessions_tab_clicked`, `terms_checkbox_clicked`, `testimonial_video_clicked`, `text_submit_button_clicked`, `thumbs_down_clicked`, `thumbs_up_clicked`, `User Registration`, `user_engagement`, `verify_otp_button_clicked`

---

## 7. Common Query Patterns

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
  MAX(event_title) AS event_title,
  MAX(start_date) AS start_date,
  MAX(program_key) AS program_key,
  MAX(sessiontype) AS session_type,
  COUNT(*) AS registrations,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END) AS attended,
  SUM(CASE WHEN participant_status = 'NOSHOW' THEN 1 ELSE 0 END) AS no_shows
FROM nep_master_live_events_data
WHERE event_status = 'COMPLETED'
GROUP BY event_id
ORDER BY start_date DESC;
```

### Get weekly active users
```sql
SELECT week_range, COUNT(DISTINCT userid) AS weekly_active_users
FROM nep_liftoffx_data_sample
GROUP BY week_range, month_year_order
ORDER BY month_year_order ASC;
```

### Join users with activity (correct JOIN key)
```sql
SELECT u.user_email, u.user_type, a.activity_type, a.ga_event_date
FROM nep_master_user_table_sample_data u
JOIN nep_liftoffx_data_sample a ON u.user_id = a.userid
ORDER BY a.ga_event_date DESC
LIMIT 500;
```

### Monthly event breakdown (use TO_CHAR on start_date)
```sql
SELECT
  TO_CHAR(start_date, 'YYYY-MM') AS month,
  COUNT(DISTINCT event_id) AS total_events,
  COUNT(*) AS total_registrations,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END) AS attended
FROM nep_master_live_events_data
WHERE start_date IS NOT NULL
GROUP BY TO_CHAR(start_date, 'YYYY-MM')
ORDER BY month ASC
LIMIT 500;
```

### Mentors by program and industry
```sql
SELECT program, industry_name, COUNT(DISTINCT user_id) AS mentor_count
FROM nep_mentor_profiles_sample_data
WHERE user_status = 'ACTIVE' AND deleted = false
GROUP BY program, industry_name
ORDER BY program, mentor_count DESC
LIMIT 500;
```

### Activity by month (use pre-built month_year columns)
```sql
SELECT month_year, month_year_order, activity_type,
  COUNT(*) AS total_events, COUNT(DISTINCT userid) AS unique_users
FROM nep_liftoffx_data_sample
GROUP BY month_year, month_year_order, activity_type
ORDER BY month_year_order ASC, total_events DESC
LIMIT 500;
```
