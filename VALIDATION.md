# Resumable workflow refactor

Verified on 2026-11-01: **62 pipeline/context/workflow tests and 3 schedule tests passed**. Skill frontmatter validation passed. The new tests exercise missing-input pauses, failed-stage recovery, input/plan tampering, cached reruns, render-only retries, palette changes, revised-data research checks, current-artifact review/delivery receipts, and shared threshold configuration. Existing arithmetic and source/date checks remain covered.

An independent fixture trial completed the documented workflow and inspected both image sizes. A palette-only revision reused collection, normalization, research and composition; metrics and snapshot stayed byte-identical. Its revised render took 3.580 seconds, excluding fresh source retrieval/research. A separate comparison confirmed the default refactored renderer produced a pixel-identical image for the approved pre-refactor payload (1200 × 3038).

A fresh Massive daily-summary request for SPY on 2026-10-30 succeeded; this was a connector connectivity/schema smoke check, not a full live workflow timing benchmark.

The scheduled task delegates to one installed skill and one workflow entry point. The runtime still performs authenticated retrieval, research, inspection and actual publication. Recording a receipt does not independently establish external delivery. Tests do not claim a measured live end-to-end speed improvement; any local fixture timings exclude real network research.

---

# Editorial typography and risk-context update

Verified on 2026-11-01: **49 pipeline/context tests and 3 schedule tests passed**; installed skill frontmatter validation passed. Tests cover the full CLI-to-PNG workflow, VIX boundaries, 252-prior-return percentile calculation, tie handling, insufficient history, source/contract/cutoff mismatches, future or duplicate dates, sentinel missing values, sentiment timestamps and illustrative-data safeguards. The approved renderer now uses Bookman headings, Nimbus Sans body and a lavender sentiment gauge.

An independent offline trial exercised sourced fictional sentiment, historical percentiles, incomplete history and rejected mismatches. It found a wrapped-label row-spacing issue; the renderer now measures row heights. A fresh Massive daily-summary request for SPY on 2026-10-30 succeeded as a connector smoke check.

This revision uses fictional fixtures to test new sentiment/history features; it does not claim a fresh live CNN score or a verified real-world historical percentile. Source truth, provider access and history completeness still require per-run verification. Cloud execution and notification delivery are not established by these local tests.

---

# Market pipeline validation

Verified on 2026-11-01 with Python 3.12, Pillow 12.3.0, and python-dateutil 2.9.0.post0.

## Automated checks

- **39 pipeline tests passed**, including actual SQL execution in SQLite and the complete command-line flow through full-size and preview PNGs.
- **3 schedule tests passed**, interpreting the exported iCalendar with python-dateutil: Tuesday–Saturday at 08:00 Asia/Hong_Kong, weekend skipping, and stable Hong Kong timing across US daylight-saving changes.
- The installed skill passed the Skill Creator validator.
- Whitespace/diff checks passed.

Run the commands in [README.md](README.md) to reproduce the offline checks. Fixtures are fictional; they do not need credentials or network access.

## Connector smoke test

Using fresh Massive connector requests for 2026-10-30 and 2026-10-29:

1. Two grouped equity requests and the generated SQL returned all 14 core ETFs and three optional proxies.
2. Python verified each session timestamp, duplicate count, price and SQL return, then calculated the display metrics.
3. The date-bounded Treasury request stopped at 2026-10-29. The pipeline correctly emitted three follow-ups rather than presenting those observations as 2026-10-30 yields.
4. Both comparison dates were independently verified from the [official Treasury October table](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202610&type=daily_treasury_yield_curve), using one source and series for both observations. Normalization then completed without warnings.
5. Composition and rendering succeeded. The 1200 × 2388 image and 600px preview were inspected for values, dates, signs, units, source keys, clipping and readability.

This was a numeric pipeline smoke test, not a complete researched market briefing. Its news, upcoming calendar and risk benchmarks were explicitly unverified/unavailable. Full structured news, sentiment, event-table, proxy and missing-data behavior was exercised with offline fixtures.

## Independent fixture trial

A separate agent used the installed skill instructions and saved fixtures to complete `plan → normalize → compose → render`, inspected the full-size and preview images, and independently checked the 17 ETF comparisons, yield changes, source references and DST/midnight conversions. There were no blocking issues. A misleading connector label in fictional-mode source metadata was corrected and regression-tested; fictional outputs now identify fixture sources.

## Limits

- The script validates arithmetic and structured data, not whether a headline, consensus or causal interpretation is supported by its cited source. Those still require research and review.
- The bundled exchange calendar covers scheduled 2026–2028 NYSE sessions. Exceptional closures must be checked; uncovered dates fail until a verified calendar is supplied. Treasury observations have their own calendar.
- The Python program prepares requests and consumes saved responses; authenticated retrieval remains with the Massive connector. It does not contain a standalone API client or credentials.
- The task JSON is a portable definition. Recurrence parsing and saved task configuration do not establish successful future cloud execution, attachment persistence or notification delivery. Those require a recorded task run and result.
- Live raw responses, trial reports and credentials are not published in this repository.
