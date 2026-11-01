# Fixed market-data pipeline

## Contents

- Responsibilities and files
- Plan and collect
- Normalize and handle follow-ups
- Compose and render
- Editorial schema
- Offline tests and maintenance

## Responsibilities and files

Run the pipeline from the installed skill directory, with all run outputs in a separate scratch directory. The Python script uses the standard library for dates, parsing and arithmetic; composition/rendering also require Pillow. It does not authenticate or make network requests. Use the connected Massive tools for retrieval. A standalone Python API fetcher would require its own credentials and is not part of this workflow.

- `config/market-data.json`: fixed instruments, query templates, adjustment conventions and fallback order.
- `config/us-equity-calendar.json`: officially verified 2026–2028 NYSE scheduled core sessions, including early closes. Verify exceptional closures each run. Update from the linked official source when needed; never guess an uncovered year.
- `queries/equity-returns.sql`: filter to 14 core ETFs plus three optional risk proxies; left joins preserve missing symbols, counts expose duplicates.
- `scripts/prepare_market_data.py`: `plan`, `normalize`, `compose`.
- `tests/fixtures/`: fictional saved responses and editorial data, strictly for offline tests.

## Plan and collect

Set `SKILL_DIR` to the installed skill and `RUN_DIR` to a fresh run directory. For the current morning briefing:

```bash
python3 "$SKILL_DIR/scripts/prepare_market_data.py" plan \
  --output "$RUN_DIR/plan.json" --sql-output "$RUN_DIR/equity-returns.sql"
```

For a historical US date, add `--date YYYY-MM-DD`. The historical calendar is anchored after that report day; morning mode uses the next session not yet begun at retrieval. `--as-of` accepts an offset-aware timestamp for reproducible tests. Do not backdate retrieval timestamps to imply historical data were retrieved then. The default is the actual current time. `--calendar` accepts a verified replacement calendar including exceptional closures. The plan contains the reporting date, completed equity session, prior session, next session, raw request parameters and calendar/config copies.

Execute the fixed requests through Massive:

1. Discover the configured grouped-stock and Treasury paths using `search_endpoints(path=...)`. Verify the documented schema. Do this before API calls, as the connector requires. No broad endpoint search is needed on the normal path.
2. Pass the first equity request's `path`, `params`, and `store_as` to `call_api`. Capture the returned workspace handle. Preserve the raw tool result and request metadata in the run directory.
3. Pass the second equity request to `call_api` with the same workspace. The Treasury request is independent and can run concurrently. Do not send `role` to the API; it is local metadata.
4. Read the stored-table schema. Massive currently renames timestamp `t` to `t_2` because ticker `T` conflicts in SQLite. If this changes, adapt the SQL explicitly to the observed schema. Never substitute price column `T` for timestamp `t`.
5. Submit the generated SQL verbatim to `query_data(sql=..., workspace=...)`. Save its complete CSV text as `equities.csv`; save the Treasury response's complete CSV as `treasuries.csv`. JSON arrays and completed REST `results` envelopes are also accepted. Save returned text directly through structured tool/file arguments; do not manually transcribe values or shell-interpolate raw responses.
6. Preserve pagination and API status. Follow any next-page hint; do not pass an error, truncated result or a first-page subset as a complete response. Stored tables expire after one hour: they are not a persistent daily cache. Regenerate/refetch if the workspace expires.

Two grouped data fetches plus one filtered SQL query cover the equity portion; Treasury yields require one additional bounded query. CNN Fear & Greed, VIX, actual dollar/oil/gold benchmarks and comparable historical levels, macro releases and calendar evidence still require separate retrieval. Optional UUP/USO/GLD rows are available if an explicitly documented benchmark fallback is necessary; collecting them does not authorize silently substituting them.

On a transient timeout/rate limit, retry only the failed request up to twice, respecting provider retry guidance. Do not retry permission failures blindly. If grouped data are unavailable, discover the configured daily open-close path and request each required ticker for both planned dates. Convert those responses to the same rows: `ticker,current_close,prior_close,current_timestamp,prior_timestamp,current_count,prior_count,change_pct`. Verify `from`, `symbol` and adjustment convention; derive a midnight ET millisecond timestamp only from the response's verified session date. Set counts to 0 and values to null for absent bars. Omit `change_pct` if not provided; Python calculates it. Keep one source and adjustment convention within each comparison.

## Normalize and handle follow-ups

```bash
python3 "$SKILL_DIR/scripts/prepare_market_data.py" normalize \
  --plan "$RUN_DIR/plan.json" --equities "$RUN_DIR/equities.csv" \
  --treasuries "$RUN_DIR/treasuries.csv" --output "$RUN_DIR/metrics.json"
```

Invalid dates, duplicate observations, nonfinite/nonpositive prices, wrong sessions, inconsistent SQL returns and future Treasury observations fail with exit code 2. Missing prices are unavailable, never zero. Incomplete sector coverage is retained. Treasury comparisons use each maturity's two newest valid observations on or before the report date, independently of equity sessions. Older latest yields are dated and emit follow-ups; missing maturities are unavailable. Rounding occurs only at display time, using decimal arithmetic.

Read `warnings` and stderr follow-ups before composing. For stale/missing Treasury data, check official Treasury or Fed sources. Save **both observations from one fallback source/series** and rerun normalize with `--treasury-source source.json`. Example metadata shape:

```json
{"name":"US Treasury","kind":"web","series":"Daily Treasury par yields","url":"https://home.treasury.gov/resource-center/data-chart-center/interest-rates"}
```

Use the exact page URL retrieved for the run. Do not silently splice a fallback's latest value with Massive's prior value. If verification remains incomplete, retain the dated/unavailable rows and explain the limitation; `normalize` warnings are follow-up requests, not proof that a holiday occurred. A named equity fallback can likewise be supplied via `--equity-source` with its `name`, `kind`, exact `url` and `adjusted:true`; do not label fallback numbers Massive. Preserve raw evidence alongside the normalized file.

## Compose and render

Build `editorial.json` from independently verified research. Run:

```bash
python3 "$SKILL_DIR/scripts/prepare_market_data.py" compose \
  --metrics "$RUN_DIR/metrics.json" --editorial "$RUN_DIR/editorial.json" \
  --output "$RUN_DIR/snapshot.json"
python3 "$SKILL_DIR/scripts/render_snapshot.py" \
  "$RUN_DIR/snapshot.json" "$RUN_DIR/market-update.png" --preview "$RUN_DIR/preview.png"
```

Composition recomputes normalized metrics from saved observations and rejects edited derived values. It generates all equity/yield cards, sector rankings, the default RSP/SPY participation proxy, source keys and date notes. Do not edit these display strings by hand. Revise editorial wording and recompose if the image exceeds the height limit. Inspect both images, then follow `image-format.md` for saving and delivery. Keep source IDs matched to actual tool evidence; connector-only data need truthful connector attribution, not an unrelated public data URL. The `sources` map is retained in snapshot JSON for caption links.

The script validates structure and arithmetic, not the truth of a headline or whether a claimed source supports it. Verify news, consensus, sentiment and causation separately. Keep the headline and interpretation under 40 words combined. The pipeline does not guess unverified news or future events.

## Editorial schema

Read [risk-sentiment.md](risk-sentiment.md) for optional `fear_greed` and each risk item’s `history`. Composition computes context badges from raw observations; it never accepts hand-written percentiles.

Use the fixture's shape as an example only. Required: `headline`, `interpretation`. Optional fields default to explicit unavailable/unverified output, not invented facts:

- `sources`: object keyed by numeric strings starting at `"3"`; IDs 1 and 2 belong to normalized equity and yield sources. Each value has `name`, `kind` (`web` or `connector`) and exact `url` for web evidence. Fictional `kind:fixture` is accepted only in an explicitly fictional plan.
- `news`: at most two objects with target US `date`, concise `text`, `sentiment` (`positive`, `negative`, `neutral`, `mixed`), `source_ids`, and optional short `label`. Source keys are appended automatically. Empty news produces “verification incomplete,” never an assertion that no releases happened.
- If checks are complete and no major items were verified, set `news_checked_none:true` with `news_source_ids`, or `calendar_checked_none:true` with `calendar_source_ids`, to cite the checked sources and distinguish a quiet calendar from incomplete verification. Do not set these flags without actually checking the sources.
- `upcoming`: at most three objects with `event`, `watch`, `source_ids`, confirmed offset-aware `at`, and source IANA `timezone`. For example, `2026-11-02T10:00:00-05:00` in `America/New_York` converts to 23:00 HKT. Wrong DST offsets and past events are rejected; simultaneous distinct events remain separate rows. Historical mode uses the end of the report day as the exclusion boundary. For uncertain times, omit `at` and use US `date`, `timezone:"America/New_York"`, and `timing` equal to `before market`, `after close`, or `time unconfirmed`; the table preserves that wording and says HKT time TBD.
- `risk`: object with optional `vix`, `dollar`, `oil`, `gold`. Each verified item has `instrument`, numeric `level`/`prior_level`, `date`/`prior_date`, a common `cutoff`, and `source_ids`. Supported primary identifiers are `VIX` (or `VIX index`), `DXY`, `WTI`, and `Gold spot`; preserve actual contract details in the common cutoff for futures and supply `prior_instrument` if needed to confirm identity. Never use different futures contracts for a daily comparison. Units are enforced: points, USD/bbl, USD/oz; VIX changes use points, the rest percentages. An optional `prior_cutoff` must equal `cutoff`. For dollar/oil/gold only, `{"use_etf_proxy":true,"reason":"verified benchmark inaccessible"}` uses the collected UUP/USO/GLD with USD/share labels. VIX has no ETF fallback. Missing entries say unavailable.
- `breadth`: optional verified count data with matching equity-session `date`, named `universe`, `complete:true`, nonnegative integer `advancing`, `declining`, `unchanged`, `total`, and `source_ids`. Counts must sum to total, including unchanged. Without verified counts, use the explicitly labelled RSP/SPY proxy; never compute breadth from the unfiltered whole-market response.

Risk observation and comparison dates/cutoffs remain in the footer, so a differing timestamp is not presented as synchronized with the equity close. Yields include comparison dates too. Missing source references, duplicate equity cards, invalid reporting dates, malformed prices and unknown sentiment values are rejected before rendering. If the conservative formatter does not support a verified alternative benchmark, adapt it with tests or present a clearly sourced text fallback; never relabel an unsupported series as a supported one.

## Offline tests and maintenance

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$SKILL_DIR/tests" -v
```

Tests run without network or API keys, execute the actual SQL in SQLite, and exercise the CLI through PNG generation. They cover missing/duplicate/stale observations, holiday and early-close sessions, DST and midnight conversion, source mappings, proxies, incomplete sector coverage and invalid payloads. For an inspectable fictional preview, use `plan --date 2026-10-30 --as-of 2026-10-31T08:00:00+08:00 --example`, then normalize `tests/fixtures/equity-returns.csv` and `tests/fixtures/treasuries.json`, and compose `tests/fixtures/editorial.json`. Never use those fixture observations for a live report.

When changing files, run the offline suite, one fresh connector smoke test, and visual inspection of full-size and 600px images. Update the installed skill and public repository together when authorized. Keep the scheduled task concise and pointed at the installed skill; the GitHub task JSON is an exported definition, not an executable scheduler or automatic sync mechanism.
