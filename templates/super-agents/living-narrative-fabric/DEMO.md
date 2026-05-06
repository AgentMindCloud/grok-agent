<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Living Narrative Fabric — Demo video script (P116, Recipe C Slot 8) -->

# Living Narrative Fabric — 90-Second Demo Script

> Built for xAI, X, Grok and the ecosystem community. ❤️
>
> *A cinematic walkthrough of the full eight-slot Super Agent: orchestrator,
> Mem0+Qdrant memory, six connectors, append-only provenance, self-
> improvement loop, and the 7-tab Streamlit dashboard — all running locally
> on Windows 11.*

---

## Recording setup (one-time)

| Item | Value |
|---|---|
| OS                  | Windows 11 (build 22H2 or newer) |
| Shell               | PowerShell 7.x (`pwsh.exe`) |
| Browser             | Google Chrome (latest) — required by CLAUDE.md §4 |
| Recorder            | OBS Studio 30+ — 1080p, 30 fps, system-audio mute |
| Microphone          | Any USB or headset; record at -12 dB peak |
| Window layout       | Single 1920×1080 display, terminal pinned bottom-half + Chrome top-half |
| Default port        | `8501` (Streamlit standard) |
| Local data root     | `$env:LOCALAPPDATA\grok-agent\living-narrative-fabric` |
| Render target       | 60–90 seconds, exported as `.mp4` (H.264, 1080p) |

> ⚠️ **Privacy check before recording**: the demo runs in `force_stub`
> mode by default — no API keys are sent anywhere. Confirm the sidebar
> shows "Force stub mode (connectors): ☑" before pressing record.

---

## Scene-by-scene script

### Scene 1 — Hook + title card  ·  `0:00 → 0:08`  (8 s)

**On-screen**

* Black background; title card fades in:
  > **Living Narrative Fabric**
  > Versioned synthesis across X, news, academia, government, and the open web.
  > Built for xAI, X, Grok and the ecosystem community. ❤️

**Narration**

> "Most agents make claims. This one cites them — and never silently
> resolves a contradiction."

**Cut on**: terminal opens.

---

### Scene 2 — Install in one command  ·  `0:08 → 0:20`  (12 s)

**On-screen** — terminal full-screen, type slowly:

```powershell
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\templates\super-agents\living-narrative-fabric
python -m pip install -r requirements.txt
```

Then run the smoke battery to prove the agent works on a fresh box:

```powershell
python orchestrator.py --topic "Grok Agent OS launch" --time-range 7d
python memory\__init__.py
python connectors\__init__.py
python provenance\__init__.py
python eval\__init__.py
python dashboard.py --smoke
```

**On-screen overlay** — checklist appears next to the terminal as each
prints its OK line:

* ✅ orchestrator (7 markdown sections)
* ✅ P111 memory layer smoke OK
* ✅ P112 connectors smoke OK
* ✅ P113 provenance layer smoke OK
* ✅ P114 self-improvement loop smoke OK
* ✅ P115 dashboard smoke OK

**Narration**

> "One git clone, one pip install. Six smoke tests pass on a fresh
> Windows 11 box — no API keys required."

---

### Scene 3 — Launch the dashboard  ·  `0:20 → 0:30`  (10 s)

**On-screen** — type:

```powershell
streamlit run dashboard.py
```

Chrome auto-focuses on `http://localhost:8501`. The sidebar shows:

* Local data root: `$env:LOCALAPPDATA\grok-agent\living-narrative-fabric`
* "Force stub mode (connectors): ☑"
* Tab strip: Overview · Live Pipeline · Contradictions · Provenance · Memory · Improvements · Settings

**Narration**

> "One PowerShell command. The dashboard reads directly from the local
> Mem0+Qdrant store — every byte stays on the machine."

---

### Scene 4 — Live Pipeline: run a synthesis  ·  `0:30 → 0:50`  (20 s)

**On-screen** — click **⚡ Live Pipeline** tab.

* Type into the topic field: `Grok Agent OS launch`
* Time range: `7d`
* Click **Run synthesize()**.
* The 6-node DAG strip fills column-by-column with `ok` counts:
  `ingest → normalise → detect_contradictions → score → audit → finalize`.
* A green banner appears:
  > Version `xxxxxxxxxxxxxxxx` persisted (confidence 60/100, 18 claims, N contradictions).

**Narration**

> "Six connectors fan out — NewsAPI, GNews, Semantic Scholar, data.gov,
> X via Grok 4.3, and Crawl4AI. Eighteen claims land in memory, every
> one carrying a non-empty source_id. Constitution Article: source
> citations are mandatory."

**Cut to** — zoom on the four-metric Synthesis Confidence panel:
`0.30·SourceDiversity + 0.30·ProvenanceCompleteness + 0.25·CrossSourceAgreement + 0.15·RecencyCoverage`.

---

### Scene 5 — Contradictions explorer  ·  `0:50 → 1:05`  (15 s)

**On-screen** — click **🪢 Contradictions** tab.

* A severity-sorted table fills the screen.
* Pick the top-severity row.
* In the "Flag a contradiction" form, type:
  > Reason: "Authority spread too narrow — re-check Semantic Scholar weighting."
* Click **Flag this contradiction**.
* Green banner: `Flag <flag_id> recorded (immutable; visible in audit_trail forever).`

**Narration**

> "Both sides of every contradiction stay visible — the orchestrator
> never picks a winner. Flags are append-only and survive every rewind."

---

### Scene 6 — Provenance report + Markdown download  ·  `1:05 → 1:18`  (13 s)

**On-screen** — click **📜 Provenance Reports** tab.

* Pick the version we just produced.
* The full Markdown report renders in-page: Topic Snapshot, Run Timeline,
  Connector Activity (6 rows), Contradictions Flagged (with the one we
  just added), Bridges (≥3).
* Click **Download Markdown report**. A toast confirms:
  `lnf-provenance-<version_id>.md downloaded.`

**Narration**

> "Append-only JSONL on disk; optional Langfuse spans for cloud audit.
> One click exports the whole timeline as Markdown."

---

### Scene 7 — Rewind through Memory Explorer  ·  `1:18 → 1:28`  (10 s)

**On-screen** — click **🧠 Memory Explorer** tab.

* Topic dropdown: `Grok Agent OS launch`.
* History table shows two rows (v1 and v2).
* Drill into v2 → the rewind chain table shows v1 as parent.
* Click **Rewind to selected version**. Sidebar updates:
  `Active version set to <v1_id>.`

**Narration**

> "Versioned synthesis means you can rewind to any prior state. Memory
> is official SQLite, semantic search via Qdrant — both fully local."

---

### Scene 8 — Self-improvement run + suggestion  ·  `1:28 → 1:38`  (10 s)

**On-screen** — click **🛠️ Improvements** tab.

* "Dry run" checkbox: ☑
* Click **Run weekly eval**.
* Spinner runs ~2 s; banner appears:
  `Run <run_id> complete: overall 100/100; 2 versions evaluated; 1 suggestion(s).`
* Suggestion card slides in: `[WARNING] Promptfoo category 'audit' below pass-rate floor`.

**Narration**

> "Weekly Promptfoo + DeepEval loop. Suggestions are dry-run by default —
> nothing changes on disk until you say so."

---

### Scene 9 — Outro + CTA  ·  `1:38 → 1:30`  (~2 s padding to 90 s)

**On-screen** — fade to title card:

> **Living Narrative Fabric**
> One YAML manifest. One PowerShell command.
> `github.com/AgentMindCloud/grok-agent`
>
> Built for xAI, X, Grok and the ecosystem community. ❤️

**Narration**

> "Eight slots, one Super Agent. Open source, Apache-2.0, Windows-first.
> Try it: github.com/AgentMindCloud/grok-agent."

**Hard cut**.

---

## Post-production checklist

* [ ] Burn-in lower-third caption: `github.com/AgentMindCloud/grok-agent`
* [ ] Show the `[stub source]` watermark on the connector cards in scene 4
      so viewers know no real API was hit during the demo.
* [ ] Mute system audio between scenes 2 and 3 to keep the install
      crisp; un-mute for the dashboard so Streamlit's click sounds
      land naturally.
* [ ] Title card font: Inter Bold; accent colour cinnabar (`#e34a33`)
      per the Residual Frequencies palette in CLAUDE.md §3.
* [ ] Final render: 1920×1080, H.264, ~6 Mbps target, 90 s exact.

---

## Bridges (three minimum, per the Constitution)

Pair this demo with at least three of the fabric's neighbours so
viewers see the wider story:

* `self-evolving-personal-os` — Super Agent #2 personalises every synthesis.
* `cross-reality-action-fabric` — Super Agent #3 turns synthesis into action.
* `analytics-summarizer` — creator template; periodic narrative health.
* `x-money-companion-dashboard` — X Money tool #1; cashtag context.

---

*Built for xAI, X, Grok and the ecosystem community. ❤️ Apache-2.0.
Local-first. Privacy-first.*
