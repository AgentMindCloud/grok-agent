<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Creator Program v2 — Mon/Wed/Fri Curation Cadence

> Built for xAI, X, Grok and the ecosystem community. Heart.

The curation harness automates the weekly Creator Program rhythm:

| Day | Subcommand | Output |
| --- | --- | --- |
| Monday 09:00 UTC | `monday` | `ContentSelection` — top-3 templates pinned for the week. |
| Wednesday 09:00 UTC | `wednesday` | `ThreadDraft` — 5-7 tweet launch thread for the pinned templates. |
| Friday 09:00 UTC | `friday` | `RetroSummary` — sentiment + theme rollup of creator retros. |

Each subcommand reads from and writes to a local-first directory under
`$env:LOCALAPPDATA\grok-agent\creator-program\curation\`, so the cadence can
run inside GitHub Actions, in a Codespace, or on a creator's Windows 11 box
without any external data store.

---

## Disclaimers (mandatory per `CLAUDE.md` Section 12)

> Warning: **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> Warning: **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

The harness summarizes Creator Program activity. Any inferences a creator
draws about earnings, tax obligations, or investment behavior must be
validated with a licensed professional before being acted on.

---

## Architecture at a glance

```
weekly_curation.run_monday  -->  trend_analyzer.analyze_week
                            -->  content_selector.select_top_n
                            -->  ContentSelection.json on disk

weekly_curation.run_wednesday -->  load Monday's ContentSelection
                              -->  launch_thread_generator.generate_thread
                              -->  ThreadDraft.json on disk

weekly_curation.run_friday  -->  retro_collector.summarize_week
                            -->  RetroSummary.json on disk
```

Module boundaries:

| Module | Responsibility |
| --- | --- |
| `trend_analyzer.py` | Pydantic v2 `TemplateMetrics` + `TrendScore`; weighted-sum scoring (0.4 installs, 0.3 rating, 0.2 mention velocity, 0.1 engagement). |
| `content_selector.py` | `ContentSelection` model; `select_top_n`; JSON persistence under `curation\selections\`. |
| `launch_thread_generator.py` | `ThreadDraft` model; produces 5-7 tweet threads (hook + 1 per winner + CTA), enforces the 280-char limit. |
| `retro_collector.py` | `RetroResponse` + `RetroSummary`; transparent keyword-based sentiment classification; week-level rollups. |
| `weekly_curation.py` | Orchestrator with `monday`/`wednesday`/`friday` argparse subcommands. |

Storage layout under `$env:LOCALAPPDATA\grok-agent\creator-program\curation\`:

```
curation\
  selections\<week_iso>.json
  threads\<week_iso>.json
  retros\<week_iso>\<creator_id>.json
  retros\<week_iso>\_summary.json
```

On Linux CI runners (where `LOCALAPPDATA` is unset), the harness falls back
to `~/AppData/Local/grok-agent/creator-program/curation/` so the path shape
matches Windows for portable test fixtures.

---

## Quickstart (Windows 11 + PowerShell)

Install dependencies into your existing Python 3.12 environment:

```powershell
python -m pip install --upgrade pip
python -m pip install pydantic pytest
```

Run the test suite (the test conftest registers the curation submodule under
the `grok_creator_v2.curation` alias so the hyphenated parent directory
does not block imports):

```powershell
python -m pytest creator-program\v2\curation\tests\ -v
```

Trigger Monday's run with the built-in mock metrics fetcher:

```powershell
python creator-program\v2\curation\weekly_curation.py monday 2026-W19
```

Generate Wednesday's thread draft (consumes Monday's saved selection):

```powershell
python creator-program\v2\curation\weekly_curation.py wednesday 2026-W19
```

Roll up Friday's retro summary (after creators have submitted responses via
`retro_collector.collect_response` + `retro_collector.save_response`):

```powershell
python creator-program\v2\curation\weekly_curation.py friday 2026-W19
```

The `monday` subcommand uses an injectable metrics fetcher; production
deployments override the default by importing
`weekly_curation.run_monday(week_iso, metrics_fetcher=my_fetcher)`.

---

## Sentiment heuristic

Sentiment classification in `retro_collector.collect_response` is rule-based:

* Tokens are extracted with a simple regex, lowercased, and de-duplicated
  per response.
* Positive and negative keyword sets are hard-coded and reviewable in
  source. The label is `"positive"` if positives strictly outnumber
  negatives, `"negative"` if the opposite, and `"neutral"` otherwise
  (including when no keywords match).

This is intentional: the Friday cron job must be auditable end-to-end with
zero network calls. A richer LLM-backed classifier can be layered on later
without breaking the `RetroResponse` schema, because the `sentiment` field
is a `Literal["positive", "neutral", "negative"]` regardless of how the
label is computed.

---

## CI cadence

The GitHub Actions workflow at
`.github/workflows/curation-cadence.yml` runs the matching subcommand on a
cron schedule:

* `0 9 * * 1` — Monday 09:00 UTC -> `monday`
* `0 9 * * 3` — Wednesday 09:00 UTC -> `wednesday`
* `0 9 * * 5` — Friday 09:00 UTC -> `friday`

`workflow_dispatch` is also wired for manual triggering, with an optional
`subcommand` input override (`monday` / `wednesday` / `friday`) so an
operator can re-run any leg without waiting for the next cron tick.

---

## Local-first contract

* No data leaves the host machine unless the calling code explicitly opts
  in. The harness writes JSON files under `$env:LOCALAPPDATA` only.
* Every Pydantic model uses `extra="forbid"` and validates input shape on
  construction so a malformed disk file is caught immediately.
* `week_iso` and `creator_id` strings are screened for path separators and
  `..` segments before being used in filesystem paths.

---

> Built for xAI, X, Grok and the ecosystem community. Heart.
