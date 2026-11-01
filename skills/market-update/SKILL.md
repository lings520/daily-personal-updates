---
name: market-update
description: Produce a quick previous-day US market snapshot image in a dreamy pastel style with a headline and interpretation, using Massive for recent data, covering SPY and QQQ, US Treasury yields, market breadth and sectors, risk and sentiment indicators, major economic events and news, and the next US session’s calendar in Hong Kong time. Use for daily market updates, yesterday's market movements, morning US market briefings, visual market snapshots, or a recap for a specified date.
---

# Market Update

Lead with one factual, source-backed market snapshot PNG, readable at a glance, with a short accessible text fallback and source links below. Put a factual headline and a clearly labeled one-sentence interpretation at the top of the image (roughly 30–40 words combined, at most 40). Keep all core sections below in compact visual form; prioritize the biggest developments and avoid duplicating the image with a 300+ word report. Read [references/image-format.md](references/image-format.md) for the payload, bundled renderer, visual QA, and delivery workflow. Use live retrieval for every run. Do not create an automation unless separately requested.

## Resolve the reporting date

- Use an explicit requested date if supplied. Otherwise set the target date to yesterday's calendar date in the user's current timezone, defaulting to Asia/Hong_Kong when no timezone is available. Interpret that date as the US market session and US news date in America/New_York; say so in the header. This supports a Hong Kong morning recap of the prior US session.
- State the exact target date and US/Eastern convention, plus the retrieval time in the user's timezone. Use IANA timezone conversion to respect daylight saving; do not hardcode the Hong Kong–New York offset.
- Check whether the target session has completed, including early closes. If it has not, clearly label available prices as intraday or use the latest completed session and label its date; never call them final target-date closes.
- On weekends or US equity holidays, say that equities were closed and show the latest completed session on or before the target date as context, with its actual date. Keep the news window on the target calendar date. If the target-day news is quiet, briefly add separately dated context from the last session only when useful.
- Compare each asset to its own immediately preceding available trading-day observation. Treasury and equity calendars can differ. A missing response alone does not prove a holiday: verify the calendar or disclose missing data.

## Run the fixed data pipeline

Read [references/data-pipeline.md](references/data-pipeline.md) and use the bundled `scripts/prepare_market_data.py` for every run. Run `plan` to resolve dates and produce fixed Massive requests plus SQL, execute those requests through the connected Massive tools, then run `normalize` on the saved responses. Resolve its follow-ups with the specified fallback sources, and use `compose` to combine verified metrics with sourced news, risk benchmarks, and calendar events. Never hand-calculate or hand-edit generated numeric cards. Use `tests/fixtures/` only for explicitly fictional offline tests.

Use `config/market-data.json` for instrument mappings, endpoint templates and fallback order; use `config/us-equity-calendar.json` for verified scheduled equity sessions. Verify exceptional exchange closures each run, and refresh the calendar from its official source when needed. The script refuses uncovered years; do not extrapolate holidays. Treasury observations use their own available dates. Preserve raw responses and query parameters in the current run directory for inspection, not in the installed skill or public repository.

The normal path uses two date-specific grouped equity requests, one fixed SQL filter for the required ETFs, and one bounded Treasury query. Keep the grouped tables in Massive and return only the filtered rows. Preserve the workspace handle and inspect the reported schema; Massive renames `t` to `t_2` to distinguish it from `T`. If a grouped request is unavailable, use the configured per-ticker fallback for the same dates and adjustment convention. Missing data must remain visible; do not treat missing responses as holiday evidence.

## Retrieve prices and yields with Massive

Discover the current Massive tools by name and description. Call `search_endpoints(path=...)` for the configured paths before `call_api`; verify the current schema rather than performing open-ended discovery or inventing endpoint fields. Rediscover alternatives only if the configured path is unavailable or has changed. Batch independent requests when supported.

### SPY and QQQ

- Retrieve both target-session and preceding-session regular-hours closes for SPY and QQQ. Use daily historical data, not a current snapshot or a relative previous-close endpoint when reporting a specific date.
- Endpoint discovered during creation: `/v1/open-close/{stocksTicker}/{date}` with `adjusted=true`; use `close`, `from`, and `symbol`. Ignore `preMarket` and `afterHours` for the headline. A discovered daily aggregate range endpoint is also suitable when it returns comparable completed session closes.
- Use the same split-adjustment convention for both observations. Daily price change is `close - prior_close`; daily percent change is `(close / prior_close - 1) * 100`. Calculate from unrounded data, then round USD and percent changes to two decimals and show signs. Do not use open-to-close returns or imply dividend-inclusive total returns.
- Identify SPY as the S&P 500 ETF proxy and QQQ as the Nasdaq-100 ETF proxy. Do not label QQQ as the Nasdaq Composite or claim these ETFs measure market breadth.
- Report closing price, dollar change, and percent change in two side-by-side ETF cards. Add one brief sentence about relative performance when useful.

### US Treasury yields

- Use Massive first. Endpoint discovered during creation: `/fed/v1/treasury-yields`. Query a date-bounded range ending on the target date, sorted descending, with sufficient records to identify the target and preceding available observations. Verify dates and missing fields.
- Use `yield_2_year`, `yield_10_year`, and `yield_30_year`. Treat these as daily constant-maturity observations, not live executable Treasury quotes or necessarily equity-close timestamps.
- Report yield levels in percent and day-over-day changes in basis points. For yields expressed in percent, calculate `change_bp = (yield - prior_yield) * 100`; e.g., 4.20% to 4.25% is +5 bp. Missing values are not zero.
- Optionally add the 10-year minus 2-year spread in bp and its change when it explains a material curve move. Do not confuse rising yields with rising bond prices.
- If Massive yield data are unavailable, stale, or permission-limited, try official US Treasury daily par yield rates or Federal Reserve H.15/FRED constant-maturity series (DGS2, DGS10, DGS30). Name the fallback and observation date. Compute changes within a consistent source and series, never splice sources silently.
- If target-date yields are not yet published, label the latest available date and its comparison date. Do not present an older observation as the target date or use a later observation to fill a historical gap.

## Verify the day's events and news

- Browse the web for the exact target US date, using recent-event search where appropriate. Confirm release/event dates as distinct from article publication dates. For historical recaps, use information available by the end of the reporting day; avoid hindsight and later revisions presented as original results.
- Check official calendars and releases for Federal Reserve rate decisions/minutes, CPI/PPI and employment (BLS), PCE/GDP (BEA), retail sales (Census), jobless claims (Labor Department), ISM manufacturing/services surveys, and S&P Global flash/final PMIs. Cover only events that occurred on the reporting day, prioritizing those with market relevance.
- For relevant releases, give actual, consensus if reliably sourced, and prior when available, with units, reference period, headline/core distinction, and revisions. Label survey provider and flash/final vintage. Never manufacture consensus or treat a prior value as a forecast; omit unavailable comparisons or mark them unavailable.
- For a rate decision, state the resulting target range, the size/direction of change in bp, and the key guidance. Include other central-bank decisions only if materially relevant to US markets.
- Add material earnings, policy, geopolitical, or company news only when it helps explain broad-market moves. Use official releases for facts and reliable contemporaneous financial reporting for market reaction. Massive news endpoints may supplement coverage but do not replace verification of macro releases.
- Select the two most important verified event/news items for the image; retain additional detail only if specifically requested. Distinguish reported explanations from inference: use “coincided with” unless evidence supports a stronger causal claim. Do not attribute the entire day's move to one release without support.
- If no major scheduled US releases occurred, say so only after checking calendars. If verification is incomplete, state that no major releases were verified rather than asserting none occurred. Never fill this section with upcoming events.

## Add breadth, sectors, and risk context

Use Massive first for these market data too, discovering supported endpoints and instrument identifiers before requesting them. Use the same completed equity session and comparable prior-session observations as the headline where applicable. Label differing session dates and observation times rather than implying synchronized closes.

### Market breadth and sectors

- Prefer a verified daily advancing/declining count or percentage of advancing constituents for a named universe (e.g., NYSE-listed issues or S&P 500 constituents). Identify the universe, date, source, treatment of unchanged issues, and denominator. Do not build a supposedly complete universe from a partial or unfiltered API result; account for pagination and missing observations.
- If reliable breadth counts are unavailable, use RSP versus SPY daily price returns as an explicitly labeled equal-weight-versus-cap-weight participation proxy. Report the return gap in percentage points. Do not call that gap an advance/decline statistic or treat it as proof that a few stocks caused the move. If neither is available, say breadth is unavailable.
- Compare all 11 US sector ETF proxies for the same session using comparable closes: XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY. Verify the ticker/sector mapping. Name the strongest and weakest sector and their daily percent changes; label them ETF proxies. If coverage is incomplete, name the observed subset and say “among sectors checked,” never rank it as the full market.
- Compress the result to one or two sentences explaining whether participation was broad or concentrated only to the extent supported by the evidence.

### Risk indicators

Read [references/risk-sentiment.md](references/risk-sentiment.md) for CNN Fear & Greed retrieval, dated observations, the lavender gauge, VIX bands, and 252-return historical context. Use its structured inputs and deterministic calculations; never use the review images’ illustrative values.

- Add the Fear & Greed gauge above a four-row context table with VIX, the US dollar, oil, and gold: named benchmark, level with units, and daily change. Use VIX index level and change in index points; use percentage changes for the other three.
- Prefer the actual VIX index, DXY US Dollar Index, WTI crude (USD/barrel), and gold spot (USD/troy ounce) when accessible. Verify identifiers, dates, and quotation conventions. Never label a volatility ETF as VIX or a broad trade-weighted dollar series as DXY.
- Use a named reliable alternative source if Massive does not cover a benchmark. If necessary, use clearly labeled liquid ETF proxies (such as UUP for the dollar, USO for oil, and GLD for gold), quote ETF prices in USD/share, and do not describe them as the underlying benchmark. Do not silently switch between spot, futures, and ETFs or compare unlike instruments.
- For futures, identify the contract and settlement/close convention. Compare the same contract across observations and flag rollover effects where relevant. For FX, commodities, and indices, use consistent daily cutoffs and disclose when dates differ from equities. Never mix a live quote with a prior session close as a daily completed-session return.
- Add commentary only when a move is notable in its verified recent context or directly relevant to the day's news. Do not invent historical percentiles or declare significance from an arbitrary threshold. Missing indicators must be marked unavailable, not omitted without explanation.

## Add the next-session calendar

- Keep this forward-looking section separate from “What happened.” For a current morning briefing, identify the next US equity session that has not begun as of retrieval, including Monday/holiday adjustments; include material pre-market releases for that session. For an explicitly historical recap, anchor the calendar to the next session after the report date and describe events as they were scheduled then, without hindsight.
- Verify official publisher calendars and select the top 2–3 relevant upcoming releases, central-bank events, or major earnings. Do not pad a quiet calendar with low-impact items. If no major items are verified, say so and identify the next verified major event if useful.
- Give each event's Hong Kong calendar date and time (HKT, Asia/Hong_Kong), converting from the verified source timezone with IANA timezone rules. Include the date rollover for events that occur after midnight HKT. Do not hardcode a 12- or 13-hour offset; DST changes can fall between sessions. If only “before market” or “after close” is confirmed, retain that label instead of inventing an exact time.
- Exclude events already completed at retrieval from the upcoming list. Include consensus only if verified, and never supply actual results for an event still in the future relative to the briefing.

## Interpret the combined moves

Give one cautious sentence synthesizing equity participation, Treasury yields, and risk indicators. Explicitly label an inference (e.g., “Taken together, this suggests…”), distinguish it from sourced facts, and acknowledge mixed signals where appropriate. Do not force a risk-on/risk-off narrative or imply a forecast or trading recommendation. Avoid repeating this sentence elsewhere.

## Render and deliver the snapshot

Use the `compose` output with bundled `scripts/render_snapshot.py` and the instructions in [references/image-format.md](references/image-format.md). Render precise data programmatically from the verified payload, not with generative image text. Use this top-to-bottom order inside one image:

1. **Header:** exact report date (US/Eastern), a prominent factual headline, and a clearly labeled one-sentence interpretation immediately beneath it, at most 40 words combined. State the actual equity session/comparison dates and any market-closed context.
2. **US equities:** SPY and QQQ closing prices in USD and signed dollar/percent changes.
3. **Treasury yields:** 2Y, 10Y, and 30Y yields in percent and signed changes in bp; label differing observation dates.
4. **Breadth and sectors:** compact named breadth measure or participation proxy, strongest/weakest sector proxies and changes, with incomplete-coverage caveats where needed.
5. **Risk & sentiment:** CNN Fear & Greed score/label, dated point change and lavender gauge; VIX/dollar/oil/gold levels, signed daily changes and computed context badges. Follow risk-sentiment.md; mark missing scores or history unavailable.
6. **What happened:** the two most important verified event/news headlines in tinted cards with visible sentiment labels. Use mint for supportive, rose for adverse, and lavender for neutral or mixed market implications. Include actual versus consensus when verified and relevant. Treat an in-line release as neutral unless independent evidence supports another interpretation; do not force positive/negative labels or map a rising number automatically to positive sentiment.
7. **What to watch next:** a three-column table: **HKT date/time | Event | What to watch**. Include up to 2–3 verified events with Hong Kong dates and times; keep each event on its own row, including simultaneous events. Make the final column a short observation focus, not a forecast or invented consensus. For uncertain times, retain the verified before-market/after-close label.
8. **Footer:** actual data sources, observation-date exceptions, and retrieval date/time in HKT. Map compact source keys to real clickable links/citations below the image; never invent citations or attribute connector-only numbers to unrelated web sources.

Apply the approved visual system: a soft blue/lavender gradient with mint and blush accents, lightly tinted rounded cards, dark navy main text, prominent ETF values, and a lavender interpretation panel. Use smaller monospaced footer text (19px at 1200px image width). Render every inline numeric source marker as a muted monospaced superscript at about 60% of adjacent text size (14–19px), including inside bold labels, metric cards, news, and tables. Never leave citation markers at body size or on an orphaned line. Pair sentiment colours with written labels.

Inspect the rendered image at full size and at a roughly 600px-wide preview; check clipping, legibility, exact numbers/signs/units, date labels, and source mapping. Keep body type readable and shorten copy instead of shrinking it. Save the final image using the available Library workflow and show it inline using supported image embedding; retain source links in the accompanying caption because links inside a PNG are not clickable.

Follow the image with a 60–100 word accessible text fallback summarizing the headline, equity moves, key yield move and next event time, plus source links/citations. Do not repeat a full 350–500 word narrative. If rendering or attachment is unavailable, clearly disclose the limitation and provide the verified compact text/tables for that run (aim under 200 words plus sources). Never claim a missing image was created or delivered.

If Massive is inaccessible, clearly disclose the limitation and use a named, reliable alternative where available; do not claim the data came from Massive. If prices, yields, news, or consensus cannot be verified, mark the affected items unavailable and provide the verified remainder. Do not fabricate values, silently substitute stale data, or turn this factual briefing into unsolicited trading recommendations.

Before sending, check date labels, session completion, ticker identity, return denominators, yield units, source consistency, rounding, and citations. Also verify breadth universe/coverage, complete sector rankings, risk-indicator instrument labels and cutoffs, and Hong Kong event dates including DST and midnight rollovers. Keep the calendar separate from past events and keep the whole briefing concise.
