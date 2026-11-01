> Default delivery is now English plus Simplified Chinese. Follow [languages.md](languages.md) for bilingual initialization, the translation pause, both-image review evidence and delivery references. Existing English-only commands below remain supported.

# Market workflow

## Contents

- Responsibilities and contracts
- Normal execution
- Review and delivery
- Resume, retry and configure
- Timing and limits

## Responsibilities and contracts

`scripts/workflow.py` is the single supported orchestration entry point. It calls the existing calculation and rendering modules; their standalone CLIs remain available for diagnosis. This is an assistant-mediated workflow, not an unattended Python network client.

| Stage | Owner and input | Output |
| --- | --- | --- |
| Plan | Python; requested date/current clock and configurations | `plan.json`, fixed `equity-returns.sql`, configuration snapshots |
| Collection | Assistant; authenticated Massive calls and named fallbacks | Raw equities/treasuries responses; optional source metadata |
| Normalize | Python; registered raw inputs and plan | `artifacts/metrics.json`, explicit warnings |
| Research | Assistant; verified metrics, sources, news and calendars | `editorial.json`, including verified risk/sentiment inputs |
| Compose | Python; metrics, editorial and risk settings | `artifacts/snapshot.json` |
| Render | Python; snapshot, style settings and resolved font files | `artifacts/market-update.png`, `artifacts/preview.png` |
| Review | Assistant; actual full-size/preview inspection and factual check | Hash-bound review attestation |
| Delivery | Assistant; actual save/display tools | Hash-bound receipt with real returned reference |

`run.json` records statuses, attempts, errors, input/output hashes, configuration changes and timings. Inputs are copied into content-addressed run-local files; replacing a slot preserves previous input versions. `put` registers inputs, not a declaration that their facts are true. Raw response and editorial schemas remain in [data-pipeline.md](data-pipeline.md) and [risk-sentiment.md](risk-sentiment.md). Compose validates arithmetic/structure; the assistant verifies source support.

Statuses are pending, waiting, running, complete or failed. Exit code 0 means the command succeeded, 3 means `run` awaits external inputs, and 2 means invalid input or a failed operation. Read the JSON response. A successful render is ready for review, not proof of delivery.

## Normal execution

Set `SKILL_DIR` to the installed skill directory and `RUN_DIR` to a fresh, empty directory outside the skill/public repository. Do not initialize over an existing run.

```bash
python3 "$SKILL_DIR/scripts/workflow.py" init --run-dir "$RUN_DIR"
```

For an explicit historical US session, add `--date YYYY-MM-DD`. Omit `--as-of` for actual reports so the retrieval context uses the current clock. Use `--example --date 2026-10-30 --as-of 2026-10-31T08:00:00+08:00` only for a labelled offline fixture trial.

Read the plan and generated SQL. Discover the configured endpoints, execute their requests with Massive, preserve its workspace handle, inspect the schema and run the SQL. Follow [data-pipeline.md](data-pipeline.md) exactly, including pagination, timestamp-column mapping and fallback rules. Save complete tool responses, never shell-interpolate raw provider text. Retain separate request metadata/evidence files in the run directory as needed.

```bash
python3 "$SKILL_DIR/scripts/workflow.py" put --run-dir "$RUN_DIR" --slot equities --file /absolute/path/equities.csv
python3 "$SKILL_DIR/scripts/workflow.py" put --run-dir "$RUN_DIR" --slot treasuries --file /absolute/path/treasuries.json
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR"
```

CSV and JSON numeric response formats are supported. Optional `equity-source` and `treasury-source` slots accept the exact metadata JSON described in the pipeline reference. A fallback must include both comparable observations; do not mix sources. Correct only failed/missing retrievals, register their replacement input and resume. Resolve warnings before writing the editorial input; explicitly dated/unavailable output is allowed only after the required verification attempts.

The first `run` completes numeric validation and pauses for research. It starts the research timer automatically. If researching concurrently with collection, call `begin --stage research --run-dir "$RUN_DIR"` before that work. Read `artifacts/metrics.json`, verify releases/news and the next-session calendar, and prepare editorial JSON. All mandatory sections must have verified information or explicit unavailable/unverified states. Risk history and sentiment retrieval remain assistant-led.

```bash
python3 "$SKILL_DIR/scripts/workflow.py" put --run-dir "$RUN_DIR" --slot editorial --file /absolute/path/editorial.json
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR"
```

Editorial input is accepted only after numeric validation, and is bound to that metrics version. If numerical inputs change, resume normalization, recheck the research/interpretation, then re-supply editorial input even if the wording remains correct.

## Review and delivery

Inspect the returned full-size and preview paths. Check all displayed values, signs, dates, units, sources, labels, table spacing and typography. A review receipt must identify the **current** `artifact_sha256` returned by `status`/`run`. Create it only after performing the checks:

```json
{
  "artifact_sha256": "COPY_THE_RETURNED_PNG_SHA256",
  "full_size_checked": true,
  "preview_checked": true,
  "facts_checked": true,
  "notes": "Describe checks actually completed and any disclosed limitations."
}
```

```bash
python3 "$SKILL_DIR/scripts/workflow.py" record --run-dir "$RUN_DIR" --stage review --evidence /absolute/path/review.json
```

Then perform the real save/display operation using the current delivery skill/tool instructions. Record a delivery JSON containing `artifact_sha256`, `reference` (the actual returned persistent file/message reference), and `notes` explaining the operation/result. Run `record --stage delivery --evidence /absolute/path/delivery.json --run-dir "$RUN_DIR"`. Recording does not upload, send messages, or certify notification delivery. Offline tests may record a plainly fictional reference, only inside explicitly fictional runs; never claim it represents publication.

## Resume, retry and configure

```bash
python3 "$SKILL_DIR/scripts/workflow.py" status --run-dir "$RUN_DIR"
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR"
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR" --rerender
```

Resume the same run after a failed command. Completed stages are reused only while their input, output, code, config and font hashes match. A render failure does not repeat successful numeric processing/research. An interrupted running attempt is retried when `run` resumes; previous attempt information remains in the manifest. Do not modify registered raw input files or the immutable plan directly: use `put`, or initialize a new run for a new date. Run directories are not a reusable live-data cache across daily briefings.

Adjust an existing run's approved design or risk configuration with:

```bash
python3 "$SKILL_DIR/scripts/workflow.py" configure --run-dir "$RUN_DIR" --kind visual-style --file /absolute/path/visual-style.json
python3 "$SKILL_DIR/scripts/workflow.py" run --run-dir "$RUN_DIR"
```

Use `--kind risk-context` for approved threshold/lookback edits. A style change rerenders without repeating collection, normalization or research. Risk setting changes recompose and render. Both invalidate earlier review/delivery attestations. Thresholds and their image legend come from the same risk configuration. Fonts and palette come from the same style configuration. Market instruments and exchange calendar are fixed in each plan; update the installed config for future runs, rather than changing a run's plan.

## Timing and limits

Python stages record monotonic execution durations. External collection/research/review/delivery timers measure elapsed wall time from `begin` (automatic at the normal stage boundary) until validation/recording completes. They include assistant/tool waits and may overlap; do not sum them to invent total elapsed time. `seconds` per stage is cumulative across attempts; `last_attempt_seconds` isolates the latest attempt. `first_render_elapsed_seconds` preserves the initial start-to-image interval; `elapsed_to_render_seconds` is the start-to-latest-render interval; `elapsed_wall_seconds` includes the run's lifetime and freezes when delivery is recorded. Cached calls add no new execution attempts. Compare only equivalent runs, and state whether retrieval/research/delivery were included.

Run-local manifests are inspection records, not tamper-proof audit logs. The workflow cannot establish that a cited page is truthful, that the assistant really inspected an image, or that a scheduler delivered a notification; those require actual source/tool evidence. Keep private raw data, manifests and rendered reports outside the public repository. No API keys are required by this local CLI; no connector credentials are copied into it.
