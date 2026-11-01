# Risk & sentiment

`config/risk-context.json` is authoritative for lookback and thresholds; `config/visual-style.json` controls the palette. Values below describe the approved defaults. Change settings in configuration, not duplicated code or task prompts.

## Retrieval and provenance

Use the CNN **US equity** Fear & Greed Index, never the similarly named crypto index. Check https://www.cnn.com/markets/fear-and-greed for the target date's score, published rating, timestamp and previous observation. If the primary source is inaccessible, try one credible dated secondary source that explicitly attributes the score to CNN. Cite the actual retrieved source. Do not reconstruct the proprietary index or infer its score from VIX. On failure, retain the gauge with “Target-date score unavailable”; do not repeatedly probe blocked endpoints. A past date requires that date's observation, never today's live score. An older observation may be shown only with the prominent STALE date label. Preserve published vintage; do not use later revisions as historical known-at-the-time facts.

For each VIX/dollar/oil/gold comparison follow the existing Massive-first benchmark and fallback rules. For dollar, oil and gold, additionally retrieve historical **levels from the same source, instrument/contract and daily cutoff** as both comparison observations. Discover the endpoint before use; bound the lookback to approximately 550 calendar days through the prior observation, follow pagination, and keep the latest 253 valid chronological observations (252 daily returns). Verify completeness against the instrument's trading calendar; absence of data is not a closure. Never use absolute prices as fixed “normal” bounds or join different futures contracts for percentile calculations. A recently listed or illiquid contract may lack sufficient history; show context unavailable. Keep the level and daily move when context is unavailable. Do not silently calculate benchmark context from an ETF's history.

## Editorial input

`fear_greed` is optional; missing data remains unavailable. Verified input:

```json
{
  "publisher": "CNN",
  "score": 42,
  "rating": "fear",
  "date": "2026-10-30",
  "observed_at": "2026-10-30T16:00:00-04:00",
  "cutoff": "published end-of-day observation",
  "prior_score": 45,
  "prior_date": "2026-10-29",
  "prior_cutoff": "published end-of-day observation",
  "source_ids": ["3"]
}
```

These are **fictional schema examples**, not observations. Omit all prior fields if the previous comparable score is unverified; the renderer then says daily change unavailable. `observed_at` must be the source's timestamp with its verified timezone. Do not invent midnight to replace an unknown timestamp; mark the score unavailable until its dated observation can be verified. Retain source provenance for both dates. Allowed published ratings: extreme fear, fear, neutral, greed, extreme greed. The score and rating are complementary; never manufacture a rating from a rounded score.

Each verified `risk` item may include `history`:

```json
{
  "instrument": "DXY",
  "cutoff": "provider daily close",
  "source_ids": ["4"],
  "complete": true,
  "observations": [{"date": "2026-10-29", "level": 100.0}]
}
```

The abbreviated example above intentionally has insufficient history. Supply at least 253 observed levels, strictly ascending with unique dates; the last must match `prior_date` and `prior_level`. Current/future observations, mismatched sources and cutoffs, and nonpositive levels fail validation. `complete:true` is a research assertion, not a substitute for checking gaps. No authored `percentile` field is accepted. For explicitly chosen ETF fallbacks, context currently remains unavailable; do not pass benchmark history under proxy labels.

## Calculations and display

`scripts/risk_context.py` computes the current absolute simple return against the latest 252 **prior** absolute simple returns. Percentile is `100 × (count below + 0.5 × count equal) / 252`; current-day data are excluded. Use unrounded percentile for categories, rounded P-number for display. P90 and P97 are display cutoffs, not predictive signals. Flat-history ties have midrank P50.

| Indicator | Context badges |
| --- | --- |
| VIX level | <15 subdued (mint); 15–<20 moderate (lavender); 20–<30 elevated (peach); ≥30 high (rose) |
| Dollar/oil/gold absolute daily move | <P90 typical (lavender); P90–<P97 large (peach); ≥P97 extreme (rose) |
| Insufficient/unverified context | Unavailable (muted) |

Show the conventions below the table. Colour expresses context, not buy/sell advice, and never replaces signed changes or units.

Above the four-row table, render the Fear & Greed score, published label, comparable point change, and observation timestamp. Use five lavender segments at 0/25/45/55/75/100: `#EDE6F7`, `#D5C6EC`, `#B7A0D8`, `#9476BE`, `#6C4A96`. Add a dark position marker only for a verified score. Keep both endpoint labels. Pale means fear and deep means greed; intensity is not a statement of safety. Keep the entire panel lavender, with a lavender sentiment badge.

Never copy illustrative review scores, daily changes or percentile badges into a real run. Test fixtures must be explicitly fictional. Validate through `compose`, then inspect full-size and 600px images, including extreme labels and unavailable states.
