-- Run this in the Supabase SQL Editor to update the execute_sql function.
-- It now handles both plain SELECT queries and CTEs (WITH ... SELECT).
-- Go to: https://supabase.com/dashboard/project/mybdvsxiynpdbuzmtquu/sql/new

CREATE OR REPLACE FUNCTION execute_sql(query text)
RETURNS json LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  result json;
  trimmed text;
BEGIN
  trimmed := trim(trailing ';' from trim(query));

  -- Use json_agg(row_to_json(t)) which correctly handles both:
  -- 1. Plain SELECT: SELECT ... FROM table WHERE ...
  -- 2. CTEs:        WITH cte AS (...) SELECT ... FROM cte ...
  EXECUTE format(
    'SELECT json_agg(row_to_json(t)) FROM (%s) AS t',
    trimmed
  ) INTO result;

  RETURN COALESCE(result, '[]'::json);

EXCEPTION
  WHEN others THEN
    RAISE EXCEPTION 'execute_sql error: % | Query: %', SQLERRM, left(trimmed, 300);
END;
$$;
