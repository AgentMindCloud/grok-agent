<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Cross-Reality Action Fabric — 90-second Demo Script

> Built for xAI, Grok and the whole community on X — the missing
> "do something for me" layer that turns Grok from a chat partner
> into an OS-grade Windows agent.
>
> ⚠️ **This agent can take real-world actions.** Every action requires
> explicit consent. Review the action plan before approving. The agent
> never acts autonomously. — *Article V.3, constitution.md*

---

## Demo at a glance

| Field | Value |
|---|---|
| Total runtime | **90 seconds** |
| Target screen | Windows 11 + Chrome (1920 × 1080), PowerShell 7.4 |
| Recording tool | Windows + Game Bar (`Win + G`) or OBS at 1080p / 30fps |
| Network | Offline. Every action runs through the in-process stub backends. |
| Palette | Cinnabar `#C5524A` on parchment `#FAF6EC` (matches `.streamlit/config.toml`) |
| Audio | Single-take voiceover, no music bed |
| Captions | Burn-in via PowerToys / OBS — required, not optional |
| Demo scenario | "Plan a cross-reality day → approve 3 actions → execute → roll back the last one" |

The demo is one continuous take. **No cuts.** The whole point is to
show that the action fabric runs end-to-end on a real Windows machine
in real time, with the V.3 banner visible at every step where the
agent could touch the real world.

---

## Prep checklist (do once, before recording)

Run all four steps in PowerShell, in order, with the working directory
at `templates\super-agents\cross-reality-action-fabric\`:

```powershell
# 1. Confirm Python 3.12 is in PATH (Windows Store install is fine).
python --version            # expect Python 3.12.x

# 2. Install the dashboard requirements.
python -m pip install -r requirements.txt

# 3. Pre-warm the stub stack so the recording is hermetic.
Remove-Item "$env:LOCALAPPDATA\grok-agent\cross-reality-action-fabric" -Recurse -Force -ErrorAction SilentlyContinue
python agent.py daily-plan --stub --auto-approve --quiet

# 4. Open Chrome at 1920 × 1080. Pin the PowerShell window to the
#    bottom-right quadrant; the dashboard fills the rest.
Start-Process chrome.exe "--new-window http://127.0.0.1:8506"
```

After step 3 the user's `$env:LOCALAPPDATA\grok-agent\cross-reality-
action-fabric\` folder contains:

```
runs\run-YYYYMMDDTHHMMSS.json   # one prior run, used by rollback-last
provenance\YYYY-MM-DD.jsonl     # 11 ActionProvenanceRecord rows
provenance\langfuse_stub_trace.jsonl
memory\qdrant\stub_index.sqlite3
memory\mem0_state.sqlite3
eval\                            # empty until the demo's Self-Improve step
logs\agent.log
connector_audit.db
```

This pre-warm is **only** to prove that the demo isn't a fresh-machine
trick — the recording itself wipes and re-runs the same flow live.

---

## Live recording — frame-by-frame timeline

The voiceover sentences below are the **exact text** to say. They were
counted at a comfortable 165 wpm so the whole thing lands at 90 seconds
without rushing. If you're under, slow down; if over, drop the
parenthetical phrases first.

### `00:00 – 00:05` · Hook (5s)

> **Voiceover:** "Grok runs on X. Now Grok *acts* on your Windows
> machine — with explicit consent on every single action."

**Screen action:**
- PowerShell window focused.
- Type, slowly:
  ```powershell
  cd templates\super-agents\cross-reality-action-fabric
  ```

**Title-card overlay:** "Cross-Reality Action Fabric — Super Agent #3".

---

### `00:05 – 00:15` · Launch the dashboard (10s)

> **Voiceover:** "One command. Six tabs. Article V.3 banner on every
> action surface — local-first, port 8506."

**Screen action:**
- Type, then `Enter`:
  ```powershell
  streamlit run dashboard.py --server.port 8506
  ```
- Streamlit prints the local URL. Chrome opens to
  `http://127.0.0.1:8506`. The Overview tab loads with the cinnabar /
  parchment palette and the V.3 banner visible at top.

**Caption overlay:** "`streamlit run dashboard.py --server.port 8506`".

---

### `00:15 – 00:30` · Overview tab — backends + V.3 banner (15s)

> **Voiceover:** "Five tools across three realities — web via
> Stagehand, local PowerShell on Windows, and read-only public APIs.
> All five backends visible in the sidebar. Notice the V.3 banner —
> every action will be gated."

**Screen action:**
- Hover the V.3 banner at the top of the Overview tab — pause 1s.
- Highlight the **Backends in use** sidebar block
  (`Graph: stub:sequential`, `Langfuse: stub:offline`,
  `DeepEval: stub:offline`).
- Show the **Memory rows per kind** table (5 rows: action / approval /
  rollback / preference / context).

**Caption overlay:** "5 tools · 3 realities · Article V.3 always visible".

---

### `00:30 – 00:45` · Action Planner — Run Daily Plan (15s)

> **Voiceover:** "Click *Run Daily Plan*. The fabric drafts four
> actions — weather, X search, a local PowerShell append, and a
> Stagehand web open. Notice every state-changing action carries a
> verbatim rollback. Constitution Rule 3 in code."

**Screen action:**
- Click the **Action Planner** tab.
- Confirm the sidebar **Force stub mode** toggle is ON, **Auto-approve**
  is OFF (default).
- Click **Run Daily Plan**. Spinner runs ~250ms.
- Scroll through the proposed-actions table — point at the
  `has_rollback` column.

**Caption overlay:** "Every state-changing action carries a verbatim
rollback (Rule 3)".

---

### `00:45 – 01:00` · Pending Approvals — typed approval (15s)

> **Voiceover:** "Switch to *Pending Approvals*. Four steps are queued
> behind the HITL gate. Type the steps you want to approve, click
> *Approve & re-run*. Three actions executed. The fourth stays
> pending — explicit per-step consent, every time."

**Screen action:**
- Click the **Pending Approvals** tab.
- The selector pre-fills "1, 2, 3, 4". Edit it to "1, 2, 3" (skip
  step 4 to demonstrate per-step consent).
- Click **Approve selected & re-run**. Spinner ~250ms.
- Show success message: "Approved 3 step(s) — 3 executed."

**Caption overlay:** "Per-step typed approval — Rule 1 in code".

---

### `01:00 – 01:15` · Provenance Audit + rollback chain (15s)

> **Voiceover:** "Every action wrote one ActionProvenanceRecord. Open
> *Provenance Audit*. Eleven events: plan_built, three approvals,
> three executions, run_complete. Now click *Roll back the most recent
> action*. The rollback-chain visualizer cross-links the rollback to
> its forward action — full audit, both directions."

**Screen action:**
- Click the **Provenance Audit** tab.
- Show the per-event filter dropdowns. Pick `event_kind = action_executed`
  to highlight 3 rows.
- Switch back to "(all)".
- Click **Pending Approvals** → **Roll back the most recent action**.
- Switch back to **Provenance Audit**.
- Scroll to the **Rollback chain visualizer** section — point at the
  one row pairing forward `action_id` ↔ `rollback_id`.

**Caption overlay:** "Rollback chain (Rule 3) — forward ↔ rollback in
one table".

---

### `01:15 – 01:30` · Close — install line (15s)

> **Voiceover:** "Apache 2.0. Windows-native. Built to make Grok the
> obvious choice for every agent on X — explicit consent on every
> action. One command to install — see the launch thread for the line."

**Screen action:**
- Tab back to PowerShell.
- Type, slowly:
  ```powershell
  grok install this
  ```
- Pause 1 second on the install command (don't run it during the demo
  — that's the call-to-action).
- Fade to a closing card with the install line + GitHub URL.

**Closing-card overlay:**
```
Cross-Reality Action Fabric
github.com/AgentMindCloud/grok-agent
> grok install this
Apache 2.0 · Windows 11 · Local-first
Article V.3 — every action requires explicit consent.
Built to help xAI and Grok win.
```

---

## Voiceover word count + pacing reference

| Segment | Seconds | VO words | wpm |
|---|---:|---:|---:|
| Hook | 5 | 18 | 216 |
| Launch | 10 | 17 | 102 |
| Overview | 15 | 38 | 152 |
| Action Planner | 15 | 41 | 164 |
| Pending Approvals | 15 | 41 | 164 |
| Provenance + rollback | 15 | 49 | 196 |
| Close | 15 | 32 | 128 |
| **Total** | **90** | **236** | **157** |

Average pacing 157 wpm — comfortable for a non-pro voice. The hook
runs hot at 216 wpm — that's deliberate; the 5-second hook only works
if you say it briskly.

---

## Visuals + branding

- **Palette:** the dashboard renders in cinnabar (`#C5524A`) on
  parchment (`#FAF6EC`) per `.streamlit/config.toml`. Match every
  caption overlay to those values.
- **V.3 banner:** must be visible in at least four frames — Overview,
  Action Planner, Pending Approvals, and Self-Improve. Don't crop it
  out.
- **Cursor:** standard Windows cursor. No fancy highlight effects —
  we want the demo to feel like real software, not a sales reel.
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
streamlit run dashboard.py --server.port 8506
```

A viewer with the repo cloned and Python 3.12 in `PATH` should hit a
working dashboard in under two minutes.

---

## Variant: zero-stub demo (internal review only)

If presenting to a credential-holding team (xAI engineering, a closed
review) and you want to show the real backends, swap the launch line:

```powershell
$env:OPENWEATHER_API_KEY  = "<your-key>"
$env:LANGFUSE_PUBLIC_KEY  = "<your-key>"
$env:LANGFUSE_SECRET_KEY  = "<your-key>"
streamlit run dashboard.py --server.port 8506
```

The dashboard automatically picks up real backends; the rest of the
script is unchanged.

> ⚠️ **Do NOT record this variant for public release.** The credential
> prompts and any real-world side effects (a Booking.com tab opening,
> a real PowerShell file write) make the recording un-reproducible
> and could leak data on screen.

---

## Failure modes to handle on-camera

If anything below shows up during the recording, **cut and re-take**.

- Streamlit prints `OSError: [Errno 98] Address already in use`. Fix:
  ```powershell
  Get-NetTCPConnection -LocalPort 8506 ; Stop-Process -Id <pid>
  ```
- The Provenance Audit tab is empty. Cause: pre-warm step skipped.
  Fix: re-run the prep checklist's step 3.
- The Pending Approvals tab is empty. Cause: previous run already
  auto-approved. Fix: clear the AppData folder (prep step 3) and
  re-run `agent.py daily-plan --stub --quiet` (without `--auto-approve`)
  so the gate-block path persists the pending plan.
- The Rollback chain visualizer is empty after clicking
  *Roll back the most recent action*. Cause: the prior run had no
  state-changing action with a forward ``action_executed`` record.
  Fix: re-run the prep checklist's step 3 with `--auto-approve` so
  the forward action_executed records exist before the rollback.
- The Self-Improve OverallActionImprovement score is below 0.8 in
  the recording. Cause: one of the per-kind metrics (ApprovalCompliance
  / RollbackSuccess) collapsed. Fix: re-run with `--auto-approve` to
  get clean approvals + rollbacks.

---

## Posting checklist

Once the recording is in the can:

1. Trim to 90 seconds exactly. Cut nothing else.
2. Render at 1080p, 30 fps, MP4 (H.264 + AAC).
3. Burn-in captions at 90% white-on-cinnabar lower-third.
4. Upload to X **as a video reply to tweet #8** of `X_LAUNCH_THREAD.md`.
5. Add the closing-card image as a separate image attachment on
   tweet #10 (the closing frame).

---

> Built to help xAI and Grok win. 🚀
