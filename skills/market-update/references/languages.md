# English and Simplified Chinese images

Produce two separate images by default: English (`en`) and **Simplified Chinese (`zh-Hans`)**. Do not substitute Traditional Chinese. Use one normalized dataset and one verified editorial snapshot, never two research passes. Preserve the approved pastel design, risk colours, lavender sentiment gauge, small citations and next-session HKT table.

## Start a bilingual run

```bash
python scripts/install_chinese_fonts.py --font-dir /absolute/writable/market-fonts
python scripts/workflow.py init --run-dir /absolute/new-run --languages en,zh-Hans --chinese-font-dir /absolute/writable/market-fonts
```

Add `--date YYYY-MM-DD` for an explicitly requested US session. Use `--example --as-of ...` only for fictional tests. Legacy CLI runs default to English for compatibility; **the skill and scheduled task must explicitly pass `--languages en,zh-Hans`** unless the user requests English only.

The font installer downloads two SHA-256 verified, open-source Noto CJK SC fonts, then reuses the cache. It contains no market credentials. Noto Sans CJK SC Regular is Chinese body text; Noto Serif CJK SC Bold is headings and smaller Chinese footnotes. Tiny Latin citation markers remain DejaVu Sans Mono. English typography B is unchanged. Font sources and checksums are in `config/chinese-fonts.json`; upstream licensing is at https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE and https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE . Keep fonts and private run files outside the public repository. If download or verification fails, report the precise limitation; never silently render Chinese with a Latin-only font.

## Translate after composing

Follow the normal collection, normalization and research steps in `workflow.md`. After editorial is supplied, `run` composes `artifacts/snapshot.json` and pauses for translation, writing `artifacts/translation-template-zh-Hans.json`. Copy the template to a working JSON file. Fill every blank value in its `translations` map; keep keys and `source_sha256` unchanged. Read the source snapshot and preserve meaning, caveats and interpretation strength. Translate static headings, news sentiment labels and unavailable/stale/proxy wording into Simplified Chinese; use `config/zh-Hans.json` for terminology. Translate the headline, interpretation, news, context, events and footer. Keep headline + interpretation within 140 characters combined. Keep untranslated tickers, source names where appropriate, `bp`, `pts`, `pp`, USD and HKT; explain these units in the accessible summary when useful.

Do not change, omit, add or reorder numeric tokens, signs, units, ticker symbols, source markers or their attached facts. Keep machine metadata and URLs untouched. The calendar may change `02 Nov 2026\n23:00` to `2026-11-02\n23:00`; this exact date-format conversion is validated. Translate prose naturally around the preserved values. Do not translate into Traditional Chinese or mechanically replace characters without checking meaning.

```bash
python scripts/workflow.py put --run-dir /absolute/new-run --slot translation-zh-Hans --file /absolute/translation.json
python scripts/workflow.py run --run-dir /absolute/new-run
```

The translation is bound to the full canonical snapshot hash. A change to figures, editorial, sources or risk configuration requires a new translation template and reverification. A style-only rerender reuses both data and translation. Unknown/missing translation entries, stale hashes and altered protected tokens are rejected. These mechanical checks do not prove semantic accuracy or Simplified character usage: inspect both manually.

## Review and delivery

`status.images` lists both PNGs, previews and hashes. Inspect **both** full-size images and 600px previews. Check Chinese glyphs, wrapping, clipping, tiny citations, financial meaning, missing-data caveats and all figures against English. The source snapshot remains English; translations only affect display. Do not edit the verified snapshot to make Chinese copy fit. Shorten prose without dropping qualifications; never shrink fonts to hide overflow.

Review evidence retains the existing fields (`artifact_sha256` for English, `notes`, `full_size_checked`, `preview_checked`, `facts_checked`) and adds:

```json
{
  "artifacts_sha256": {"en": "<English PNG SHA-256>", "zh-Hans": "<Chinese PNG SHA-256>"},
  "translation_checked": true
}
```

Only attest after actually inspecting both images. Delivery evidence also needs `references: {"en": "<real saved/displayed reference>", "zh-Hans": "<real saved/displayed reference>"}` plus the existing English `reference` and both hashes. Save/display both images with an English 60–100 word accessible summary and a concise Simplified Chinese equivalent, and clickable source links. If one language fails, clearly identify the limitation and deliver the verified available output and compact translated text; do not claim the bilingual run completed. Translation time is included in total elapsed wall time, although no separate translation-stage timer is claimed.
