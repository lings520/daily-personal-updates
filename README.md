# Daily Personal Updates

Skills, instructions, and task definitions for concise personal briefings. The first briefing is a US market update.

## Market update

The `market-update` skill prepares a source-backed daily snapshot covering SPY and QQQ, US Treasury yields, market breadth and sector performance, VIX, CNN Fear & Greed and other risk indicators, major economic news, and the next US session's calendar in Hong Kong time. It uses Massive first for market data and names any fallback sources.

The primary output is a portrait PNG with a headline, a clearly labelled interpretation, a dreamy pastel palette, Bookman headings with Nimbus Sans body text, a lavender Fear & Greed gauge, computed risk-context badges, sentiment-labelled news cards, an HKT events table, and small monospaced citations. A short accessible summary and source links accompany the image.

## What's here

| Path | Purpose |
| --- | --- |
| [skills/market-update/SKILL.md](skills/market-update/SKILL.md) | Full research, verification, and delivery instructions |
| [skills/market-update/references/image-format.md](skills/market-update/references/image-format.md) | Image payload, visual style, and quality checks |
| [skills/market-update/scripts/render_snapshot.py](skills/market-update/scripts/render_snapshot.py) | Deterministic PNG renderer for verified data |
| [skills/market-update/config/market-data.json](skills/market-update/config/market-data.json) | Fixed instruments, query parameters, and fallback order |
| [skills/market-update/config/us-equity-calendar.json](skills/market-update/config/us-equity-calendar.json) | Verified equity holidays and early closes for 2026–2028 |
| [skills/market-update/queries/equity-returns.sql](skills/market-update/queries/equity-returns.sql) | Filtered two-session ETF comparisons with missing/duplicate checks |
| [skills/market-update/scripts/prepare_market_data.py](skills/market-update/scripts/prepare_market_data.py) | Request planning, decimal calculations, validation, and renderer input |
| [skills/market-update/references/data-pipeline.md](skills/market-update/references/data-pipeline.md) | Exact connector execution steps, input schemas, and fallback handling |
| [skills/market-update/tests](skills/market-update/tests) | Offline fixtures and regression tests, including CLI-to-PNG integration |
| [skills/market-update/agents/openai.yaml](skills/market-update/agents/openai.yaml) | Skill display and invocation metadata |
| [tasks/morning-market-update.json](tasks/morning-market-update.json) | Snapshot of the scheduled task's prompt, timing mode, timezone, and iCalendar schedule |
| [examples/market-update.example.json](examples/market-update.example.json) | Fictional sample payload for trying the renderer |

## Use the skill

Use the skill in a compatible assistant that supports installed skills, the Massive connector, live web retrieval, and image/file delivery. Invoke it with `@market-update` or ask for a daily US market briefing. The skill describes how to verify dates and sources, handle holidays and unavailable data, and prepare the structured payload.

The data pipeline validates observations and computes metrics before the renderer lays out the image. It rejects malformed dates, bad prices, duplicate bars, inconsistent comparisons and unmapped source keys. Missing observations remain unavailable; older Treasury observations retain their dates and request a fallback check. Source support for news and interpretation still requires independent verification.

The Python preparation script does **not** make network calls or inherit connector credentials. A compatible assistant executes its generated requests through the authenticated Massive connector. The normal equity path uses two grouped daily data fetches plus one filtered SQL query for SPY, QQQ, RSP, all 11 sectors, and three optional ETF proxies. A separate date-bounded request obtains Treasury yields. Read [data-pipeline.md](skills/market-update/references/data-pipeline.md) for the full workflow.

Use Python 3.10+ with an available IANA timezone database. Install the tested dependencies:

```bash
python3 -m pip install -r requirements.txt
```

To try just the fictional visual layout:

```bash
python3 skills/market-update/scripts/render_snapshot.py \
  examples/market-update.example.json output/example.png \
  --preview output/example-preview.png
```

The sample is fictional. Approved typography B uses URW Bookman Demi headings/bold values, Nimbus Sans body text, and DejaVu Sans Mono citations/footer. Install `fonts-urw-base35` and `fonts-dejavu-core` on Debian/Ubuntu, or supply font paths through the renderer options. Missing editorial fonts trigger a warning and a documented DejaVu/Liberation fallback. See [image-format.md](skills/market-update/references/image-format.md) for the payload and visual review instructions.

## Test the complete local pipeline

Run the offline suite and the schedule checks. Neither requires API keys or network access:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/market-update/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

To keep an inspectable fictional result:

```bash
SKILL_DIR=skills/market-update
python3 "$SKILL_DIR/scripts/prepare_market_data.py" plan \
  --date 2026-10-30 --as-of 2026-10-31T08:00:00+08:00 --example \
  --output output/fixture/plan.json --sql-output output/fixture/queries.sql
python3 "$SKILL_DIR/scripts/prepare_market_data.py" normalize \
  --plan output/fixture/plan.json --equities "$SKILL_DIR/tests/fixtures/equity-returns.csv" \
  --treasuries "$SKILL_DIR/tests/fixtures/treasuries.json" --output output/fixture/metrics.json
python3 "$SKILL_DIR/scripts/prepare_market_data.py" compose \
  --metrics output/fixture/metrics.json --editorial "$SKILL_DIR/tests/fixtures/editorial.json" \
  --output output/fixture/snapshot.json
python3 "$SKILL_DIR/scripts/render_snapshot.py" \
  output/fixture/snapshot.json output/fixture/snapshot.png --preview output/fixture/preview.png
```

Fixtures exercise holidays, early closes, DST and HKT midnight rollovers, stale/null yields, missing sectors, inconsistent units and dates, and citation validation. They are **never inputs to a real daily update**. Generated reports and raw data belong under ignored `output/` or outside this public repository. See [VALIDATION.md](VALIDATION.md) for the latest recorded validation and its limits.

## Risk and sentiment

Read [risk-sentiment.md](skills/market-update/references/risk-sentiment.md) for retrieval and the input contract. The CNN US equity Fear & Greed gauge uses pale-to-deep lavender, a dark marker, the published label, point change and observation timestamp. Unverified scores remain unavailable; older scores are visibly dated.

VIX badges use labelled display bands. Dollar, oil and gold badges compare the absolute daily return with 252 prior returns from the same source/instrument/cutoff. The Python module calculates midrank percentiles, excludes the current observation, and rejects mismatched or malformed history. With insufficient history it displays context unavailable rather than a made-up percentile. These are descriptive conventions, not trading signals. Review-image scores and P53/P93/P98 examples are never live inputs.

## Scheduled task

The task definition requests **08:00 Asia/Hong_Kong, Tuesday–Saturday**, with an explicit timezone in DTSTART. Its short prompt invokes the installed skill, where detailed research and design rules live. It intentionally omits account-specific identifiers. Consult the scheduler for the live task and its displayed run times; this JSON is a reference copy and does not create or run an automation by itself. Local recurrence tests verify the definition; they do not prove cloud execution or delivery.

This repository is a snapshot: editing these files does not automatically update the installed skill or the scheduled task, and changes to those do not automatically update this repository. Synchronize changes explicitly when needed. Do not commit API keys, access tokens, or private update output to this public repository.
