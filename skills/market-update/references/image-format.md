# Market snapshot image

Use the bundled renderer for an exact, repeatable PNG layout. It uses Pillow and renders supplied text verbatim; it does not fetch, calculate, infer, or validate market facts. Use `prepare_market_data.py normalize` and `compose` from [data-pipeline.md](data-pipeline.md) to validate observations, perform calculations and build its input; complete independent source verification for prose and events. Use another deterministic HTML/SVG/chart renderer only if this renderer is unavailable; follow the same design and visual QA rules. Do not generate factual numbers, labels, or headlines with a generative image model.

## Approved visual style

Use the dreamy design approved in this conversation: soft sky-blue/lavender background with diffuse mint and blush, lightly tinted rounded cards, restrained shadows, and dark navy text. Put the headline first and the labelled interpretation in a lavender panel. Use two ETF cards, three yield cards, breadth plus labelled sector leader/laggard, a lavender Fear & Greed gauge and risk-context table, coloured news cards, and the upcoming-events table. Retain a clear hierarchy; decorative colour must not overpower the facts.

- Approved version B: URW Bookman Demi for headings/bold values and Nimbus Sans for regular body text; 27–30px body text and 39–46px primary values/headline at 1200px width.
- Footer: 19px DejaVu Sans Mono or equivalent monospaced type, muted but readable, distinctly smaller than body copy.
- Inline citations: write ordinary source keys such as `[1]` in the payload. The renderer styles them as monospaced superscripts at about 60% of surrounding text (14–19px), even in bold labels and tables. Keep them attached to the preceding word. Do not manually fake superscripts with Unicode digits, shrink the main text, or drop citations.
- Sentiment: mint/green for supportive, blush/rose for adverse, lavender for neutral/mixed. Use a visible label as well as colour. Judge implications from verified evidence, not the sign of a statistic or a desire to balance colours. Matching consensus is ordinarily neutral; a lower yield or higher oil price is not automatically good or bad. Treat the tag as interpretation, never as a trading instruction.
- Preserve numeric signs and units regardless of colour. The pastel style must remain legible at 600px width.

## Prepare the payload

Write a UTF-8 JSON object in the current run's scratch workspace. Never write daily outputs or data into the installed skill directory. The pipeline emits schema version 3 and a `sources` map. Every `[n]` marker must resolve to that map; retain it alongside the image for caption links. Set `example: true` only for clearly labelled fictional tests. Required display fields:

| Field | Content |
|---|---|
| `report_date` | Exact target US date and US/Eastern label |
| `headline` | Factual 6–12 word headline reflecting the verified day |
| `interpretation` | One cautious inference; headline plus interpretation at most 40 words total |
| `session_note` | Actual equity session and prior-session comparison dates; closed-session caveat where applicable |
| `equities` | Exactly two rows: SPY and QQQ |
| `yields` | Exactly three rows: 2Y, 10Y, 30Y |
| `fear_greed` | Validated score/rating/change/observation note or explicit unavailable state; see [risk-sentiment.md](risk-sentiment.md) |
| `risk` | Exactly four rows: VIX, dollar, oil, gold, with truthful benchmark/proxy names |
| `breadth` | One or two concise strings describing the named breadth measure or participation proxy |
| `sectors` | Object with `leader`, `laggard`, and `coverage` strings; include names, returns, proxy labels and source keys; state complete or partial coverage |
| `news` | One or two objects: `text`, `sentiment`, and optional `label`; use a neutral unavailable/no-verified-news item when appropriate |
| `upcoming` | One to three objects with `hkt`, `event`, and `watch` strings for the three table columns; include full year where ambiguous and one event per row |
| `footer` | One to five concise strings: actual source names and citation keys; data-date exceptions; retrieval date/time in HKT |

Structured examples (illustrative shapes, not current facts):

```json
{
  "sectors": {"leader": "Energy (XLE) +1.20% [1]", "laggard": "Tech (XLK) −0.80% [1]", "coverage": "Across all 11 sector ETF proxies. [1]"},
  "news": [{"text": "Release matched the verified consensus. [2]", "sentiment": "neutral", "label": "NEUTRAL · IN LINE"}],
  "upcoming": [{"hkt": "[verified HKT date]\n[verified time]", "event": "[verified release] [3]", "watch": "Revisions vs flash"}]
}
```

Allowed news sentiments: `positive`, `negative`, `neutral`, `mixed`. A short optional label adds context, e.g. `ADVERSE · TECH SENTIMENT`; it must agree with the sentiment and must not exaggerate certainty. If no upcoming event is verified, use one neutral table row with `hkt: "—"`, an honest `event` status, and a `watch` explanation; do not invent a date. Do not combine two events in one row merely because they share a release time.

Each numeric row is an object: `{"cells": ["label", "level with units", "daily change with sign and units"], "tone": "neutral"}`. Allowed numeric tones are `up`, `down`, and `neutral`. Risk rows also have a computed `context` object with a label and `mint`, `lavender`, `peach`, `rose` or `muted` tone; never author live percentile badges by hand. Color is only a visual supplement to signed values; use neutral for Treasury/risk changes unless meaning is clearly explained. Always include missing rows with `Unavailable`, never a fabricated zero.

- Equities: prices in the two ETF cards are USD (the renderer adds `$` to bare numeric prices); change includes both dollar change and percent (e.g., `+$1.00 / +1.00%`). This example is illustrative, not live market data.
- Yields: level has `%`; change has `bp`. Use `2Y`, `10Y`, `30Y` labels; put mismatched observation dates in footer or row label.
- Risk levels: VIX in points, DXY as index points, WTI in USD/bbl, gold in USD/oz. ETF proxies must be labeled with their tickers and `ETF proxy` and levels in USD/share. If a full label is too long, shorten to e.g. `Oil · USO ETF proxy`, retaining essential instrument identity and units.
- Use compact, factual text. Include source reference keys such as `[1]` only if they map to real citations/URLs in the message caption. Attribute market data actually supplied by Massive to Massive; do not invent public URLs for connector-only results.
- Preserve important qualifiers in the image: delayed/unavailable, actual dates, proxy, limited sector coverage. Move long methodology or supporting links to the caption, not essential caveats.
- Do not supply output from a previous day as a rendering fallback, invent illustrative values for a live briefing, or label a test layout as a real update.

## Render and inspect

Resolve `SKILL_DIR` to the installed skill's absolute path. Run:

```bash
python3 "$SKILL_DIR/scripts/render_snapshot.py" "$RUN_DIR/snapshot.json" "$RUN_DIR/market-update-YYYY-MM-DD.png" \
  --preview "$RUN_DIR/preview.png"
```

Use available Pillow in the primary runtime when the default Python lacks it. The renderer prefers URW Bookman Demi and Nimbus Sans (fonts-urw-base35), with DejaVu Sans Mono for citations. It warns and uses DejaVu/Liberation fallbacks if unavailable; disclose this in delivery. provide `--font-regular`, `--font-bold`, and `--font-mono` with available TrueType font paths if necessary. Do not install large dependencies merely for a screenshot if a supported local renderer already exists.

The renderer outputs a 1200px-wide portrait PNG with a measured height, 27–30px body text, a prominent headline, distinct small citation/footer typography, explicit signs, and high contrast. It rejects very long copy or unbreakable labels instead of shrinking text or truncating silently. If rejected, edit the copy and rerun. Keep the layout close to 2300–2800px tall where possible; 3200px is the upper bound. Prefer concise copy over unnecessary height.

Open the rendered image with an available image viewer before delivery. Inspect both full resolution and a roughly 600px-wide preview for clipping, crowded rows, glyph problems, and readable hierarchy. Compare every displayed number, sign, date, unit, source key, and headline against the verified payload. Check that interpretation is visibly labeled and is not stated as proven causation. Check the smaller citations everywhere, including metric labels and table cells; ensure no source marker wraps alone, no sentiment pill overlaps its body, and the HKT table headers/rows remain separated. Verify the footer uses a distinct smaller font. Correct and rerender any defect.

## Save and deliver

Save the final PNG through the available Library workflow, following its skill and upload-only access rules; use the returned persistent file reference and the supported local image embedding so the image is shown, not just linked. Do not assume a scratch link alone persists or that task delivery supports attachments without checking the tool result. Never claim the image was delivered or saved if that failed.

Lead the response with the displayed image. Below it provide a brief accessible text fallback (normally 60–100 words, not a duplicate long report) with the headline, SPY/QQQ moves, key Treasury move and next event time, followed by clickable source links/citations keyed to the image. Keep the fallback useful for screen readers and text-only notification previews. An optional downloadable PNG link is secondary to inline display.

If the runtime cannot render, persist, or attach the image, state the specific limitation plainly and supply the verified compact text/tables for that run (aim under 200 words plus sources). Do not pretend an image exists, remove sections silently, or modify the recurring schedule. Do not replace a failed current image with yesterday's image.
