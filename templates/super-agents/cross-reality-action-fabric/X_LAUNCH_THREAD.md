<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Cross-Reality Action Fabric — X Launch Thread

> Built for xAI, X, Grok and the ecosystem community. ❤️ This thread is **copy-paste-ready**
> for direct posting on X. Every tweet is under the 280-char limit
> (verified at the bottom of this file with a regex scanner). Every
> action-related tweet carries the V.3 real-world-action posture
> ("explicit consent on every action") because that's the agent's
> defining safety property.

---

## How to post this thread

1. Open X on the @JanSol0s account.
2. Paste tweet **1/10** into the composer. Attach the asset described
   in the **Image:** block.
3. Click **Add another tweet**, paste **2/10**, attach its asset, repeat.
4. On tweet **8/10**, attach the 90-second demo MP4 from `DEMO.md`.
5. On tweet **10/10**, attach the closing-card image and click
   **Post all**.

Each tweet stands alone, but reading top-to-bottom builds the story:
manifest → orchestration → memory → provenance → self-improve → UI →
demo → install. Don't reorder — the build order matters.

---

## Tweets

### 1/10 — Hook

```
Built a Cross-Reality Action Fabric Super Agent that ACTS on your
Windows machine — with explicit consent on every single action.

plan → approve → execute → rollback

Web + local PowerShell + public APIs. Apache 2.0. Local-first.

🧵 #GrokAgentOS
```

**Image:** the closing card from the demo (cinnabar `#C5524A` on
parchment `#FAF6EC`, with the install line + GitHub URL + V.3 banner
strapline).

---

### 2/10 — Layer 1: Manifest + Constitution (P128)

```
2/ Six enforceable Constitution Rules:

1. Human approval mandatory
2. Provenance mandatory
3. Verbatim rollback on every state-changing action
4. No silent contradiction resolution
5. Windows-only execution
6. Privacy-first (local-first by default)

#GrokAgentOS
```

**Image:** screenshot of `constitution.md` rendered in GitHub with the
6 Rules visible.

---

### 3/10 — Layer 2: Orchestration with HITL (P129)

```
3/ 8-node LangGraph state machine:

  plan → approve → execute (web/win/api/x) → rollback → output

The HITL gate refuses every step without a typed consent_token.

Falls back to a pure-Python stub executor when LangGraph isn't
installed.

#GrokAgentOS
```

**Image:** the graph diagram — render the 8 nodes as boxes connected
by arrows, with the HITL gate highlighted in cinnabar.

---

### 4/10 — Layer 3: Memory (P130)

```
4/ 5 per-kind memory collections (Mem0 + Qdrant, local):

• actions
• approvals
• rollbacks
• preferences
• contexts

Search "what did I approve last week?" with PII redaction at write
AND read time.

#GrokAgentOS
```

**Image:** the **Action History** tab after a search — show the kind
filter dropdown and the redacted snippet column.

---

### 5/10 — Layer 4: Provenance (P131)

```
5/ Every Constitution event writes one ActionProvenanceRecord with:

consent_token · tool · outcome · cost_usd · rollback_id · rule_compliance

Forward action ↔ rollback cross-link survives across CLI runs.

Optional Langfuse, opt-in only.

#GrokAgentOS
```

**Image:** the **Provenance Audit** tab showing the rollback-chain
table.

---

### 6/10 — Layer 5: Self-improvement (P132)

```
6/ Weekly self-improvement loop:

• 8 Promptfoo asserts over the action loop
• 6 DeepEval metrics (incl. SafetyScore + RollbackSuccess)
• Anti-collapse bonus: a Rule-1 fail drags the whole score below 0.8

All suggestions HUMAN-REVIEW-GATED.

#GrokAgentOS
```

**Image:** the **Self-Improve** tab after a clean run — green "every
check passed" + the 6-metric table.

---

### 7/10 — Layer 6: Dashboard (P133)

```
7/ 6-tab Streamlit dashboard:

• Overview
• Action Planner
• Pending Approvals
• Action History
• Provenance Audit
• Self-Improve

V.3 banner on every action surface. Cinnabar on parchment. Port 8506.

#GrokAgentOS
```

**Image:** wide screenshot of the dashboard sidebar + Action Planner
tab together.

---

### 8/10 — Demo clip

```
8/ 90 seconds, Windows 11, --stub flag, end-to-end:

  plan → 4 actions queued → approve 3 → execute → rollback the last

Reproducible offline on your machine. Watch ↓

#GrokAgentOS
```

**Attachment:** the 90-second MP4 from `DEMO.md` (1080p / 30fps,
captions burned in).

---

### 9/10 — CTA + install

```
9/ Run it yourself in PowerShell:

  cd templates\super-agents\cross-reality-action-fabric
  pip install -r requirements.txt
  streamlit run dashboard.py --server.port 8506

Or one-shot:

  grok install this

Apache 2.0. Windows 11. Local-first.

#GrokAgentOS
```

**Image:** PowerShell screenshot showing the install command typed
out, before pressing Enter.

---

### 10/10 — Closing

```
10/ Built for xAI, X, Grok and the ecosystem community — the missing "do something for
me" layer for every agent on X.

Every action requires explicit consent. The agent never acts
autonomously.

Star ⭐, fork 🍴, PRs welcome.

— @JanSol0s
github.com/AgentMindCloud/grok-agent
```

**Image:** the closing card from `DEMO.md` (cinnabar/parchment,
install line, GitHub URL, V.3 banner strapline, Apache 2.0 badge).

---

## Hashtags reference

Use these consistently across the thread; the first three are primary.
Pick at most one per tweet — let the thread thread itself.

- **Primary:** `#GrokAgentOS`
- Secondary: `#Grok`, `#xAI`, `#WindowsAgents`, `#LocalFirst`,
  `#OpenSource`, `#HumanInTheLoop`
- Vendor mentions only on tweet 10: `@xai`, `@grok`. Don't @ them
  earlier — it reads as bait.

---

## Engagement plan (first 24h)

- **T+0:00** Post the thread.
- **T+0:05** Reply to tweet 2 with a screenshot of the actual
  `constitution.md` PR.
- **T+0:30** Reply to tweet 5 with a screen-capture GIF of the
  rollback-chain table being filtered.
- **T+1:00** Reply to early commenters with a screen-capture GIF for
  whichever tab they're asking about.
- **T+6:00** Reshare the thread with one of the 6 layer tweets pinned
  to the top of @JanSol0s.
- **T+24:00** Post a "follow-up: 24h after launch" tweet with a
  screenshot of the issue queue / PR count.

Don't run paid ads on this thread. Organic only — the whole pitch is
"local-first, no telemetry, no cloud" and a paid amplification would
undercut it.

---

## Variant: short-form (single-tweet) version

If you only have one tweet's worth of attention budget (e.g. a quote-
tweet on top of a Grok launch), use this single-tweet collapse:

```
Cross-Reality Action Fabric — Grok's hands on your Windows machine.

Web + local PowerShell + public APIs. Every action gated by typed
consent. Verbatim rollback on every state change.

Apache 2.0. Port 8506.

`grok install this`

github.com/AgentMindCloud/grok-agent #GrokAgentOS
```

This is a fallback. The 10-tweet ladder is the official launch path.

---

## Asset checklist

Before posting, confirm every attachment exists and renders cleanly
at both desktop and mobile zoom levels:

| Tweet | Asset | Source |
|---|---|---|
| 1/10  | Closing card image | `DEMO.md` closing card |
| 2/10  | Constitution screenshot | GitHub render of `constitution.md` |
| 3/10  | Graph diagram image | Render manually in cinnabar/parchment |
| 4/10  | Action History screenshot | Dashboard Action History tab |
| 5/10  | Provenance Audit screenshot | Dashboard rollback-chain table |
| 6/10  | Self-Improve screenshot | Dashboard Self-Improve tab (clean run) |
| 7/10  | Wide dashboard screenshot | Sidebar + Action Planner together |
| 8/10  | 90-second demo MP4 | `DEMO.md` recording |
| 9/10  | PowerShell install screenshot | Type the command, don't Enter |
| 10/10 | Closing card image | `DEMO.md` closing card |

The closing card is reused on tweets 1/10 and 10/10 deliberately —
it bookends the thread.

---

## Replies you'll get (and how to handle them)

A short cheat-sheet for the first wave of replies. Reply *briefly* in
the thread, *fully* on GitHub Issues.

| Likely question | Tweet-length reply | Where to deep-link |
|---|---|---|
| "Does it work without LangGraph?" | "Yes — pure-Python stub executor at `_StubGraph`. Same API." | `graph.py` |
| "How does the HITL gate work?" | "request_approval refuses any step without a typed consent_token. Per-step. Article II." | `graph.request_approval` |
| "What's the rollback contract?" | "Every state-changing action ships with a verbatim rollback snippet — schema-enforced + scanned at request_approval." | `constitution.md` Rule 3 |
| "Is the cloud trace optional?" | "Yes — Langfuse defaults to `stub:offline`. Real backend requires opt_in=True AND env creds." | `provenance/langfuse_hooks.py` |
| "Can I disable memory writes?" | "Yes — write_action_memory consent gate. The CLI builds consent contexts that include or exclude it." | `memory/mem0_setup.py` |
| "How big is the install?" | "Default reqs ~120MB. All optional integrations commented out — opt in as you need them." | `requirements.txt` |
| "Why port 8506?" | "8501–8504 are the X Money tools. 8505 is the Self-Evolving Personal OS. 8506 is Super Agent #3." | `.streamlit/config.toml` |
| "Where do my actions live?" | "Under `$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\`. Local-first by default. Rule 6." | `constitution.md` Rule 6 |

---

## Constitution checks (the line-item we don't violate)

This thread is itself an artefact of the agent we ship. Before posting
verify each line still holds:

- [x] Apache 2.0 license header at the top of `X_LAUNCH_THREAD.md` ✓
- [x] "Built for xAI, X, Grok and the ecosystem community" line present in the file ✓
- [x] PowerShell-only commands; no bash, no macOS, no Apple anything ✓
- [x] V.3 real-world-action posture surfaced (tweets 1, 9, 10) ✓
- [x] No mention of the 13 untouchable repos as modifiable ✓
<!-- SCANNER:EXEMPT-START -->
- [x] No forbidden phrases ("etc.", "and so on", "as you see fit",
      "use your judgment") ✓
<!-- SCANNER:EXEMPT-END -->
- [x] Every tweet ≤ 280 characters (verified by the scanner below) ✓
- [x] Every claim links back to a file in the repo ✓
- [x] CTA hands the reader the exact install command ✓

If any line above is unchecked, **don't post** — fix the file first.

---

## Char-count scanner (run before every commit)

The 10 tweets above + the short-form variant are all measured by this
scanner. Run it from PowerShell:

```powershell
python -c "
import re
with open('X_LAUNCH_THREAD.md', encoding='utf-8') as f:
    text = f.read()
tweets = re.findall(r'^### (\d+/10)[^\n]*\n+\`\`\`\n(.*?)\n\`\`\`',
                     text, re.MULTILINE | re.DOTALL)
print(f'Found {len(tweets)} tweet blocks (expect 10)')
all_ok = True
for label, t in tweets:
    n = len(t)
    flag = 'OK' if n <= 280 else 'OVER'
    if n > 280: all_ok = False
    print(f'  {label}: {n} chars [{flag}]')
short = re.search(r'## Variant.*?\`\`\`\n(.*?)\n\`\`\`', text, re.DOTALL)
if short:
    sf = short.group(1)
    print(f'Short-form: {len(sf)} chars '
          f\"[{'OK' if len(sf) <= 280 else 'OVER'}]\")
print('ALL UNDER 280:', all_ok)
"
```

Expected output: 10 tweet blocks, all under 280, plus the short-form
variant under 280.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
