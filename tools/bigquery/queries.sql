-- Qtown v2 commit analytics — BigQuery queries
--
-- Table: `PROJECT.qtown_analytics.commits` (replace PROJECT with your GCP project id)
--
-- Partitioned by DATE(committed_at) for cheaper scans as the dataset grows.
-- Each query below answers a concrete question about the AI-driven development
-- of Qtown v2. Numbers here become raw material for the Qtown case study.

-- 1. Ralph vs human split — headline stat for the case study
SELECT
  is_ralph,
  COUNT(*)                               AS commit_count,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_total,
  SUM(lines_added)                       AS lines_added_total,
  SUM(lines_deleted)                     AS lines_deleted_total,
  SUM(files_changed)                     AS files_changed_total
FROM `PROJECT.qtown_analytics.commits`
GROUP BY is_ralph;

-- 2. Weekly commit velocity — was this a slow burn or burst shipping?
SELECT
  DATE_TRUNC(DATE(committed_at), WEEK) AS week_start,
  SUM(CASE WHEN is_ralph THEN 1 ELSE 0 END) AS ralph_commits,
  SUM(CASE WHEN NOT is_ralph THEN 1 ELSE 0 END) AS human_commits,
  COUNT(*) AS total_commits
FROM `PROJECT.qtown_analytics.commits`
GROUP BY week_start
ORDER BY week_start;

-- 3. Time-of-day patterns — when does Ralph ship vs when does a human commit?
SELECT
  EXTRACT(HOUR FROM committed_at AT TIME ZONE 'America/New_York') AS hour_et,
  SUM(CASE WHEN is_ralph THEN 1 ELSE 0 END) AS ralph_commits,
  SUM(CASE WHEN NOT is_ralph THEN 1 ELSE 0 END) AS human_commits
FROM `PROJECT.qtown_analytics.commits`
GROUP BY hour_et
ORDER BY hour_et;

-- 4. Average commit size — are AI commits smaller/larger than human commits?
SELECT
  is_ralph,
  COUNT(*) AS commit_count,
  ROUND(AVG(files_changed), 2) AS avg_files_per_commit,
  ROUND(AVG(lines_added),   2) AS avg_lines_added,
  ROUND(AVG(lines_deleted), 2) AS avg_lines_deleted,
  APPROX_QUANTILES(lines_added, 100)[OFFSET(50)] AS p50_lines_added,
  APPROX_QUANTILES(lines_added, 100)[OFFSET(95)] AS p95_lines_added
FROM `PROJECT.qtown_analytics.commits`
GROUP BY is_ralph;

-- 5. Story-level commit footprint — how many commits does Ralph spend per story?
-- (Ralph commit subjects start with "[Ralph] Story N:" — extract the story id.)
SELECT
  REGEXP_EXTRACT(subject, r'Story\s+(\d+)') AS story_id,
  COUNT(*)                AS commits_for_story,
  SUM(lines_added)        AS lines_added,
  MIN(committed_at)       AS started_at,
  MAX(committed_at)       AS finished_at,
  TIMESTAMP_DIFF(MAX(committed_at), MIN(committed_at), HOUR) AS elapsed_hours
FROM `PROJECT.qtown_analytics.commits`
WHERE REGEXP_CONTAINS(subject, r'Story\s+\d+')
GROUP BY story_id
ORDER BY CAST(story_id AS INT64);

-- 6. The "is Ralph slowing down or speeding up" question
SELECT
  DATE_TRUNC(DATE(committed_at), MONTH) AS month_start,
  COUNTIF(is_ralph) AS ralph_commits,
  ROUND(SUM(IF(is_ralph, lines_added, 0)) / NULLIF(COUNTIF(is_ralph), 0), 2) AS ralph_avg_lines_per_commit,
  ROUND(SUM(IF(is_ralph, files_changed, 0)) / NULLIF(COUNTIF(is_ralph), 0), 2) AS ralph_avg_files_per_commit
FROM `PROJECT.qtown_analytics.commits`
GROUP BY month_start
ORDER BY month_start;
