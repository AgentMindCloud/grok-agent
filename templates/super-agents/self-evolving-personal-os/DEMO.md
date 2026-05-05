<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Self-Evolving Personal OS — 90-second Demo Script

> Built for xAI, Grok and the whole community on X — the personal OS layer
> xAI hasn't shipped yet. This demo runs end-to-end on Windows 11 with the
> `--stub` flag so anyone can reproduce it without API keys.

---

## Demo at a glance

| Field | Value |
|---|---|
| Total runtime | **90 seconds** |
| Target screen | Windows 11 + Chrome (1920 × 1080), PowerShell 7.4 |
| Recording tool | Windows + Game Bar (`Win + G`) or OBS at 1080p / 30fps |
| Network | Offline. Every action runs through the in-process stub backends. |
| Palette | Cinnabar `#C5524A` on parchment `#FAF6EC` (matches `.streamlit/config.toml`) |
| Audio | Single-take voiceover, no music bed (so screen-reader users can follow) |
| Captions | Burn-in via PowerToys / OBS — required, not optional |

The demo is one continuous take. **No cuts.** The whole point is to show
that the agent runs end-to-end on a real Windows machine in real time,
not a montage stitched in post.

---

## Prep checklist (do once, before the recording)

Run all four steps in PowerShell, in order, with the working directory at
`templates/super-agents/self-evolving-personal-os/`:

```powershell
# 1. Confirm Python 3.12 is in PATH (Windows Store install is fine).
python --version            # expect Python 3.12.x

# 2. Install the dashboard requirements.
python -m pip install -r requirements.txt

# 3. Pre-warm the stub stack so the recording is hermetic.
Remove-Item "$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os" -Recurse -Force -ErrorAction SilentlyContinue
python agent.py daily-brief --stub --quiet

# 4. Open Chrome in a fresh window at 1920 × 1080. Pin the PowerShell
#    window to the bottom-right quadrant; the dashboard fills the rest.
Start-Process chrome.exe "--new-window http://127.0.0.1:8505"
```

After step 3 the user's `$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os\`
folder contains:

```
provenance\YYYY-MM-DD.jsonl    # 6 ProvenanceRecord rows
provenance\langfuse_stub_trace.jsonl
memory\qdrant\stub_index.sqlite3
memory\mem0_state.sqlite3
eval\                           # empty until the demo's Self-Improve step
logs\agent.log
connector_audit.db
```

This pre-warm is **only** to prove that the demo isn't a fresh-machine
trick — the recording itself wipes and re-runs the same flow live.

---

## Live recording — frame-by-frame timeline

The voiceover sentences below are the **exact text** to say. They were
counted at a comfortable 165 wpm so the whole thing lands at 90 seconds
without rushing. If you're under a minute, slow down; if over, drop the
parenthetical phrases first.

### `00:00 – 00:05` · Hook (5s)

> **Voiceover:** "Grok runs on X. Now Grok runs your *personal* OS — on
> your Windows machine, offline, with full provenance."

**Screen action:**
- PowerShell window focused.
- Type, slowly:
  ```powershell
  cd templates\super-agents\self-evolving-personal-os
  ```

**Title card overlay:** "Self-Evolving Personal OS — Super Agent #2".

---

### `00:05 – 00:15` · Launch the dashboard (10s)

> **Voiceover:** "One command. Five tabs. Local-first by design — every
> byte stays under your AppData folder."

**Screen action:**
- Type, then `Enter`:
  ```powershell
  streamlit run dashboard.py --server.port 8505
  ```
- Streamlit prints the local URL. Within 2 seconds Chrome opens to
  `http://127.0.0.1:8505`. The Overview tab loads.

**Caption overlay:** "`streamlit run dashboard.py --server.port 8505`".

---

### `00:15 – 00:30` · Overview tab — the "what's wired" view (15s)

> **Voiceover:** "Six personal sources — X mentions, Gmail, Calendar,
> Obsidian notes, weather, news. Backed by a local Qdrant vector index
> and a LangGraph orchestration core. Every backend has a stub fallback,
> so this whole demo runs offline."

**Screen action:**
- Hover the **Backend** sidebar block (`Graph: stub:sequential`,
  `Langfuse: stub:offline`, `DeepEval: stub:offline`) — pause 1s.
- Highlight the **Memory rows per source** table (six rows, one per
  source, populated by the pre-warm step).

**Caption overlay:** "All 6 sources — local-first — zero cloud calls".

---

### `00:30 – 00:45` · Daily Brief tab — one-click LangGraph run (15s)

> **Voiceover:** "Click *Run daily brief*. Behind the scenes, a five-node
> LangGraph state machine ingests, remembers, evolves, briefs, outputs —
> with a self-evolution loop bounded at one extra iteration."

**Screen action:**
- Click the **Daily Brief** tab.
- Confirm the sidebar **Force stub mode** toggle is ON (default).
- Click the **Run daily brief** button.
- Wait for the spinner (~250 ms in stub mode).
- Scroll once to show the six rendered sections:
  Today's schedule → Inbox pulse → X pulse → Notes recent →
  Ambient (weather + news) → Memory health.

**Caption overlay:** "ingest → remember → evolve → brief → output".

---

### `00:45 – 01:00` · Memory Explorer + provenance (15s)

> **Voiceover:** "Search runs against the Qdrant index — six per-source
> collections, PII redacted at write *and* read. The Provenance Audit
> tab shows every step the agent took — six ProvenanceRecords per run."

**Screen action:**
- Click the **Memory Explorer** tab.
- Type `stub` in the search box, click **Search memory**.
- Result table appears; scroll once to show snippets are PII-redacted.
- Click the **Provenance Audit** tab.
- Show the JSONL row count (6) and the per-node trail table.

**Caption overlay:** "Every claim is sourced. Every byte is local."

---

### `01:00 – 01:15` · Self-Improve tab — the weekly evolution loop (15s)

> **Voiceover:** "Click *Run self-improve loop*. Eight Promptfoo asserts
> plus five DeepEval metrics, all human-review-gated. Nothing is
> auto-applied — every suggestion is yours to accept or reject."

**Screen action:**
- Click the **Self-Improve** tab.
- Click the **Run self-improve loop** button.
- Wait ~1 second.
- Show: `Promptfoo PASS 8/8`, `DeepEval PASS 5/5`,
  `Overall self-improvement score: 1.000`.
- Scroll to the **Improvement suggestions** panel (empty on the happy
  path — the green "every check passed" message is the highlight).

**Caption overlay:** "Suggestions are HUMAN-REVIEW-GATED — never auto-applied".

---

### `01:15 – 01:30` · Close — the install command (15s)

> **Voiceover:** "Apache 2.0. Windows-native. Built to make Grok the
> obvious choice for every agent on X. One command to install on your
> machine — see the launch thread for the install line."

**Screen action:**
- Tab back to the PowerShell window.
- Type, slowly:
  ```powershell
  grok install this
  ```
- Pause 1 second on the install command (don't actually run it during
  the demo — that's the call-to-action).
- Fade to a closing card with the install line and the GitHub URL:
  `github.com/AgentMindCloud/grok-agent`.

**Closing card overlay:**
```
Self-Evolving Personal OS
github.com/AgentMindCloud/grok-agent
> grok install this
Apache 2.0 · Windows 11 · Local-first
Built to help xAI and Grok win.
```

---

## Voiceover word count + pacing reference

| Segment | Seconds | VO words | wpm |
|---|---:|---:|---:|
| Hook | 5 | 14 | 168 |
| Launch | 10 | 17 | 102 |
| Overview | 15 | 41 | 164 |
| Daily Brief | 15 | 36 | 144 |
| Memory + provenance | 15 | 36 | 144 |
| Self-Improve | 15 | 35 | 140 |
| Close | 15 | 28 | 112 |
| **Total** | **90** | **207** | **138** |

Average pacing 138 wpm — comfortable for a non-pro voice, leaves room
for emphasis on the cinnabar lines ("local-first", "human-review-gated",
"Apache 2.0").

---

## Visuals + branding

- **Palette:** the dashboard already renders in cinnabar (`#C5524A`) on
  parchment (`#FAF6EC`) per `.streamlit/config.toml` — match every
  caption overlay to those values. Keep text high-contrast (`#1F1B16`
  ink on parchment).
- **Font:** the dashboard uses sans-serif system stack. Captions use the
  same family for consistency.
- **Cursor:** keep the standard Windows cursor (no fancy highlights). We
  want the demo to feel like real software, not a sales reel.
- **No music.** A single voice + the soft Streamlit click sounds is
  plenty.

---

## Reproducing the demo (for the viewer)

The demo's whole pitch is "you can run this in 90 seconds on your own
Windows machine." Include the install line in the closing frame:

```powershell
grok install this
# or, equivalently:
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8505
```

A viewer with the repo cloned and Python 3.12 in PATH should hit a
working dashboard in under two minutes.

---

## Variant: zero-stub demo (for an internal review only)

If presenting to a credential-holding team (xAI engineering, a closed
review) and you want to show the real backends, swap the launch line:

```powershell
$env:OPENWEATHER_API_KEY = "<your-key>"
$env:NEWSAPI_KEY         = "<your-key>"
$env:LANGFUSE_PUBLIC_KEY = "<your-key>"
$env:LANGFUSE_SECRET_KEY = "<your-key>"
streamlit run dashboard.py --server.port 8505
```

The dashboard automatically picks up real backends; the rest of the
script is unchanged. Do **not** record this variant for public release —
the credential prompt is too easy to mis-read in screenshots.

---

## Failure modes to handle on-camera

If anything below shows up during the recording, **cut and re-take** —
do not narrate around it. The demo's credibility depends on it being
clean.

- Streamlit prints an `OSError: [Errno 98] Address already in use`. Fix:
  `Get-NetTCPConnection -LocalPort 8505 ; Stop-Process -Id <pid>`.
- The Provenance Audit tab is empty. Cause: pre-warm step skipped. Fix:
  re-run the prep checklist's step 3.
- Article-II violations panel appears red. Cause: the sidebar's
  **Allow memory writes** toggle is OFF. Fix: turn it ON before clicking
  *Run daily brief*.
- The Self-Improve **OverallSelfImprovement** score is below 0.8 in the
  recording. Cause: one of the personal collections is empty (most
  likely after a partial wipe). Fix: re-run *Run daily brief* once first
  to repopulate, then re-run *Run self-improve loop*.

---

## Posting checklist

Once the recording is in the can:

1. Trim to 90 seconds exactly. Cut nothing else.
2. Render at 1080p, 30 fps, MP4 (H.264 + AAC).
3. Burn-in captions at 90% white-on-cinnabar lower-third.
4. Upload to X **as a video reply to tweet #8** of `X_LAUNCH_THREAD.md`.
5. Add the closing card image as a separate image attachment on
   tweet #10 (the CTA).

---

> Built to help xAI and Grok win. 🚀
