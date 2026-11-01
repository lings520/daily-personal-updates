-- Render placeholders with prepare_market_data.py plan; do not hand-edit dates.
-- Massive renames timestamp t to t_2 because SQLite treats T and t alike.
-- Counts preserve duplicate detection; LEFT JOIN preserves missing instruments.
WITH wanted(ticker) AS (VALUES {{wanted}}),
current_rows AS (
  SELECT T AS ticker, MAX(c) AS close, MAX(t_2) AS timestamp, COUNT(*) AS count
  FROM {{current_table}} GROUP BY T
),
prior_rows AS (
  SELECT T AS ticker, MAX(c) AS close, MAX(t_2) AS timestamp, COUNT(*) AS count
  FROM {{prior_table}} GROUP BY T
)
SELECT w.ticker, c.close AS current_close, p.close AS prior_close,
  c.timestamp AS current_timestamp, p.timestamp AS prior_timestamp,
  COALESCE(c.count, 0) AS current_count, COALESCE(p.count, 0) AS prior_count,
  100.0 * (c.close / NULLIF(p.close, 0) - 1.0) AS change_pct
FROM wanted w
LEFT JOIN current_rows c ON c.ticker = w.ticker
LEFT JOIN prior_rows p ON p.ticker = w.ticker
ORDER BY w.ticker;
