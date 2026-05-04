<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🧾 X Money Vision Analyzer

> Drag-and-drop vision-powered receipt and statement analyzer. Parses receipts with Grok 4.3 vision and one-click imports them into the X Money Companion Dashboard's SQLite.
>
> *Built to help xAI and Grok win the platform battle on X.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Disclaimers (non-negotiable, Constitution Article V)

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

These banners appear on every Streamlit tab, on every parsed-receipt card, and as the first row / first page of every export. Required by Constitution Article V.1 (finance) and V.2 (tax — receipts feed tax records, so V.2 is mandatory here, not optional). Auto-checked by `safety/scanner.py` on every install and every PR.

---

## What it is

The **vision tool** of the Grok Agent OS suite. A local-first, Windows-native Streamlit app that:

- Accepts drag-and-drop receipt images (JPG, PNG, HEIC) and multi-page statements (image or PDF)
- Calls **Grok 4.3 vision** to extract structured fields (date, total, currency, counterparty, line items, tax) on every receipt
- Runs an optional **second vision pass** that flags contradictions between the two extractions (Article IV — never silently resolve)
- Lets you **one-click import** parsed receipts into the X Money Companion Dashboard (Tool #1) — and **only** Tool #1, only via the documented `data/import_receipts.py` entry point, only after the user explicitly approves the consent gate

Receipt images stay under `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\receipts\` unless you opt into cloud sync. The vision call itself is the only outbound: Grok 4.3 vision happens on xAI's servers, but no other PII leaves the box. (Constitution Article VII — `pii_handling: "redacted-cloud"` is documented in the manifest.)

---

## Quick Launch (Windows 11)

**TL;DR — one command, opens in your browser:**

```powershell
.\launcher.ps1
```

That's it. The launcher resolves Python 3.12+, installs pinned deps from `requirements.txt` on first run, ensures `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\` exists with an initialised SQLite + a `receipts/` subfolder, then opens `http://localhost:8504` in your default browser. (Port 8504 leaves 8501 free for Tool #1 and 8502 free for Tool #2 — all four X Money tools coexist.) For more control, see the three options below.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install x-money-vision-analyzer
```

The CLI resolves the manifest, validates against `spec/v2.15/grok-agent.yaml`, runs `safety/scanner.py` against the Constitution, and only on a clean pass copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder. If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — manual launch (for dev / contribution)

```powershell
cd templates\finance\x-money-vision-analyzer
.\launcher.ps1
```

The launcher does six things in order: shows the disclaimer banner; resolves Python 3.12+ (`python` then `py -3`); runs `python -m pip install --quiet -r requirements.txt` (skip with `-SkipDeps`); creates `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\` AND the `receipts/` subfolder if missing; calls `data.store.init_db()` to create the SQLite schema (idempotent — safe on every launch); then runs `streamlit run app.py` headless on port 8504 and opens the URL in your default browser (skip with `-NoBrowser`).

Optional flags:

```powershell
.\launcher.ps1 -Port 8765 -SkipDeps -NoBrowser
```

Chrome only, per the manifest's `windows.chrome_only: true`.

### Option C — direct Streamlit (developers only)

```powershell
cd templates\finance\x-money-vision-analyzer
python -m pip install -r requirements.txt
streamlit run app.py
```

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| SQLite database (parse history + import audit) | `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\data.db` |
| Receipt images | `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\receipts\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\logs\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\cache\` |
| Provenance log | `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\provenance.log` (append-only — every consent-gated import + every Grok vision call is recorded) |

These follow Constitution Article VII (local-first, privacy-first) and the repo-wide path convention in `CLAUDE.md` §9.

---

## The 6 tabs (planned)

| Tab | What it does | Disclaimer |
|---|---|---|
| 📥 **Drop Files** | Drag-drop receipts (JPG/PNG/HEIC) and statements (PDF/image) | V.1 |
| 🔍 **Parsed Preview** | Review structured fields Grok extracted from each receipt | V.1 + V.2 (parsed amounts feed tax records) |
| 🔁 **Validate** | Run a second vision pass and flag contradictions between the two extractions | V.1 (reinforced — AI-generated) |
| 📤 **Import to Tool #1** | Send approved batches into the X Money Companion Dashboard's SQLite (consent-gated) | V.1 + V.2 |
| 📜 **History** | Past parses + import status + the provenance log surface | V.1 |
| ⚙️ **Settings** | API key, redaction policy, cloud-sync opt-in (default off) | V.1 |

Tabs land in Slot 2 / P32 (Streamlit skeleton). The 6-tab shape adapts Recipe A's canonical layout for the vision-tool surface; fewer real-time elements than Tool #2, more emphasis on review-before-write.

---

## Cross-tool integration (Tool #4 → Tool #1)

This tool **writes into** the X Money Companion Dashboard (Tool #1) — the only such cross-tool write the Grok Agent OS Constitution permits.

**The contract:**

- The Vision Analyzer parses receipts locally and stores them in its own SQLite first (per-receipt audit trail with the original image path).
- When the user opts to import, `data/import_receipts.py` opens Tool #1's SQLite at `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\data.db` and writes rows into its `transactions` table with `source = 'vision'` and the local `receipt_image_path`.
- The schema is **fixed** in Tool #1's `data/store.py` (already shipped with `receipt_image_path TEXT` column) so Tool #4 can be installed before or after Tool #1 without breaking the round-trip.
- **Every batch passes through the `import_to_companion_dashboard` consent gate** (Constitution Article II). The runtime presents the action plan — N receipts, totals, target file, estimated cost — and the user must explicitly approve. No auto-imports, ever.

**The Constitution rule** baked into this manifest:

> *"Tool #4 writes to Tool #1's SQLite via data/import_receipts.py only. No other cross-tool writes are permitted by this manifest (Article III)."*

If the user installs both tools, drag-drop a receipt → the Vision Analyzer parses → user reviews + approves → it appears as a categorized transaction in Tool #1 within seconds. No sync server, no cloud, no API between the two tools — direct SQLite write across two local agents on the same Windows machine.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `vision-analyzer` — the canonical schema enum value for image-/document-parsing agents. (Your prompt §4 said `finance-dashboard`; both are valid v2.15 kinds and both auto-apply V.1+V.2 disclaimers per Article V, but `vision-analyzer` is the more accurate enum: the v2.15 cross-field validator *requires* `grok.vision: true` for `kind: vision-analyzer`, which is exactly the validator-level enforcement of "this is a vision tool" — and matches the recipe-skill table.)
- **`grok.vision: true`** declared (mandatory for this kind)
- **5 Grok-callable tools**: `parse_receipt`, `parse_statement`, `import_to_companion_dashboard`, `validate_extraction`, `categorize_parsed_receipt`
- **1 declared public API**: `grok_vision` (via Grok 4.3) with `privacy: "image_redacted_on_send"`
- **`pii_handling: "redacted-cloud"`** — Article VII §3 explicitly allows this when the agent's purpose requires an LLM call (vision); redaction approach documented inline on the API entry
- **`provenance` enabled** with `cite_sources: true` and `contradiction_detection: true` (the second vision pass surfaces disagreements honestly)
- **7 Constitution rules** specializing Articles II, III, IV, V, VII for vision use
- **2 consent gates**: `import_to_companion_dashboard`, `sync_to_cloud`
- **Cost limits**: $1.00/session, $5.00/day, **100 API calls/session** (vision calls are bigger than text — fewer per session) — Article VI.1
- **Human-in-the-loop**: enabled, 60s timeout, confirm before cross-tool import / cloud sync / any cost > $0.20 (Article VI.2)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\finance\x-money-vision-analyzer\grok-agent.yaml
python safety\scanner.py scan  templates\finance\x-money-vision-analyzer\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install.

---

## Build slots (Recipe A)

This is **Slot 1 of 6** — manifest + folder + README. The remaining slots populate this folder over P32–P36:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + README | `grok-agent.yaml`, `README.md` | ✅ this prompt (P31) |
| 2 — Streamlit app skeleton (6 tabs) | `app.py`, `requirements.txt` | ✅ P32 |
| 3 — Grok prompts | `prompts/system.md`, `prompts/user_templates.md` | ✅ P33 |
| 4 — Data layer + APIs + `data/import_receipts.py` | `data/__init__.py`, `data/store.py`, `data/api_clients.py`, `data/import_receipts.py` | ✅ P34 |
| 5 — Launcher + Streamlit Cloud config | `launcher.ps1`, `.streamlit/config.toml` | ✅ this prompt (P35) |
| 6 — Smoke test + `grok install this` readiness | `smoke_test.ps1` | ⏭️ P36 |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win. Tool #1 is your X Money command center, Tool #2 is its alpha brain — this analyzer is the front door: every receipt the user drops becomes a categorized transaction in Tool #1 within seconds, with full provenance and never an auto-import.
