# NEP User Analytics — Questions to SQL Reference

> **Tables used:**
> - `nep_liftoffx_data_sample` — activity fact table (one row per user event)
> - `nep_master_user_table_sample_data` — master user registry
> - `nep_master_live_events_data` — live events and attendance
> - `nep_mentor_profiles_sample_data` — mentor profiles
>
> **Key convention:** "asking a question" = a row in `nep_liftoffx_data_sample` where `activity_type = 'message'` and `message_query IS NOT NULL`.

---

## Section A — AI Chat Usage (Questions 1–4)

---

### Q1. How many users asked at least one question in January 2026?

```sql
SELECT COUNT(DISTINCT userid) AS users_who_asked
FROM nep_liftoffx_data_sample
WHERE activity_type = 'message'
  AND message_query IS NOT NULL
  AND message_date >= '2026-01-01'
  AND message_date < '2026-02-01';
```

**What it does:** Counts unique users who sent at least one AI chat message in January 2026.

---

### Q2. How many total questions were asked in January 2026?

```sql
SELECT COUNT(*) AS total_questions
FROM nep_liftoffx_data_sample
WHERE activity_type = 'message'
  AND message_query IS NOT NULL
  AND message_date >= '2026-01-01'
  AND message_date < '2026-02-01';
```

**What it does:** Counts every AI chat message (question) sent in January 2026, including multiple questions from the same user.

> **Bonus — questions per user distribution:**
> ```sql
> SELECT
>   userid,
>   COUNT(*) AS questions_asked
> FROM nep_liftoffx_data_sample
> WHERE activity_type = 'message'
>   AND message_query IS NOT NULL
>   AND message_date >= '2026-01-01'
>   AND message_date < '2026-02-01'
> GROUP BY userid
> ORDER BY questions_asked DESC;
> ```

---

### Q3. What is the DAU / WAU / MAU and stickiness over time?

**DAU — Daily Active Users (users who asked ≥1 question per day):**
```sql
SELECT
  message_date                        AS activity_day,
  COUNT(DISTINCT userid)              AS dau
FROM nep_liftoffx_data_sample
WHERE activity_type = 'message'
  AND message_query IS NOT NULL
GROUP BY message_date
ORDER BY message_date;
```

**WAU — Weekly Active Users:**
```sql
SELECT
  week_range,
  month_year_order,
  COUNT(DISTINCT userid)              AS wau
FROM nep_liftoffx_data_sample
WHERE activity_type = 'message'
  AND message_query IS NOT NULL
GROUP BY week_range, month_year_order
ORDER BY month_year_order;
```

**MAU — Monthly Active Users:**
```sql
SELECT
  month_year,
  month_year_order,
  COUNT(DISTINCT userid)              AS mau
FROM nep_liftoffx_data_sample
WHERE activity_type = 'message'
  AND message_query IS NOT NULL
GROUP BY month_year, month_year_order
ORDER BY month_year_order;
```

**Stickiness — DAU/MAU ratio by month (join DAU and MAU CTEs):**
```sql
WITH daily AS (
  SELECT
    month_year,
    month_year_order,
    message_date,
    COUNT(DISTINCT userid) AS dau
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY month_year, month_year_order, message_date
),
monthly AS (
  SELECT
    month_year,
    month_year_order,
    COUNT(DISTINCT userid) AS mau
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY month_year, month_year_order
),
avg_dau AS (
  SELECT
    month_year,
    month_year_order,
    AVG(dau) AS avg_daily_active
  FROM daily
  GROUP BY month_year, month_year_order
)
SELECT
  m.month_year,
  m.mau,
  ROUND(a.avg_daily_active, 2)               AS avg_dau,
  ROUND(a.avg_daily_active / NULLIF(m.mau, 0) * 100, 2) AS stickiness_pct
FROM monthly m
JOIN avg_dau a USING (month_year, month_year_order)
ORDER BY m.month_year_order;
```

---

### Q4. What is the week-on-week or month-on-month change in questions asked?

**Week-on-week:**
```sql
WITH weekly_questions AS (
  SELECT
    week_range,
    month_year_order,
    MIN(year_monthnumber_weekstart_order) AS week_order,
    COUNT(*)                              AS questions
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY week_range, month_year_order
)
SELECT
  week_range,
  questions,
  LAG(questions) OVER (ORDER BY week_order)  AS prev_week_questions,
  questions - LAG(questions) OVER (ORDER BY week_order) AS wow_change,
  ROUND(
    (questions - LAG(questions) OVER (ORDER BY week_order))::NUMERIC
    / NULLIF(LAG(questions) OVER (ORDER BY week_order), 0) * 100, 2
  )                                          AS wow_pct_change
FROM weekly_questions
ORDER BY week_order;
```

**Month-on-month:**
```sql
WITH monthly_questions AS (
  SELECT
    month_year,
    month_year_order,
    COUNT(*) AS questions
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY month_year, month_year_order
)
SELECT
  month_year,
  questions,
  LAG(questions) OVER (ORDER BY month_year_order)  AS prev_month_questions,
  questions - LAG(questions) OVER (ORDER BY month_year_order) AS mom_change,
  ROUND(
    (questions - LAG(questions) OVER (ORDER BY month_year_order))::NUMERIC
    / NULLIF(LAG(questions) OVER (ORDER BY month_year_order), 0) * 100, 2
  )                                                AS mom_pct_change
FROM monthly_questions
ORDER BY month_year_order;
```

---

## Section B — Registration & Conversion (Questions 5–8)

---

### Q5. How many users registered in January 2026?

```sql
SELECT COUNT(*) AS registered_users
FROM nep_master_user_table_sample_data
WHERE created_datetime >= '2026-01-01'
  AND created_datetime < '2026-02-01';
```

**Or using signup_date from the activity table (covers same cohort):**
```sql
SELECT COUNT(DISTINCT userid) AS registered_users
FROM nep_liftoffx_data_sample
WHERE signup_date >= '2026-01-01'
  AND signup_date < '2026-02-01';
```

---

### Q6. Out of those registered users, how many asked at least one question?

```sql
WITH jan_registrations AS (
  SELECT user_id
  FROM nep_master_user_table_sample_data
  WHERE created_datetime >= '2026-01-01'
    AND created_datetime < '2026-02-01'
),
questioners AS (
  SELECT DISTINCT userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
)
SELECT COUNT(*) AS registered_users_who_asked
FROM jan_registrations r
JOIN questioners q ON r.user_id = q.userid;
```

---

### Q7. What is the registration to first question conversion rate?

```sql
WITH jan_registrations AS (
  SELECT user_id
  FROM nep_master_user_table_sample_data
  WHERE created_datetime >= '2026-01-01'
    AND created_datetime < '2026-02-01'
),
questioners AS (
  SELECT DISTINCT userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
),
counts AS (
  SELECT
    COUNT(r.user_id)                                          AS total_registered,
    COUNT(q.userid)                                          AS converted
  FROM jan_registrations r
  LEFT JOIN questioners q ON r.user_id = q.userid
)
SELECT
  total_registered,
  converted,
  ROUND(converted::NUMERIC / NULLIF(total_registered, 0) * 100, 2) AS conversion_rate_pct
FROM counts;
```

---

### Q8. How quickly do users reach their second interaction (question)?

This measures the gap in days between a user's **first** and **second** AI chat message.

```sql
WITH ranked_messages AS (
  SELECT
    userid,
    message_date,
    ROW_NUMBER() OVER (PARTITION BY userid ORDER BY message_date, response_timestamp) AS msg_rank
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
),
first_and_second AS (
  SELECT
    userid,
    MAX(CASE WHEN msg_rank = 1 THEN message_date END) AS first_question_date,
    MAX(CASE WHEN msg_rank = 2 THEN message_date END) AS second_question_date
  FROM ranked_messages
  WHERE msg_rank <= 2
  GROUP BY userid
  HAVING MAX(CASE WHEN msg_rank = 2 THEN message_date END) IS NOT NULL
)
SELECT
  userid,
  first_question_date,
  second_question_date,
  (second_question_date::DATE - first_question_date::DATE) AS days_to_second_question
FROM first_and_second
ORDER BY days_to_second_question;
```

**Summary stats (avg/median days to second question):**
```sql
WITH ranked_messages AS (
  SELECT
    userid,
    message_date,
    ROW_NUMBER() OVER (PARTITION BY userid ORDER BY message_date, response_timestamp) AS msg_rank
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
),
gaps AS (
  SELECT
    userid,
    MAX(CASE WHEN msg_rank = 1 THEN message_date END) AS first_q,
    MAX(CASE WHEN msg_rank = 2 THEN message_date END) AS second_q
  FROM ranked_messages
  WHERE msg_rank <= 2
  GROUP BY userid
  HAVING MAX(CASE WHEN msg_rank = 2 THEN message_date END) IS NOT NULL
)
SELECT
  ROUND(AVG(second_q::DATE - first_q::DATE), 1)        AS avg_days_to_second,
  PERCENTILE_CONT(0.5) WITHIN GROUP (
    ORDER BY second_q::DATE - first_q::DATE
  )                                                     AS median_days_to_second,
  MIN(second_q::DATE - first_q::DATE)                  AS min_days,
  MAX(second_q::DATE - first_q::DATE)                  AS max_days
FROM gaps;
```

---

## Section C — UTM & Acquisition Analysis (Questions 9–12)

---

### Q9. Which UTM campaigns are driving the most engaged users?

"Engaged" = users who asked at least one AI question.

```sql
SELECT
  u.traffic_source_source   AS utm_source,
  u.traffic_source_medium   AS utm_medium,
  u.traffic_source_campaign AS utm_campaign,
  COUNT(DISTINCT u.user_id) AS total_registered,
  COUNT(DISTINCT a.userid)  AS users_who_asked,
  SUM(CASE WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
           THEN 1 ELSE 0 END) AS total_questions_asked
FROM nep_master_user_table_sample_data u
LEFT JOIN nep_liftoffx_data_sample a
  ON u.user_id = a.userid
  AND a.activity_type = 'message'
  AND a.message_query IS NOT NULL
WHERE u.traffic_source_campaign IS NOT NULL
GROUP BY u.traffic_source_source, u.traffic_source_medium, u.traffic_source_campaign
ORDER BY total_questions_asked DESC;
```

---

### Q10. Which UTM campaigns have the highest registration-to-question conversion rate?

```sql
WITH campaign_registrations AS (
  SELECT
    traffic_source_source   AS utm_source,
    traffic_source_medium   AS utm_medium,
    traffic_source_campaign AS utm_campaign,
    user_id
  FROM nep_master_user_table_sample_data
  WHERE traffic_source_campaign IS NOT NULL
),
campaign_converters AS (
  SELECT DISTINCT
    u.traffic_source_source   AS utm_source,
    u.traffic_source_medium   AS utm_medium,
    u.traffic_source_campaign AS utm_campaign,
    u.user_id
  FROM nep_master_user_table_sample_data u
  JOIN nep_liftoffx_data_sample a
    ON u.user_id = a.userid
   AND a.activity_type = 'message'
   AND a.message_query IS NOT NULL
  WHERE u.traffic_source_campaign IS NOT NULL
)
SELECT
  r.utm_source,
  r.utm_medium,
  r.utm_campaign,
  COUNT(DISTINCT r.user_id)                              AS registrations,
  COUNT(DISTINCT c.user_id)                              AS converted,
  ROUND(
    COUNT(DISTINCT c.user_id)::NUMERIC
    / NULLIF(COUNT(DISTINCT r.user_id), 0) * 100, 2
  )                                                     AS conversion_rate_pct
FROM campaign_registrations r
LEFT JOIN campaign_converters c USING (utm_source, utm_medium, utm_campaign, user_id)
GROUP BY r.utm_source, r.utm_medium, r.utm_campaign
ORDER BY conversion_rate_pct DESC;
```

---

### Q11. Which partners are sending the highest-quality users?

"Partner" is identified by `traffic_source_source`. "Quality" = engaged users (asked questions).

```sql
SELECT
  u.traffic_source_source                               AS partner,
  COUNT(DISTINCT u.user_id)                             AS users_from_partner,
  COUNT(DISTINCT CASE
    WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
    THEN a.userid END)                                  AS engaged_users,
  ROUND(
    COUNT(DISTINCT CASE
      WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
      THEN a.userid END)::NUMERIC
    / NULLIF(COUNT(DISTINCT u.user_id), 0) * 100, 2
  )                                                     AS engagement_rate_pct,
  COALESCE(SUM(CASE
    WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
    THEN 1 END), 0)                                     AS total_questions
FROM nep_master_user_table_sample_data u
LEFT JOIN nep_liftoffx_data_sample a ON u.user_id = a.userid
WHERE u.traffic_source_source IS NOT NULL
GROUP BY u.traffic_source_source
ORDER BY engagement_rate_pct DESC;
```

---

### Q12. How does engagement differ between paid, organic, and partner traffic?

Classify traffic type from UTM medium, then compare engagement.

```sql
SELECT
  CASE
    WHEN LOWER(u.traffic_source_medium) IN ('cpc', 'paid', 'ppc', 'social-paid') THEN 'Paid'
    WHEN LOWER(u.traffic_source_medium) IN ('organic', 'seo', 'direct', '(none)')
         OR u.traffic_source_medium IS NULL                                        THEN 'Organic'
    ELSE 'Partner / Other'
  END                                                   AS traffic_type,
  COUNT(DISTINCT u.user_id)                             AS total_users,
  COUNT(DISTINCT CASE
    WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
    THEN a.userid END)                                  AS users_who_asked,
  COALESCE(SUM(CASE
    WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
    THEN 1 END), 0)                                     AS total_questions,
  ROUND(
    COUNT(DISTINCT CASE
      WHEN a.activity_type = 'message' AND a.message_query IS NOT NULL
      THEN a.userid END)::NUMERIC
    / NULLIF(COUNT(DISTINCT u.user_id), 0) * 100, 2
  )                                                     AS engagement_rate_pct
FROM nep_master_user_table_sample_data u
LEFT JOIN nep_liftoffx_data_sample a ON u.user_id = a.userid
GROUP BY traffic_type
ORDER BY engagement_rate_pct DESC;
```

---

## Section D — Retention (Questions 13–15)

---

### Q13. What is user retention week-over-week?

This compares the set of users active in week N vs week N-1.

```sql
WITH weekly_users AS (
  SELECT
    year_monthnumber_weekstart_order  AS week_order,
    week_range,
    userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY year_monthnumber_weekstart_order, week_range, userid
),
week_pairs AS (
  SELECT
    curr.week_range                          AS current_week,
    curr.week_order                          AS current_week_order,
    COUNT(DISTINCT curr.userid)              AS active_users,
    COUNT(DISTINCT prev.userid)              AS retained_from_prev_week
  FROM weekly_users curr
  LEFT JOIN weekly_users prev
    ON prev.userid = curr.userid
   AND prev.week_order = curr.week_order - 1
  GROUP BY curr.week_range, curr.week_order
)
SELECT
  current_week,
  active_users,
  retained_from_prev_week,
  ROUND(
    retained_from_prev_week::NUMERIC / NULLIF(active_users, 0) * 100, 2
  ) AS retention_rate_pct
FROM week_pairs
ORDER BY current_week_order;
```

---

### Q14. How many repeat users do we have per month?

"Repeat" = users active in at least 2 different calendar months.

```sql
WITH user_months AS (
  SELECT
    userid,
    COUNT(DISTINCT month_year_order) AS months_active
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
)
SELECT
  months_active,
  COUNT(*) AS users
FROM user_months
GROUP BY months_active
ORDER BY months_active;
```

**Or simply count repeat (multi-month) users:**
```sql
WITH user_months AS (
  SELECT userid, COUNT(DISTINCT month_year_order) AS months_active
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
)
SELECT
  SUM(CASE WHEN months_active >= 2 THEN 1 ELSE 0 END) AS repeat_users,
  COUNT(*)                                             AS total_users,
  ROUND(
    SUM(CASE WHEN months_active >= 2 THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2
  )                                                    AS repeat_rate_pct
FROM user_months;
```

---

### Q15. How does retention vary by acquisition channel or partner?

```sql
WITH user_channel AS (
  SELECT
    u.user_id,
    COALESCE(u.traffic_source_source, 'Unknown') AS channel
  FROM nep_master_user_table_sample_data u
),
user_months AS (
  SELECT
    a.userid,
    COUNT(DISTINCT a.month_year_order) AS months_active
  FROM nep_liftoffx_data_sample a
  WHERE a.activity_type = 'message'
    AND a.message_query IS NOT NULL
  GROUP BY a.userid
)
SELECT
  uc.channel,
  COUNT(DISTINCT uc.user_id)                          AS total_users,
  COUNT(DISTINCT CASE WHEN um.months_active >= 2
        THEN uc.user_id END)                          AS retained_users,
  ROUND(
    COUNT(DISTINCT CASE WHEN um.months_active >= 2
          THEN uc.user_id END)::NUMERIC
    / NULLIF(COUNT(DISTINCT uc.user_id), 0) * 100, 2
  )                                                   AS retention_rate_pct
FROM user_channel uc
LEFT JOIN user_months um ON uc.user_id = um.userid
GROUP BY uc.channel
ORDER BY retention_rate_pct DESC;
```

---

## Section E — Power Users & Feature Depth (Questions 16–20)

---

### Q16. How many users are power users (more than 5 or 10 questions)?

```sql
WITH user_question_counts AS (
  SELECT
    userid,
    COUNT(*) AS questions_asked
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
)
SELECT
  COUNT(*)                                                   AS total_ai_users,
  SUM(CASE WHEN questions_asked > 5  THEN 1 ELSE 0 END)    AS power_users_5plus,
  SUM(CASE WHEN questions_asked > 10 THEN 1 ELSE 0 END)    AS power_users_10plus,
  ROUND(SUM(CASE WHEN questions_asked > 5 THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2)                         AS pct_power_5plus,
  ROUND(SUM(CASE WHEN questions_asked > 10 THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2)                         AS pct_power_10plus
FROM user_question_counts;
```

**Breakdown by tier:**
```sql
WITH user_question_counts AS (
  SELECT userid, COUNT(*) AS questions_asked
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
)
SELECT
  CASE
    WHEN questions_asked = 1        THEN '1 question (one-time)'
    WHEN questions_asked BETWEEN 2 AND 5  THEN '2–5 questions (casual)'
    WHEN questions_asked BETWEEN 6 AND 10 THEN '6–10 questions (engaged)'
    ELSE '10+ questions (power user)'
  END AS user_segment,
  COUNT(*) AS users
FROM user_question_counts
GROUP BY user_segment
ORDER BY MIN(questions_asked);
```

---

### Q17. What actions do power users take that casual users do not?

Compares activity event distributions between power users (>5 questions) and casual users (1–2 questions).

```sql
WITH question_counts AS (
  SELECT userid, COUNT(*) AS questions_asked
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
),
user_segments AS (
  SELECT
    userid,
    CASE
      WHEN questions_asked > 5 THEN 'Power User'
      ELSE 'Casual User'
    END AS segment
  FROM question_counts
)
SELECT
  s.segment,
  a.activity_type,
  a.ga_event_name,
  COUNT(*)                           AS event_count,
  COUNT(DISTINCT a.userid)           AS users
FROM nep_liftoffx_data_sample a
JOIN user_segments s ON a.userid = s.userid
GROUP BY s.segment, a.activity_type, a.ga_event_name
ORDER BY s.segment, event_count DESC;
```

---

### Q18. Do users who use multiple features have higher retention?

"Multiple features" = using more than one distinct `activity_type` (e.g. both `message` and `session`).

```sql
WITH user_features AS (
  SELECT
    userid,
    COUNT(DISTINCT activity_type)    AS feature_count
  FROM nep_liftoffx_data_sample
  GROUP BY userid
),
user_retention AS (
  SELECT
    userid,
    COUNT(DISTINCT month_year_order) AS months_active
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
  GROUP BY userid
)
SELECT
  CASE
    WHEN uf.feature_count = 1 THEN '1 feature only'
    WHEN uf.feature_count = 2 THEN '2 features'
    ELSE '3+ features'
  END                                AS feature_breadth,
  COUNT(DISTINCT uf.userid)          AS users,
  ROUND(AVG(ur.months_active), 2)    AS avg_months_active,
  SUM(CASE WHEN ur.months_active >= 2 THEN 1 ELSE 0 END)  AS retained_users,
  ROUND(
    SUM(CASE WHEN ur.months_active >= 2 THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(DISTINCT uf.userid), 0) * 100, 2
  )                                  AS retention_rate_pct
FROM user_features uf
LEFT JOIN user_retention ur ON uf.userid = ur.userid
GROUP BY feature_breadth
ORDER BY feature_breadth;
```

---

### Q19. Do users who ask questions also book mentor sessions?

```sql
WITH ai_users AS (
  SELECT DISTINCT userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
),
mentor_users AS (
  SELECT DISTINCT userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'mentor'
)
SELECT
  COUNT(DISTINCT a.userid)               AS users_who_asked_questions,
  COUNT(DISTINCT m.userid)               AS users_who_booked_mentors,
  COUNT(DISTINCT CASE WHEN m.userid IS NOT NULL
    THEN a.userid END)                   AS did_both,
  ROUND(
    COUNT(DISTINCT CASE WHEN m.userid IS NOT NULL
      THEN a.userid END)::NUMERIC
    / NULLIF(COUNT(DISTINCT a.userid), 0) * 100, 2
  )                                      AS pct_ai_users_also_mentor
FROM ai_users a
LEFT JOIN mentor_users m ON a.userid = m.userid;
```

**Cross-feature overlap matrix (AI chat, mentor, live events):**
```sql
SELECT
  CASE WHEN ai.userid IS NOT NULL THEN 'Yes' ELSE 'No' END   AS used_ai_chat,
  CASE WHEN me.userid IS NOT NULL THEN 'Yes' ELSE 'No' END   AS booked_mentor,
  CASE WHEN le.userid IS NOT NULL THEN 'Yes' ELSE 'No' END   AS attended_event,
  COUNT(DISTINCT u.user_id)                                   AS users
FROM nep_master_user_table_sample_data u
LEFT JOIN (
  SELECT DISTINCT userid FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message' AND message_query IS NOT NULL
) ai ON u.user_id = ai.userid
LEFT JOIN (
  SELECT DISTINCT userid FROM nep_liftoffx_data_sample
  WHERE activity_type = 'mentor'
) me ON u.user_id = me.userid
LEFT JOIN (
  SELECT DISTINCT participant_user_id AS userid
  FROM nep_master_live_events_data
  WHERE participant_status = 'ATTENDED'
) le ON u.user_id = le.userid
GROUP BY used_ai_chat, booked_mentor, attended_event
ORDER BY users DESC;
```

---

### Q20. Does guided question usage improve retention or repeat behaviour?

"Guided question usage" = users who asked questions AND received a non-null AI response (`response_content IS NOT NULL` and `response_flow_state = 'completed'`). This compares their return rate vs users who only browsed.

```sql
WITH guided_users AS (
  -- Users who completed at least one full AI Q&A interaction
  SELECT DISTINCT userid
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'
    AND message_query IS NOT NULL
    AND response_flow_state = 'completed'
    AND response_content IS NOT NULL
),
all_registered AS (
  SELECT user_id AS userid FROM nep_master_user_table_sample_data
),
user_months AS (
  SELECT userid, COUNT(DISTINCT month_year_order) AS months_active
  FROM nep_liftoffx_data_sample
  GROUP BY userid
)
SELECT
  CASE WHEN g.userid IS NOT NULL THEN 'Used Guided Q&A' ELSE 'Never Used Q&A' END
                                                             AS user_type,
  COUNT(DISTINCT r.userid)                                   AS total_users,
  ROUND(AVG(um.months_active), 2)                            AS avg_months_active,
  SUM(CASE WHEN um.months_active >= 2 THEN 1 ELSE 0 END)    AS repeat_users,
  ROUND(
    SUM(CASE WHEN um.months_active >= 2 THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(DISTINCT r.userid), 0) * 100, 2
  )                                                          AS repeat_rate_pct
FROM all_registered r
LEFT JOIN guided_users g ON r.userid = g.userid
LEFT JOIN user_months um ON r.userid = um.userid
GROUP BY user_type;
```

---

## Quick Reference Index

| # | Question | Key Table(s) | Filter / Key Column |
|---|----------|-------------|---------------------|
| 1 | Users who asked ≥1 question (Jan 2026) | `nep_liftoffx_data_sample` | `activity_type='message'`, `message_date` |
| 2 | Total questions asked (Jan 2026) | `nep_liftoffx_data_sample` | `activity_type='message'`, `message_date` |
| 3 | DAU/WAU/MAU & stickiness | `nep_liftoffx_data_sample` | `message_date`, `week_range`, `month_year` |
| 4 | WoW/MoM questions change | `nep_liftoffx_data_sample` | `LAG()` over `week_order` / `month_year_order` |
| 5 | Users registered (Jan 2026) | `nep_master_user_table_sample_data` | `created_datetime` |
| 6 | Registered users who asked ≥1 question | Both tables | JOIN on `user_id` = `userid` |
| 7 | Registration-to-question conversion rate | Both tables | LEFT JOIN + COUNT |
| 8 | Days to second question | `nep_liftoffx_data_sample` | `ROW_NUMBER()` + date diff |
| 9 | Campaigns with most engaged users | Both tables | `traffic_source_campaign` |
| 10 | Campaigns with highest conversion rate | Both tables | `traffic_source_campaign` + JOIN |
| 11 | Partners sending highest-quality users | Both tables | `traffic_source_source` |
| 12 | Paid vs organic vs partner engagement | Both tables | `traffic_source_medium` classification |
| 13 | Week-over-week retention | `nep_liftoffx_data_sample` | `LAG()` over `week_order` |
| 14 | Repeat users per month | `nep_liftoffx_data_sample` | `COUNT(DISTINCT month_year_order)` |
| 15 | Retention by acquisition channel | Both tables | JOIN on `user_id`, group by `channel` |
| 16 | Power users (5+, 10+ questions) | `nep_liftoffx_data_sample` | `COUNT(*)` per user |
| 17 | Actions power vs casual users take | `nep_liftoffx_data_sample` | segment by question count |
| 18 | Multi-feature users vs single-feature retention | `nep_liftoffx_data_sample` | `COUNT(DISTINCT activity_type)` |
| 19 | Users who ask questions AND book mentors | `nep_liftoffx_data_sample` | `activity_type` overlap |
| 20 | Guided Q&A usage vs retention/repeat behaviour | All tables | `response_flow_state='completed'` |
| 21 | Active mentors by industry | `nep_mentor_profiles_sample_data` | `user_status='ACTIVE'`, `industry_name` |
| 22 | Mentors by startup stage expertise | `nep_mentor_profiles_sample_data` | `stage_name` |
| 23 | Mentor sessions booked vs profiles available | Both mentor tables | JOIN on `user_id` |
| 24 | Top events by attendance rate | `nep_master_live_events_data` | `participant_status='ATTENDED'` |
| 25 | Events by program and session type | `nep_master_live_events_data` | `program_key`, `sessiontype` |
| 26 | No-show rate by gap area / topic | `nep_master_live_events_data` | `gapkey`, `participant_status` |
| 27 | User activity breakdown by type | `nep_liftoffx_data_sample` | `activity_type` |
| 28 | Users by traffic source who attended events | Both tables | JOIN on `user_id`, `participant_user_id` |
| 29 | Internal vs External user engagement | Both tables | `user_type` |
| 30 | Profile completion status distribution | `nep_master_user_table_sample_data` | `login_status`, `profile_status` |

---

## Section F — Mentor Profiles, Live Events & Activity Breakdown (Questions 21–30)

> These examples are grounded in the functional business context of each table:
> - **nep_master_dataset_table** → registration, identities, status, acquisition
> - **Nep_liftoffx_data** → user actions: AI chat, mentor sessions, events, resource views, visitor journeys
> - **Nep_mentor_profiles** → mentor identities, expertise (industry + stage), account status
> - **Nep_master_live_events** → virtual sessions, attendance, speaker details, Zoom logistics

---

### Q21. How many active mentors are there per industry?

```sql
SELECT
  industry_name,
  COUNT(DISTINCT user_id) AS active_mentors
FROM nep_mentor_profiles_sample_data
WHERE user_status = 'ACTIVE'
  AND deleted = false
GROUP BY industry_name
ORDER BY active_mentors DESC
LIMIT 500;
```

**What it does:** Shows which industries are best represented in the active mentor pool — useful for spotting supply gaps.

---

### Q22. How many mentors cover each startup stage?

```sql
SELECT
  stage_name,
  COUNT(DISTINCT user_id) AS mentors
FROM nep_mentor_profiles_sample_data
WHERE user_status = 'ACTIVE'
  AND deleted = false
GROUP BY stage_name
ORDER BY mentors DESC
LIMIT 500;
```

**What it does:** Identifies which startup stages (Pre Idea, Idea, Early, Growth, Demo) have the most mentor coverage — helps spot demand gaps.

---

### Q23. Which industries have the most mentor sessions booked?

```sql
SELECT
  m.industry_name,
  COUNT(DISTINCT a.userid)  AS users_who_booked,
  COUNT(*)                  AS total_sessions
FROM nep_liftoffx_data_sample a
JOIN nep_mentor_profiles_sample_data m
  ON a.mentor_id::VARCHAR = m.user_id
WHERE a.activity_type = 'mentor'
GROUP BY m.industry_name
ORDER BY total_sessions DESC
LIMIT 500;
```

**What it does:** Connects mentor session activity with mentor industry expertise to reveal which sectors see the most bookings.

---

### Q24. What is the attendance rate for each completed event?

```sql
SELECT
  event_id,
  MAX(event_title)    AS event_title,
  MAX(start_date)     AS start_date,
  MAX(sessiontype)    AS session_type,
  MAX(gapkey)         AS gap_area,
  COUNT(*)            AS total_registrations,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END)  AS attended,
  SUM(CASE WHEN participant_status = 'NOSHOW'   THEN 1 ELSE 0 END)  AS no_shows,
  ROUND(
    SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2
  ) AS attendance_rate_pct
FROM nep_master_live_events_data
WHERE event_status = 'COMPLETED'
GROUP BY event_id
ORDER BY attendance_rate_pct DESC
LIMIT 500;
```

**What it does:** Ranks every completed event by its attendance rate, making it easy to spot which sessions resonated most.

---

### Q25. How many events and attendees does each program and session type have?

```sql
SELECT
  program_key,
  sessiontype,
  COUNT(DISTINCT event_id)                                            AS total_events,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END)  AS total_attended,
  COUNT(*)                                                            AS total_registrations,
  ROUND(
    SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2
  ) AS attendance_rate_pct
FROM nep_master_live_events_data
WHERE event_status = 'COMPLETED'
GROUP BY program_key, sessiontype
ORDER BY program_key, total_attended DESC
LIMIT 500;
```

**What it does:** Compares programs (`liftoff-propel`, `liftoff-spark`, `ignite`) and session formats (`roundTable`, `workshop`, `masterclass`) side-by-side.

---

### Q26. Which gap areas have the highest no-show rates?

```sql
SELECT
  gapkey                                                              AS gap_area,
  COUNT(DISTINCT event_id)                                            AS events,
  COUNT(*)                                                            AS total_registrations,
  SUM(CASE WHEN participant_status = 'NOSHOW'   THEN 1 ELSE 0 END)  AS no_shows,
  SUM(CASE WHEN participant_status = 'ATTENDED' THEN 1 ELSE 0 END)  AS attended,
  ROUND(
    SUM(CASE WHEN participant_status = 'NOSHOW' THEN 1 ELSE 0 END)::NUMERIC
    / NULLIF(COUNT(*), 0) * 100, 2
  ) AS no_show_rate_pct
FROM nep_master_live_events_data
WHERE event_status = 'COMPLETED'
  AND gapkey IS NOT NULL
GROUP BY gapkey
ORDER BY no_show_rate_pct DESC
LIMIT 500;
```

**What it does:** Surfaces gap areas (e.g. GrowthHacking, Finance, Marketing) where users register but don't show up — signals for scheduling or content improvements.

---

### Q27. What is the breakdown of user activity types on the platform?

```sql
SELECT
  activity_type,
  COUNT(*)                    AS total_events,
  COUNT(DISTINCT userid)      AS unique_users,
  ROUND(
    COUNT(*)::NUMERIC / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 2
  ) AS share_pct
FROM nep_liftoffx_data_sample
GROUP BY activity_type
ORDER BY total_events DESC
LIMIT 500;
```

**What it does:** Shows how users spend their time — AI chat, mentor sessions, live events, resource views, or just browsing — and the relative share of each.

---

### Q28. Which traffic sources produce users who attend the most live events?

```sql
SELECT
  u.traffic_source_source                                             AS traffic_source,
  COUNT(DISTINCT u.user_id)                                           AS total_users,
  COUNT(DISTINCT e.participant_user_id)                               AS users_attended_events,
  COUNT(*)                                                            AS total_event_attendances,
  ROUND(
    COUNT(DISTINCT e.participant_user_id)::NUMERIC
    / NULLIF(COUNT(DISTINCT u.user_id), 0) * 100, 2
  ) AS event_attendance_rate_pct
FROM nep_master_user_table_sample_data u
LEFT JOIN nep_master_live_events_data e
  ON u.user_id = e.participant_user_id
 AND e.participant_status = 'ATTENDED'
WHERE u.traffic_source_source IS NOT NULL
GROUP BY u.traffic_source_source
ORDER BY event_attendance_rate_pct DESC
LIMIT 500;
```

**What it does:** Connects acquisition source to live event participation — shows which channels bring users who actually show up to sessions.

---

### Q29. How does engagement compare between Internal and External users?

```sql
SELECT
  u.user_type,
  COUNT(DISTINCT u.user_id)                                           AS total_users,
  COUNT(DISTINCT CASE WHEN a.activity_type = 'message'
        AND a.message_query IS NOT NULL THEN a.userid END)            AS ai_chat_users,
  COUNT(DISTINCT CASE WHEN a.activity_type = 'mentor'
        THEN a.userid END)                                            AS mentor_session_users,
  COUNT(DISTINCT CASE WHEN a.activity_type = 'session'
        THEN a.userid END)                                            AS live_event_users,
  COUNT(DISTINCT CASE WHEN a.activity_type = 'resource'
        THEN a.userid END)                                            AS resource_view_users,
  ROUND(
    COUNT(DISTINCT CASE WHEN a.activity_type = 'message'
          AND a.message_query IS NOT NULL THEN a.userid END)::NUMERIC
    / NULLIF(COUNT(DISTINCT u.user_id), 0) * 100, 2
  ) AS ai_chat_rate_pct
FROM nep_master_user_table_sample_data u
LEFT JOIN nep_liftoffx_data_sample a ON u.user_id = a.userid
GROUP BY u.user_type
ORDER BY u.user_type
LIMIT 500;
```

**What it does:** Side-by-side comparison of how Internal (Wadhwani staff) vs External (entrepreneurs) users engage across every feature on the platform.

---

### Q30. What is the profile completion status distribution of registered users?

```sql
SELECT
  login_status,
  profile_status,
  user_type,
  COUNT(*)  AS users,
  ROUND(COUNT(*)::NUMERIC / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 2) AS share_pct
FROM nep_master_user_table_sample_data
GROUP BY login_status, profile_status, user_type
ORDER BY users DESC
LIMIT 500;
```

**What it does:** Shows how many users have completed their profile vs remain in intermediate states — useful for onboarding funnel health checks.

---
