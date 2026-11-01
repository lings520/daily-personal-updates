# Daily Personal Updates

Reusable skills, workflows and scheduled-task definitions for personal briefings. The first workflow produces a compact US market image with verified data, news and the next US session's calendar in Hong Kong time.

## Three responsibilities

| Layer | Responsibility |
| --- | --- |
| [Market Update skill](skills/market-update/SKILL.md) | Understand the request, apply preferences, verify sources and interpret the market |
| [Workflow](skills/market-update/scripts/workflow.py) | Plan, register inputs, validate, compose, render, track review/delivery and record timings |
| [Scheduled task](tasks/morning-market-update.json) | Invoke the installed skill at 08:00 Asia/Hong_Kong, Tuesday–Saturday |

The assistant performs authenticated Massive retrieval, news research, visual review and actual delivery. The Python workflow manages reproducible local stages; it does not contain API credentials, make network requests, inspect images itself or publish files.

## Output and shared settings

The PNG covers SPY/QQQ, Treasury yields, breadth and sector proxies, risk indicators, CNN US equity Fear & Greed, prior-day news and upcoming HKT events. It uses approved Bookman headings, Nimbus Sans body text, small monospaced citations, dreamy colours, a lavender sentiment gauge and labelled risk context. Missing or unverified data stay visible. A 60–100 word accessible summary and source links accompany the image.

| Configuration | Purpose |
| --- | --- |
| [market-data.json](skills/market-update/config/market-data.json) | Instruments, fixed connector requests and source fallbacks |
| [us-equity-calendar.json](skills/market-update/config/us-equity-calendar.json) | Verified scheduled US equity sessions, 2026–2028 |
| [risk-context.json](skills/market-update/config/risk-context.json) | Lookback, thresholds and percentile method |
| [visual-style.json](skills/market-update/config/visual-style.json) | Fonts, palette, background and sentiment gauge |

New runs capture configuration snapshots. The script calculates risk badges and their reference legend from the same thresholds. Review-image example scores are never live data.

## Run and resume

Use Python 3.10+ with an IANA timezone database. Install dependencies with `python3 -m pip install -r requirements.txt`. Approved fonts are provided by `fonts-urw-base35` and `fonts-dejavu-core` on Debian/Ubuntu; configure installed font paths on other systems. Missing approved fonts produce a warning and use configured fallbacks.

Read [workflow.md](skills/market-update/references/workflow.md) for the complete command sequence and input/output contracts. A new briefing starts with:

```bash
SKILL_DIR=skills/market-update
RUN_DIR=output/my-briefing
python3 "$SKILL_DIR/scripts/workflow.py" init --run-dir "$RUN_DIR"
```

Add `--date YYYY-MM-DD` for a historical US session. The assistant executes the generated connector requests and SQL, then registers the responses:

```bash
python3 "$SKILL_DIR/scripts/workflow.py" put --run-dir "$RUN_DIR" --slot equities --file /absolute/path/equities.csv
python3 "$SKILL_DIR/scripts/workflow.py" put --run-dir "$RUN_DIR" --slot treasuries --file /absolute/path/treasuries.json
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR"
```

The workflow validates numbers and pauses for verified editorial research. Register `editorial.json` in the `editorial` slot, then resume `run` to compose and render. The assistant inspects the image and uses real delivery tools before recording review/delivery evidence. Exit code 3 means external input is needed, not a computation failure. Exit code 2 identifies invalid input or a failed stage.

```bash
python3 "$SKILL_DIR/scripts/workflow.py" status --run-dir "$RUN_DIR"
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR" --rerender
python3 "$SKILL_DIR/scripts/workflow.py" configure --run-dir "$RUN_DIR" --kind visual-style --file /absolute/path/visual-style.json
```

Successful unchanged stages are cached within that run. A style revision rerenders without repeating research or calculations. Revised market data require editorial re-verification. Rendering changes invalidate previous visual review and delivery records. Each daily briefing needs a fresh run and fresh retrieval; this is not a cross-day price cache.

Run manifests record hashes, attempts, errors and timings. External timers include assistant work/waits and may overlap; they must not be added to invent an end-to-end time. They do not prove cloud scheduling or notification delivery. Private manifests, raw data and images belong under ignored `output/` or outside this repository.

## Reference and tests

- [Research policy](skills/market-update/references/research-policy.md): dates, source verification, numerical comparisons, news and interpretation.
- [Data pipeline](skills/market-update/references/data-pipeline.md): Massive requests, SQL, raw response formats and retained low-level CLIs.
- [Risk and sentiment](skills/market-update/references/risk-sentiment.md): CNN sourcing, history and missing-data rules.
- [Image format](skills/market-update/references/image-format.md): payload, typography and visual checks.
- [Validation record](VALIDATION.md): completed checks and their limits.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/market-update/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use clearly fictional fixtures and no credentials. For a fixture run, initialize with `--example --date 2026-10-30 --as-of 2026-10-31T08:00:00+08:00`, supply bundled fixture equities/treasuries, run numeric validation, then supply fixture editorial JSON and resume. Never use fixtures for a real briefing.

The public repository, installed skill and live scheduled task are explicitly synchronized copies. Editing a task JSON does not create/update the scheduler. Editing GitHub does not automatically update an installed skill. Never commit credentials or private briefing outputs.
