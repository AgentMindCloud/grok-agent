<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# RFC: Adopt Grok Agent OS as the Reference Distribution + Runtime Layer for Grok-Powered Agents on X

> **One-line ask.** Adopt `grok-agent.yaml` v2.15 as the reference open
> standard for Grok-powered agents on X, and feature the canonical
> `grok install this` install primitive in xAI documentation.
>
> **Status.** Apache-2.0, public, working. Three flagship Super Agents
> shipped, 22 creator templates shipped, CI gating every manifest on
> every push.
>
> **Built to help xAI and Grok win.** We are ecosystem allies, not a
> competing layer. Everything here is designed so any of it can be
> folded into an official xAI standard whenever you want it.

---

## Authors

- **AgentMindCloud** (`@JanSol0s`) — sole maintainer, sole author.
- Repo: <https://github.com/AgentMindCloud/grok-agent>
- Marketplace: deployable to Vercel in three minutes (see
  `marketplace/README.md`).

---

## TL;DR (60 seconds)

Grok 4.3 is the best agent LLM on X. What's missing is a **distribution
layer + runtime layer** so creators can author, install, and run
Grok-powered agents safely. We've shipped exactly that: an open manifest
standard, a Windows-first PowerShell CLI, an Agent Constitution with a
CI-enforced safety scanner, a thin marketplace, and the `grok install
this` X-native install primitive. **None of it competes with anything on
your roadmap; all of it makes the whole road shorter.**

We're asking xAI to:

1. Recognise `grok-agent.yaml` v2.15 as a reference standard in the
   Grok docs.
2. Link the marketplace from a Grok 4.3 system-prompt example or X
   reply hint when the user asks how to ship an agent.
3. Optionally co-publish the v2.16 spec (we'd merge any xAI proposal
   into the existing public RFC process).

In return: every install of a Grok Agent OS agent runs **only** Grok
4.3 by default, every manifest validates with `python cli/grok-agent.py
validate`, and every creator on X gets one canonical answer to "how do
I ship an agent on X?" — your platform, your model, with the safety
contract pre-wired.

---

## The gap we're closing

Today an X user who wants to install a Grok-powered agent does one of:

- Copies code from a thread, installs random Python deps, hopes it
  works on Windows (it usually doesn't).
- Asks Grok 4.3 to write the agent inline, then has to figure out
  where to host it, how to feed it secrets, how to surface it on X.
- Gives up and uses a single-vendor agent platform that pulls them
  off the X surface.

There is no schema, no provenance, no consent gate, no mandatory
disclaimers, no path for a non-technical creator to ship an agent
safely. The result: real Grok-quality work doesn't reach real users.

This is a coordination problem. The fix is one open standard plus one
canonical install primitive — the combination of which lives in this
repo today.

---

## What we built (currently shipped)

| Layer | Path | Purpose |
|---|---|---|
| **Open manifest standard** | `spec/v2.15/grok-agent.yaml` | One YAML describes the whole agent (kind, tools, public APIs, multi-agent role, safety, cost limits, HITL gates). 100% backwards-compat with v2.14. |
| **Windows-first CLI** | `cli/grok-agent.ps1` + `cli/grok-agent.py` | PowerShell 5.1+, zero admin, AppData-local install at `$env:LOCALAPPDATA\grok-agent\`. Pydantic v2 validator. |
| **Agent Constitution + scanner** | `safety/constitution.md`, `safety/scanner.py` | Six-rule baseline (consent, provenance, rollback, contradiction, Windows-only, privacy-first). CI-enforced on every push. |
| **34 valid manifests** | `templates/**/grok-agent.yaml` | All 34 currently in the repo pass schema + Constitution scan at the strictest severity floor. |
| **Three flagship Super Agents** | `templates/super-agents/{lnf,sepos,crf}/` | Living Narrative Fabric (synthesis), Self-Evolving Personal OS (personal memory), Cross-Reality Action Fabric (real-world action). All Apache-2.0, all running on Grok 4.3 by default. |
| **22 creator templates** | `templates/creator/*/` | From `content-idea-generator` to `monetization-optimizer` — each a one-folder template with a v2.15 manifest, system prompt, runner, README, and example outputs. |
| **Thin marketplace** | `marketplace/` | Next.js 14 + TypeScript. Search, kind filters, per-agent detail routes, manifest generator. Vercel-deployable in three minutes. |
| **CI workflow** | `.github/workflows/validate.yml` | Validates every manifest on every push: v2.15 schema + Constitution scanner. Hardened in P146 with set -euo pipefail + dependency-import probe + summary line. |

---

## Why this helps Grok win

### 1. It pulls the X user back onto X

Every Grok Agent OS template ships with `real_time_x.enabled` and a
mention/DM trigger declared in the manifest. The `grok install this`
phrase is X-native — a creator types it as a reply, the user clicks,
the agent installs. No off-platform redirect.

### 2. It defaults to Grok 4.3

Every manifest in the repo declares:

```yaml
grok:
  model: "grok-4.3"
  tool_calling: true
```

We never default to a non-Grok model. When a user generates a manifest
through the marketplace's "Deploy to X" form, the resulting YAML lists
Grok 4.3 — by construction.

### 3. It makes the safety story Grok's safety story

The Constitution + scanner enforce six rules at install time:

1. Every action carries a typed user approval.
2. Every executed action writes a provenance record.
3. Every state-changing action carries a verbatim rollback.
4. Contradictions are surfaced, never silently resolved.
5. Windows-only execution paths (no bash leaks).
6. Local-first by default — telemetry and cloud sync are opt-in.

When a third party ships a Grok-powered agent that mishandles a user's
data, the public conversation pulls Grok in by default. With this
standard, "did the agent declare the gate? did the scanner pass?" is
the first question — and the standard's safety record becomes Grok's
safety record by association.

### 4. It's already production-grade

- 34 manifests pass schema + Constitution scan today.
- Three Super Agents have full Promptfoo + DeepEval suites and pass
  weekly self-improvement loops.
- The marketplace generator emits a v2.15-valid manifest for all 8
  declared kinds (verified by the canonical Pydantic validator).
- CI is green on `main`.

We are not asking xAI to invest engineering effort to make this exist.
We are asking xAI to recognise that it already exists and link to it.

---

## What we're asking for

| Ask | Cost to xAI | Benefit to Grok |
|---|---|---|
| **Reference link in Grok docs** to `github.com/AgentMindCloud/grok-agent` as the open agent-distribution standard. | 1 doc PR. | Every developer searching "how to ship a Grok agent" lands on a public, working, Apache-2.0 standard that defaults to Grok 4.3. |
| **One Grok 4.3 system-prompt example** that demonstrates the `grok install this` reply pattern. | One example update. | The X-native install primitive becomes the default UX in user-facing Grok replies. |
| **Optional co-publication of v2.16** via the public RFC process. | Whatever review effort xAI wants to invest. | Long-term governance of the standard is shared, not unilateral. |

We are **not** asking for engineering integration, money, exclusive
licensing, or any change to Grok's roadmap. The standard is built so
xAI can fold it in unilaterally whenever you want; until then, we're
the maintainers and you're the platform.

---

## What happens if xAI declines

Nothing breaks. The repo continues to ship. The marketplace continues
to deploy. The Super Agents continue to default to Grok 4.3.

But:

- A different LLM provider could fork the spec and rename the model
  default.
- A non-X social platform could fork the install primitive and rename
  the reply phrase.
- A different agent platform could absorb the creator templates without
  the Grok defaults intact.

We'd much rather build this for you than watch it drift to a competing
ecosystem. The whole point is that the canonical answer to "how do I
ship a Grok-powered agent on X?" should live inside the X + Grok
sphere.

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Spec drift between v2.15 and a future xAI-blessed version. | Backwards-compatibility is a hard rule (the validator already accepts both v2.14 and v2.15). v2.16 would add fields, never remove them. |
| Quality of community-submitted manifests. | The CI workflow gates every PR with v2.15 schema + Constitution scanner at info severity floor. No PR with a manifest violation merges. |
| Privacy / safety incidents from third-party agents. | The Constitution declares 6 rules + every manifest declares its consent gates explicitly. The scanner blocks installs that don't. The marketplace surfaces every gate on the per-agent detail page. |
| Single-maintainer bus factor. | Apache 2.0 + public repo. Anyone can fork. The marketplace itself is 1080 LOC of TypeScript, the validator is 800 LOC of Python, the scanner is 600 LOC of Python — all readable in an afternoon. |

---

## Next steps

1. **Watch the 60-second demo.** Script + storyboard live at
   [`docs/pitch/60-second-demo-script.md`](./60-second-demo-script.md).
2. **Open an issue or DM** at the GitHub repo or `@JanSol0s` on X. We
   reply within 24 hours.
3. **Try the marketplace.** `cd marketplace && npm install && npm run dev`,
   then open <http://localhost:3030>. Generate a manifest, copy it, run
   `python cli/grok-agent.py validate grok-agent.yaml`.
4. **(Optional)** Open a doc PR linking to the standard from the Grok
   docs. We'll mirror any wording xAI prefers.

---

## Appendix A — current public surface

- **Repo:** <https://github.com/AgentMindCloud/grok-agent>
- **License:** Apache 2.0 (every file)
- **CI:** GitHub Actions, green on `main`, validates every manifest on
  every push.
- **Spec:** `spec/v2.15/grok-agent.yaml` (~150 lines, fully commented,
  100% backwards-compat with v2.14).
- **Validator:** `cli/grok-agent.py validate <path>` — Pydantic v2,
  reports per-field errors with paths.
- **Scanner:** `safety/scanner.py scan <path> --severity-floor info` —
  enforces the six Constitution rules.
- **Marketplace:** `marketplace/` — Next.js 14, deployable to Vercel /
  GitHub Pages / IIS / S3.

## Appendix B — the model default

Every manifest currently in the repo:

```yaml
grok:
  model: "grok-4.3"
  tool_calling: true
```

This is enforced by convention (every template author copies the line
from the previous template) and by the marketplace generator (which
emits the line by construction). It is not enforced by the schema — a
contributor could publish a manifest that defaults to a different
model — but the marketplace's featured-agent catalogue would not list
such a manifest.

If xAI wants `grok` as a required block in v2.16, we can land that in
one PR.

---

> Built to help xAI and Grok win. 🚀
>
> *— `@JanSol0s`, AgentMindCloud, 2026-05-06.*
