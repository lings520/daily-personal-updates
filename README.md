# Daily Personal Updates

Skills, instructions, and task definitions for concise personal briefings. The first briefing is a US market update.

## Market update

The `market-update` skill prepares a source-backed daily snapshot covering SPY and QQQ, US Treasury yields, market breadth and sector performance, VIX and other risk indicators, major economic news, and the next US session's calendar in Hong Kong time. It uses Massive first for market data and names any fallback sources.

The primary output is a portrait PNG with a headline, a clearly labelled interpretation, a dreamy pastel palette, sentiment-labelled news cards, an HKT events table, and small monospaced citations. A short accessible summary and source links accompany the image.

## What's here

| Path | Purpose |
| --- | --- |
| [skills/market-update/SKILL.md](skills/market-update/SKILL.md) | Full research, verification, and delivery instructions |
| [skills/market-update/references/image-format.md](skills/market-update/references/image-format.md) | Image payload, visual style, and quality checks |
| [skills/market-update/scripts/render_snapshot.py](skills/market-update/scripts/render_snapshot.py) | Deterministic PNG renderer for verified data |
| [skills/market-update/agents/openai.yaml](skills/market-update/agents/openai.yaml) | Skill display and invocation metadata |
| [tasks/morning-market-update.json](tasks/morning-market-update.json) | Snapshot of the scheduled task's prompt, timing mode, timezone, and iCalendar schedule |
| [examples/market-update.example.json](examples/market-update.example.json) | Fictional sample payload for trying the renderer |

## Use the skill

Use the skill in a compatible assistant that supports installed skills, the Massive connector, live web retrieval, and image/file delivery. Invoke it with `@market-update` or ask for a daily US market briefing. The skill describes how to verify dates and sources, handle holidays and unavailable data, and prepare the structured payload.

The renderer only lays out the supplied values; it **does not** retrieve or validate market data. To try the visual layout locally:

```bash
python3 -m pip install Pillow
python3 skills/market-update/scripts/render_snapshot.py \
  examples/market-update.example.json output/example.png \
  --preview output/example-preview.png
```

The sample is fictional. The renderer needs accessible DejaVu Sans or Liberation Sans fonts, or font paths supplied through its command-line options. See [image-format.md](skills/market-update/references/image-format.md) for the payload and visual review instructions.

## Scheduled task

The task file records the currently configured prompt and schedule, including its IANA timezone, timing mode, and iCalendar representation. It intentionally omits account-specific task identifiers. Consult the scheduler for the live task and its displayed run times; the JSON file is a reference copy and does not create or run an automation by itself.

This repository is a snapshot: editing these files does not automatically update the installed skill or the scheduled task, and changes to those do not automatically update this repository. Synchronize changes explicitly when needed. Do not commit API keys, access tokens, or private update output to this public repository.
