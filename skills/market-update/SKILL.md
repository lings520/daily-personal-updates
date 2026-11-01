---
name: market-update
description: Produce quick previous-day US market snapshot images in English and Simplified Chinese in a dreamy pastel style with a headline and interpretation, using Massive for recent data, covering SPY and QQQ, US Treasury yields, market breadth and sectors, risk and sentiment indicators, major economic events and news, and the next US session’s calendar in Hong Kong time. Use for daily market updates, yesterday's market movements, morning US market briefings, visual market snapshots, or a recap for a specified date.
---

# Market Update

Produce English and Simplified Chinese (zh-Hans) previous-day US market PNGs from the same verified facts, with an accessible 60–100 word English summary, a concise Simplified Chinese equivalent and clickable sources. Keep this as one user-facing skill. The workflow manages files, validation, retries and timing; the assistant retrieves authenticated data, verifies news, writes the interpretation, inspects images and delivers the result.

## Start here

1. Read [languages.md](references/languages.md) for the bilingual setup, translation, fonts and review requirements. Explicitly initialize with `--languages en,zh-Hans` and verified Chinese fonts; do not use Traditional Chinese. Read [workflow.md](references/workflow.md) and use `scripts/workflow.py` as the execution entry point. Initialize a fresh run directory for each briefing. An explicit date means that US/Eastern session; otherwise resolve yesterday in Asia/Hong_Kong. Never reuse fixture data or a previous run's market observations for a new daily briefing.
2. Follow [research-policy.md](references/research-policy.md) for date/session resolution, sourcing, calculations, news and HKT events. Read [data-pipeline.md](references/data-pipeline.md) for the fixed Massive requests, SQL, raw response formats and source fallbacks. Execute connector calls through the authenticated runtime; Market-data scripts do not contain credentials or make market network calls; the separate font installer downloads only public font assets.
3. Supply numeric inputs with `workflow.py put`, then `run`. Resolve its dated/missing-data warnings with verified sources. The workflow pauses when it needs external inputs; a pause is not a failed briefing.
4. Research and write `editorial.json` using the schemas in [data-pipeline.md](references/data-pipeline.md) and [risk-sentiment.md](references/risk-sentiment.md). Read the normalized metrics before interpreting them. Supply the editorial input and resume `run` to compose. Translate the hash-bound template into Simplified Chinese, supply `translation-zh-Hans`, then resume to render both images. After numeric revisions, reverify and re-supply editorial input; stale research cannot silently pass through.
5. Inspect both languages at full size and 600px using [image-format.md](references/image-format.md), then record the actual review against both PNG hashes. Save/display both PNGs through the available delivery tools and record their real returned reference. Recording an attestation does not itself inspect, upload, send or prove a scheduled notification.

## Content and design

Cover SPY/QQQ closing levels and signed changes; 2Y/10Y/30Y yields and bp changes; verified breadth or the labelled RSP/SPY participation proxy; strongest/weakest of all 11 sector ETF proxies; VIX/dollar/oil/gold; CNN US equity Fear & Greed; the two most important prior-day developments; and the next US session's verified HKT calendar. Put a factual headline and a labelled cautious interpretation first, at most 40 words combined.

For English, preserve approved typography B: Bookman headings/bold values, Nimbus Sans body, smaller monospaced citations/footer. For Chinese use the Noto SC font pairing and smaller citations/footnotes defined in `languages.md`. Use the dreamy pastel palette, pale-to-deep lavender Fear & Greed gauge, labelled risk badges, sentiment news cards and HKT events table. Treat colour and historical context as description, not investment advice.

Use shared configuration rather than editing code or duplicating numerical settings in the task:

- `config/market-data.json`: instruments, queries, source conventions and fallbacks.
- `config/us-equity-calendar.json`: verified scheduled sessions; check exceptional closures.
- `config/risk-context.json`: lookback length, thresholds and percentile method.
- `config/visual-style.json`: font paths, palette, background and gauge colours.
- `config/zh-Hans.json` and `config/chinese-fonts.json`: Simplified Chinese UI labels and pinned font downloads.

New runs capture configuration snapshots. Within a run use `configure` for approved style/risk changes; a style change rerenders without refetching facts. Keep the same output quality and require a fresh visual review after rendering changes.

## Non-negotiable checks

Use comparable observations from one source, instrument/contract and cutoff. Verify dates, holidays, DST, units, adjustment conventions, pagination and source coverage. Keep dated/unavailable labels visible. Never turn missing data into zero, fabricate consensus or percentiles, relabel proxies as benchmarks, or use later information as historical known-at-the-time news. Do not generate exact market text/numbers with an image-generation model.

Separate reported facts from inference. Verify every source supports its claim. Missing research remains visibly unverified; it does not mean no event happened. Keep past events separate from the forward calendar. Preserve sources and timestamps in the run; keep private run files and credentials out of the public repository.

Resume only the same briefing attempt. Use `status` and the recorded timings to explain delays honestly; external stages may overlap and include waits. Do not infer a speed-up without comparable measured runs. If sources, rendering or delivery are unavailable, state the specific limitation and provide verified compact text/tables; never claim an absent image was delivered. Do not create or reschedule an automation unless requested.
