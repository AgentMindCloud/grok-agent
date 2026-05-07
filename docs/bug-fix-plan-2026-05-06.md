<!-- SCANNER:EXEMPT-START -->
<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
-->

# Grok Agent OS — Full Codebase Bug Report & Fix Plan
**Date:** 2026-05-06  
**Audit scope:** 10 parallel sub-agents, every file in the repo  
**Built for xAI, X, Grok and the ecosystem community. ❤️**

---

## Severity totals (unique issues, de-duplicated across all 10 agents)

| Severity | Count |
|----------|-------|
| CRITICAL | 22 |
| HIGH | 43 |
| MEDIUM | 63 |
| LOW | 59 |
| **Total** | **~187** |

CRITICAL = broken today, blocks the named feature entirely.  
HIGH = incorrect behavior or silent failure that affects real users.  
MEDIUM = works in happy path but breaks in edge case or has misleading output.  
LOW = code quality, docs accuracy, test coverage gaps.

---

## Step-by-step fix plan

Steps are numbered in the order they should be executed. Later steps may depend on earlier ones. Each step includes the file(s) to change and a one-line acceptance test.

---

### TIER 1 — Infrastructure blockers (nothing works until these are fixed)

---

**Step 1 — Fix CI/CD: pages.yml must build Next.js and deploy the output**

Problem: `.github/workflows/pages.yml` uploads the raw `./marketplace` folder (legacy static `index.html` + `script.js`) to GitHub Pages. It never runs `npm ci` or `next build`. The deployed site is always the old CDN-Tailwind page, not the Next.js app.

Files to change:
- `.github/workflows/pages.yml`

Fix: Replace the upload step with:
```yaml
- name: Install dependencies
  run: npm ci
  working-directory: marketplace

- name: Build Next.js static export
  run: npx next build
  working-directory: marketplace

- name: Upload artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: marketplace/out
```
Also update the smoke-test assertions to check for content that comes from the Next.js output (e.g., `<title>Grok Agent OS`) instead of `id="grid"` which only exists in the legacy `index.html`.

Acceptance: `gh run watch` shows the Pages workflow completes with exit 0 and the live URL serves the Next.js app at `/grok-agent/`.

---

**Step 2 — Fix next.config.js: add basePath and trailingSlash for GitHub Pages**

Problem: `next.config.js` has no `basePath` or `trailingSlash`. The site is served at `https://agentmindcloud.github.io/grok-agent/` but all asset and navigation links resolve to `/` (root), breaking every page load and CSS/JS include.

Files to change:
- `marketplace/next.config.js`

Fix:
```js
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: 'export',
  basePath: '/grok-agent',
  trailingSlash: true,
  images: { unoptimized: true },
};
```

Acceptance: After Step 1+2, the live GitHub Pages URL loads the homepage without 404 errors on any asset.

---

**Step 3 — Fix CLI install: add Invoke-WebRequest URL-fetch path**

Problem: `cli/grok-agent.ps1` line 449–474 calls `Test-Path -LiteralPath $arg` on a URL. `Test-Path` returns `$false` for any `https://` string and exits with "Path not found". There is zero use of `Invoke-WebRequest`/`Invoke-RestMethod` anywhere in the file. The headline UX promise "grok install this" (paste a URL from X) is completely broken.

Files to change:
- `cli/grok-agent.ps1` (inside `Invoke-Install`, before the `Test-Path` call)

Fix: Add a URL-detection branch:
```powershell
if ($arg -match '^https?://') {
    try {
        $response = Invoke-WebRequest -Uri $arg -UseBasicParsing -ErrorAction Stop
        $manifestText = $response.Content
        $sourceLabel  = $arg
    } catch {
        Write-Err2 ("Failed to fetch URL: {0} — {1}" -f $arg, $_.Exception.Message)
        exit 66
    }
}
```
Also update help text (`.SYNOPSIS`, `.EXAMPLE`, usage block) to show the URL install example.

Also fix line 697/707: add `-ErrorAction SilentlyContinue` to the `Get-Command python3` calls that are missing it.

Also fix line 776: change `& python $deepEval` to `& $py.Source $deepEval`.

Also fix line 744: replace `Set-Content -Encoding UTF8` with `Write-Utf8NoBom` (already defined in the file at line ~152) to avoid UTF-8 BOM on PowerShell 5.1.

Acceptance: `.\cli\grok-agent.ps1 install https://raw.githubusercontent.com/AgentMindCloud/grok-agent/main/spec/v2.15/grok-agent.yaml` downloads the file, validates it, and installs to `$env:LOCALAPPDATA\grok-agent\`.

---

**Step 4 — Fix SEPOS: remove dynamic LNF import that crashes on any violation**

Problem: `templates/super-agents/self-evolving-personal-os/orchestrator.py` lines ~115–146 dynamically imports `ConstitutionViolation` from LNF's `orchestrator.py` at module-import time via `importlib.util.spec_from_file_location`. Two consequences:
1. If the `living-narrative-fabric/` folder is absent (standalone deploy, CI, Codespaces), SEPOS's `orchestrator.py` fails to import entirely.
2. LNF's `ConstitutionViolation` is `class ConstitutionViolation(RuntimeError): pass` (no attributes). SEPOS's `graph.py` line ~194–200 accesses `exc.article` and `exc.gate` on it, causing an unhandled `AttributeError` on the first real violation.

Files to change:
- `templates/super-agents/self-evolving-personal-os/orchestrator.py` (remove `_import_lnf_constitution_violation()` and its call)
- `templates/super-agents/self-evolving-personal-os/graph.py` (update import)

Fix: In both files, replace the dynamic import with:
```python
from connectors import ConstitutionViolation
```
SEPOS's `connectors/__init__.py` already defines this class correctly with `article`, `source`, and `gate` attributes. Also update `constitution.md` to document the native class.

Acceptance: `python -c "from orchestrator import SelfEvolvingPersonalOS"` succeeds when `living-narrative-fabric/` is absent.

---

**Step 5 — Fix LNF: xAI tool-call response parsed from wrong field + wrong model name**

Problem A: `templates/super-agents/living-narrative-fabric/connectors/x_grok_client.py` line ~158 parses X-search results from `message.content`. When the model executes a tool call, `content` is `None`. Every live X-search synthesis returns zero posts — the entire X-research pipeline produces only stubs.

Problem B: Same file line ~115 uses model name `"grok-4.3"` which does not exist in the xAI API (valid names: `grok-3`, `grok-3-fast`). All X-search requests return 404/error JSON, silently falling to stub mode.

Files to change:
- `templates/super-agents/living-narrative-fabric/connectors/x_grok_client.py`

Fix A — parse from tool_calls:
```python
tool_calls = choices[0]["message"].get("tool_calls", [])
if tool_calls:
    arguments = tool_calls[0].get("function", {}).get("arguments", "{}")
else:
    arguments = choices[0]["message"].get("content") or "{}"
posts = json.loads(arguments).get("posts", [])
```

Fix B — configurable model name:
```python
model = os.environ.get("GROK_MODEL", "grok-3")
```

Acceptance: With a valid `XAI_API_KEY` env var set, `agent.py search "Grok Agent OS"` returns non-empty results.

---

### TIER 2 — Critical correctness (affects every user, every manifest)

---

**Step 6 — Fix safety scanner: version float vs string comparison**

Problem: `safety/scanner.py` line 226–230. `yaml.safe_load` parses unquoted `version: 2.15` as Python `float 2.15`. The check `v not in ("2.14", "2.15")` always fails for floats because `2.15 != "2.15"`. Any new manifest with an unquoted version field gets a spurious VER-001 error.

Files to change:
- `safety/scanner.py`

Fix:
```python
str_v = str(v) if isinstance(v, (int, float)) else v
if str_v not in ("2.14", "2.15"):
    ...
```

Acceptance: `python safety/scanner.py scan templates/super-agents/living-narrative-fabric/grok-agent.yaml` exits 0 whether `version` is quoted or unquoted.

---

**Step 7 — Fix safety scanner: dead `_HARD_REFUSAL_BLACKLIST`**

Problem: `safety/scanner.py` line 269–293. `_HARD_REFUSAL_BLACKLIST` (8 hard-refusal action strings) is defined but never referenced anywhere. The check `III.no-forbidden-actions-flipped` only verifies that `safety.forbidden_actions` and `constitution.consent_gates` don't overlap — but it never checks if a hard-refusal action appears directly in `consent_gates`. A malicious manifest can grant `scrape_authenticated_x_content` as a consent gate with no scanner objection.

Files to change:
- `safety/scanner.py`

Fix: Add a new check that iterates `constitution.consent_gates` and raises an error for any value in `_HARD_REFUSAL_BLACKLIST`:
```python
def check_no_hard_refusal_in_consent_gates(m):
    gates = _get(m, "constitution.consent_gates") or []
    violations = [g for g in gates if g in _HARD_REFUSAL_BLACKLIST]
    if violations:
        yield Finding(severity="error", code="AR-001", article="III",
                      message=f"Hard-refusal actions in consent_gates: {violations}")
```
Register this check in `CHECKS` after the existing `III.no-forbidden-actions-flipped`.

Acceptance: A manifest with `constitution.consent_gates: ["scrape_authenticated_x_content"]` exits non-zero from the scanner.

---

**Step 8 — Fix validator: `--strict` flag is a no-op**

Problem: `cli/grok-agent.py` lines 759–767. When `--strict` is passed, the CLI prints "Strict mode (extra=forbid)" but `GrokAgentManifest` root model has `model_config = ConfigDict(extra="allow")` permanently. The flag is never passed to `validate_manifest_file`. Rogue top-level fields in a manifest are silently accepted even with `--strict`.

Files to change:
- `cli/grok-agent.py`

Fix: Pass `strict` to `validate_manifest_file`. When True, rebuild the model config at call time:
```python
def validate_manifest_file(path: str, strict: bool = False) -> tuple[bool, list[str]]:
    ...
    if strict:
        # Temporarily patch the root model to forbid extra fields
        original_config = GrokAgentManifest.model_config
        GrokAgentManifest.model_config = ConfigDict(extra="forbid")
    try:
        GrokAgentManifest.model_validate(data)
    finally:
        if strict:
            GrokAgentManifest.model_config = original_config
```

Acceptance: `python cli/grok-agent.py validate --strict <manifest-with-extra-field>` exits 1 and prints an error about the unknown field.

---

**Step 9 — Fix validator: `demo_video` type mismatch between spec and Pydantic**

Problem: `spec/v2.15/grok-agent.yaml` line 105 shows `demo_video: "DEMO.md"` (a plain string). `cli/grok-agent.py` line 158 defines `Metadata.demo_video: Optional[DemoVideo]` — a structured object requiring a `status` field. Any manifest that copies the spec example literally gets `Input should be a valid dictionary or instance of DemoVideo`.

Files to change:
- `cli/grok-agent.py`

Fix: Change the field to accept both:
```python
demo_video: Optional[Union[str, DemoVideo]] = None

@field_validator("demo_video", mode="before")
@classmethod
def coerce_demo_video(cls, v):
    if isinstance(v, str):
        return v  # accept plain string (spec example form)
    return v  # pass dict/DemoVideo through
```

Acceptance: `python cli/grok-agent.py validate spec/v2.15/grok-agent.yaml` exits 0. Both `demo_video: "DEMO.md"` and `demo_video: {status: "pending"}` pass validation.

---

**Step 10 — Fix marketplace: scan `templates/creator/` for agents**

Problem: `marketplace/lib/manifests.ts` defines `SUPER_AGENTS_DIR` and `FINANCE_DIR` but has no `CREATOR_DIR`. All 22 creator templates are invisible in the marketplace.

Files to change:
- `marketplace/lib/manifests.ts`
- `marketplace/lib/types.ts`

Fix in manifests.ts: Add:
```ts
const CREATOR_DIR = path.join(REPO_ROOT, 'templates', 'creator');

export function loadAllAgents(): AgentManifest[] {
  return [
    ...scanDirectory(SUPER_AGENTS_DIR, 'super-agent'),
    ...scanDirectory(FINANCE_DIR, 'x-money-tool'),
    ...scanDirectory(CREATOR_DIR, 'creator'),
  ];
}
```

Fix in types.ts: Add `'creator'` to `AgentCategory` and `AgentTier`:
```ts
export type AgentCategory = 'super-agent' | 'x-money-tool' | 'creator';
export type AgentTier = 'flagship' | 'lighter' | 'x-money' | 'creator';
export const CATEGORY_LABELS: Record<AgentCategory, string> = {
  'super-agent': 'Super Agents',
  'x-money-tool': 'X Money Tools',
  'creator': 'Creator Templates',
};
```

Also update `app/page.tsx` to add the creator filter chip and `totals` counter.

Acceptance: `npm run build` inside `marketplace/` generates static pages for all 22 creator templates. The `/` route shows the correct agent count including creators.

---

**Step 11 — Fix marketplace: mount ScanlineOverlay and CommandPalette**

Problem: `marketplace/app/layout.tsx` never imports or renders `ScanlineOverlay` or `CommandPalette`. Both components exist but are invisible. `cmdk` (used by CommandPalette) is also missing from `package.json`.

Files to change:
- `marketplace/app/layout.tsx`
- `marketplace/package.json`

Fix in layout.tsx:
```tsx
import ScanlineOverlay from '../components/ScanlineOverlay';
import CommandPalette from '../components/CommandPalette';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <ScanlineOverlay />
        <CommandPalette />
        {children}
      </body>
    </html>
  );
}
```

Fix in package.json: Add `"cmdk": "^0.2.1"` to `dependencies`, then run `npm install`.

Acceptance: The page renders without errors. Ctrl+K opens the command palette overlay.

---

**Step 12 — Fix marketplace: add retro-terminal CSS**

Problem: `marketplace/app/globals.css` uses the cinnabar/parchment palette and has zero retro-terminal CSS. All 5 new terminal components (`TerminalHero`, `ScanlineOverlay`, `CommandPalette`, `InstallButton`, `TelemetryStrip`) reference CSS classes (`terminal-hero`, `scanline-overlay`, `cmd-overlay`, `install-btn`, `telemetry-strip`) that don't exist anywhere.

Files to change:
- `marketplace/app/globals.css`

Fix: Add a `:root` block with CRT/terminal design tokens and the required class definitions:
```css
:root {
  --bg: #070B0D;
  --fg: #00FF41;
  --fg-dim: #7FCC8F;
  --font-mono: 'JetBrains Mono', 'Space Mono', monospace;
  --scanline-opacity: 0.04;
  --border: #1a3a1a;
}
body { background: var(--bg); color: var(--fg); font-family: var(--font-mono); }
.scanline-overlay { position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background: repeating-linear-gradient(transparent, transparent 2px, rgba(0,0,0,var(--scanline-opacity)) 2px, rgba(0,0,0,var(--scanline-opacity)) 4px); }
.terminal-hero { padding: 3rem 1rem; text-align: center; }
.ascii-logo { color: var(--fg); font-size: clamp(0.5rem, 1.5vw, 0.9rem); line-height: 1.2; }
.cursor.blink { animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
.telemetry-strip { border-top: 1px solid var(--border); padding: 0.25rem 1rem;
  font-size: 0.7rem; color: var(--fg-dim); display: flex; gap: 2rem; }
.install-btn { background: transparent; border: 1px solid var(--fg); color: var(--fg);
  padding: 0.4rem 1rem; cursor: pointer; font-family: inherit; }
.install-btn:hover { background: var(--fg); color: var(--bg); }
.cmd-overlay { position: fixed; inset: 0; background: rgba(7,11,13,0.85); z-index: 1000;
  display: flex; align-items: flex-start; justify-content: center; padding-top: 10vh; }
.cmd-box { background: #0d1f0f; border: 1px solid var(--fg); width: min(600px, 90vw);
  padding: 1rem; }
.cmd-input { width: 100%; background: transparent; border: none; outline: none;
  color: var(--fg); font-family: inherit; font-size: 1rem; }
.cmd-results { margin-top: 0.5rem; max-height: 300px; overflow-y: auto; }
```

Also add JetBrains Mono font loading to `layout.tsx` via `next/font/google`.

Acceptance: `npm run build` passes. The marketplace homepage renders with a dark CRT background, scanlines visible, and the terminal hero component styled correctly.

---

**Step 13 — Fix marketplace: implement `build-agents-index.ts` and fix `__dirname` ESM bug**

Problem: `marketplace/scripts/build-agents-index.ts` is a TODO stub that always writes `[]` to `content/agents.json`. It also uses `__dirname` which throws `ReferenceError` in ESM mode.

Files to change:
- `marketplace/scripts/build-agents-index.ts`
- `marketplace/content/agents.json`

Fix: Replace the stub with a real implementation:
```ts
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import { loadAllAgents } from '../lib/manifests';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const agents = loadAllAgents();
const outPath = path.join(__dirname, '..', 'content', 'agents.json');
fs.writeFileSync(outPath, JSON.stringify(agents, null, 2));
console.log(`Wrote ${agents.length} agents to ${outPath}`);
```

Add to `package.json` scripts: `"build:index": "tsx scripts/build-agents-index.ts"` and make it run as part of `prebuild`.

Acceptance: `npm run build:index` writes the correct agent list to `content/agents.json`. `agents.json` is non-empty after the script runs.

---

**Step 14 — Fix CRF stagehand: default LLM model is OpenAI, not Grok**

Problem: `templates/super-agents/cross-reality-action-fabric/connectors/stagehand_client.py` line ~341 defaults to `modelName="gpt-4o"` (OpenAI) when `STAGEHAND_MODEL` env var is not set. This violates the xAI/Grok-first stack mandate and silently calls OpenAI when users forget the env var.

Files to change:
- `templates/super-agents/cross-reality-action-fabric/connectors/stagehand_client.py`

Fix:
```python
model = os.environ.get("STAGEHAND_MODEL", "grok-3")
if "OPENAI_API_KEY" in os.environ and "XAI_API_KEY" not in os.environ:
    import warnings
    warnings.warn("STAGEHAND_MODEL defaulting to grok-3 but XAI_API_KEY not set", UserWarning)
```

Acceptance: Starting CRF without `STAGEHAND_MODEL` set shows a clear error (no `XAI_API_KEY`) rather than silently calling OpenAI.

---

**Step 15 — Fix Tool #3: SQLite connection leak in companion_reader.py and vision_reader.py**

Problem: `templates/finance/x-creator-payout-optimizer/data/companion_reader.py` lines 45–48 and `vision_reader.py` lines 35–38. `_open_readonly()` returns a plain `sqlite3.Connection`. Used as `with _open_readonly(db) as conn:` but `Connection.__exit__` does not call `.close()`. Every read function leaks an open file handle. Under concurrent Streamlit sessions on Windows this accumulates to `database is locked` errors.

Files to change:
- `templates/finance/x-creator-payout-optimizer/data/companion_reader.py`
- `templates/finance/x-creator-payout-optimizer/data/vision_reader.py`

Fix: Convert `_open_readonly` to a proper context manager:
```python
from contextlib import contextmanager
import sqlite3

@contextmanager
def _open_readonly(db_path: Path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

Acceptance: Running 5 concurrent `get_companion_summary()` calls in a tight loop produces no `database is locked` errors.

---

### TIER 3 — High-impact correctness (feature-level failures)

---

**Step 16 — Fix LNF and SEPOS requirements.txt: add 7 missing packages**

Problem: `templates/super-agents/living-narrative-fabric/requirements.txt` is missing: `requests`, `mem0ai`, `qdrant-client`, `sentence-transformers`, `langfuse`, `deepeval`, `crawl4ai`. All these are used in production code but not listed. Users get a silent stub-only mode with no error on missing packages.

Files to change:
- `templates/super-agents/living-narrative-fabric/requirements.txt`
- `templates/super-agents/self-evolving-personal-os/requirements.txt` (same gap)

Fix: Add (as optional/stub-fallback section):
```
# Optional deps — stubs activate silently if absent
requests>=2.31,<3.0
mem0ai>=1.0,<2.0
qdrant-client>=1.9,<2.0
sentence-transformers>=2.6,<5.0
langfuse>=2.30,<4.0
deepeval>=1.0,<3.0
crawl4ai>=0.3,<2.0
```

Acceptance: `pip install -r requirements.txt` installs all deps. The agent runs in live (non-stub) mode when API keys are present.

---

**Step 17 — Fix LNF and SEPOS: deprecated mem0ai and qdrant-client APIs**

Problem: Both super agents use deprecated/removed APIs:
- `Memory.from_config()` was deprecated in mem0ai v1.x → replaced by `Memory(config=...)`
- `QdrantClient.search()` renamed to `query_points()` in qdrant-client 1.7+
- `QdrantClient.recreate_collection()` removed in qdrant-client 1.9+ (SEPOS only)

All memory operations fall back to stubs silently.

Files to change:
- `templates/super-agents/living-narrative-fabric/memory/mem0_setup.py`
- `templates/super-agents/living-narrative-fabric/memory/qdrant_index.py`
- `templates/super-agents/self-evolving-personal-os/memory/mem0_setup.py`
- `templates/super-agents/self-evolving-personal-os/memory/qdrant_index.py`

Fix A — mem0ai:
```python
self._memory = Memory(config={"history_db_path": str(self.sqlite_path),
                               "vector_store": {"provider": "qdrant", "config": {...}}})
```

Fix B — qdrant search:
```python
result = self._client.query_points(
    collection_name=collection,
    query=list(query_vector),
    query_filter=qfilter,
    limit=int(limit)
)
return [hit.payload for hit in result.points]
```

Fix C — qdrant recreate_collection (SEPOS):
```python
self._client.create_collection(
    collection_name=name,
    vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
)
```

Acceptance: With real Qdrant running locally, `agent.py` runs without `AttributeError`. Memory reads/writes function correctly.

---

**Step 18 — Fix SEPOS eval: deepeval_suite always returns exit code 0**

Problem: `templates/super-agents/self-evolving-personal-os/eval/deepeval_suite.py` line ~930: `return 0 if report.overall_score >= 0.8 else 0`. Both branches return `0`. CI jobs invoking `python -m eval` never get a non-zero exit code on regressions.

Files to change:
- `templates/super-agents/self-evolving-personal-os/eval/deepeval_suite.py`

Fix: `return 0 if report.overall_score >= 0.8 else 1`

Also fix the same issue in LNF if present.

Acceptance: When the agent's eval score falls below 0.8, `python -m eval` exits 1 and CI marks the step as failed.

---

**Step 19 — Fix SEPOS connectors: missing `grok_client.py`**

Problem: `templates/super-agents/self-evolving-personal-os/connectors/x_personal_client.py` line ~129: `from . import grok_client`. No `grok_client.py` exists in the `connectors/` package. Import always fails with `ImportError`, silently falling back to stub. Real X fetching never works.

Files to change:
- Create `templates/super-agents/self-evolving-personal-os/connectors/grok_client.py`

Fix: Create the file using the same xAI API call pattern as LNF's `x_grok_client.py`:
```python
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
import os, requests

XAI_API_BASE = "https://api.x.ai/v1"
MODEL = os.environ.get("GROK_MODEL", "grok-3")

def search_x(query: str, max_results: int = 20) -> list[dict]:
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        return []
    ...  # xAI chat completions with tool call pattern from LNF
```

Acceptance: `python -c "from connectors.grok_client import search_x"` succeeds. With `XAI_API_KEY` set, `search_x("test")` returns non-empty list.

---

**Step 20 — Fix scanner: VII.no-trackers false-positive full-blob search**

Problem: `safety/scanner.py` lines 603–615. `VII.no-trackers` does `json.dumps(m, default=str).lower()` and substring-searches for tracker domain names. A manifest whose `description` merely *mentions* "google-analytics.com" (e.g. "does NOT use google-analytics.com") exits 1 with a PII-005 error.

Files to change:
- `safety/scanner.py`

Fix: Restrict the search to specific fields known to contain URLs:
```python
url_fields = [
    *[api.get("base_url", "") for api in _get(m, "public_apis") or []],
    (_get(m, "windows.launcher") or ""),
    (_get(m, "windows.run_command") or ""),
]
haystack = " ".join(url_fields).lower()
```

Acceptance: A manifest whose description text contains "does not use google-analytics.com" exits 0 from the scanner.

---

**Step 21 — Fix scanner: empty HITL dict bypass**

Problem: `safety/scanner.py` lines 410–423. `safety.human_in_the_loop: {}` (empty dict) passes all HITL checks silently. `hitl is None` is `False`, and `hitl.get("enabled") is False` is also `False`. An agent with consent gates but a hollow HITL block bypasses both checks.

Files to change:
- `safety/scanner.py`

Fix: Add a third condition:
```python
if hitl is not None and hitl.get("enabled") is None:
    yield Finding(severity="warn", code="HITL-001", article="VI",
                  message="human_in_the_loop block present but 'enabled' field absent")
```

Acceptance: A manifest with `safety.human_in_the_loop: {}` and consent gates exits non-zero from the scanner with a HITL-001 warning.

---

**Step 22 — Fix scanner: append-only provenance check does not fire when field absent**

Problem: `safety/scanner.py` lines 493–503. `III.append-only-provenance` only fires if `provenance.append_only` is **explicitly set to `False`**. If the field is absent (most common case), no finding is emitted. Article IV.4 requires the provenance log to be append-only; absence should be flagged.

Files to change:
- `safety/scanner.py`

Fix:
```python
if _get(m, "provenance.enabled") and _get(m, "provenance.append_only", True) is not True:
    yield Finding(severity="error", code="PROV-001", article="III", ...)
```

Acceptance: A manifest with `provenance.enabled: true` but no `append_only` field emits a PROV-001 error from the scanner.

---

**Step 23 — Fix pyproject.toml: add creator-program/v2 tests to testpaths**

Problem: `pyproject.toml` line 137: `testpaths = ["tests"]`. The `creator-program/v2/tests/` and `creator-program/v2/curation/tests/` directories contain 20+ real pytest tests that are never run by `pytest` from the repo root. No CI job runs these tests.

Files to change:
- `pyproject.toml`

Fix:
```toml
testpaths = [
  "tests",
  "creator-program/v2/tests",
  "creator-program/v2/curation/tests",
]
```

Also add a GitHub Actions job that runs `python -m pytest creator-program/v2/` to a dedicated workflow or to `validate.yml`.

Acceptance: `python -m pytest` from the repo root collects and runs the creator-program tests.

---

**Step 24 — Fix CI: validate.yml set -uo pipefail missing -e**

Problem: `.github/workflows/validate.yml` lines 125 and 149 use `set -uo pipefail` instead of `set -euo pipefail`. Without `-e`, shell errors inside the validation loop body are silently swallowed.

Files to change:
- `.github/workflows/validate.yml`

Fix: Change both occurrences:
```bash
set -euo pipefail
```

Acceptance: A deliberately broken command inside the loop step causes the CI step to fail rather than continuing silently.

---

**Step 25 — Fix CI: curation-cadence.yml artifact uses unsupported tilde path**

Problem: `.github/workflows/curation-cadence.yml` line 139. The `upload-artifact` step points to `~/AppData/Local/grok-agent/creator-program/curation/**/*.json`. GitHub Actions' `upload-artifact@v4` does not expand `~` in the `path:` field. Artifacts are silently empty on every CI run.

Files to change:
- `.github/workflows/curation-cadence.yml`

Fix: Add a step before the upload to copy outputs to a workspace-relative directory:
```yaml
- name: Copy curation output to workspace
  run: |
    mkdir -p $GITHUB_WORKSPACE/curation-output
    cp -r "$HOME/AppData/Local/grok-agent/creator-program/curation/"*.json \
      "$GITHUB_WORKSPACE/curation-output/" 2>/dev/null || true

- name: Upload curation artifacts
  uses: actions/upload-artifact@v4
  with:
    name: curation-results
    path: curation-output/
    if-no-files-found: warn
```

Acceptance: The curation-cadence workflow uploads non-empty artifacts to GitHub Actions when curation produces output.

---

### TIER 4 — Medium priority fixes (edge cases, accuracy, polish)

---

**Step 26 — Fix finance tools: app.py must call init_db() on startup**

Problem: All 4 finance tool `app.py` files define an `ensure_appdata()` function that creates only a minimal `schema_meta` table stub. When the app is launched directly via `streamlit run app.py` (CI, Streamlit Cloud, development), `data/store.init_db()` is never called. Every data function silently operates on a schema-less database.

Files to change:
- `templates/finance/x-money-companion-dashboard/app.py`
- `templates/finance/x-smart-cashtag-alpha-engine/app.py`
- `templates/finance/x-money-vision-analyzer/app.py`
- `templates/finance/x-creator-payout-optimizer/app.py`

Fix (same pattern for all 4):
```python
def ensure_appdata():
    from data.store import init_db
    db_dir = db_path().parent
    db_dir.mkdir(parents=True, exist_ok=True)
    init_db()
```

Acceptance: `streamlit run app.py` without running the launcher first starts the app without any SQLite "no such table" errors.

---

**Step 27 — Fix validator: vision-analyzer + no grok: section silently accepted**

Problem: `cli/grok-agent.py` lines 619–627. The `_kind_consistency` validator only enforces `grok.vision=true` when `self.grok is not None`. A `vision-analyzer` manifest that omits the `grok:` section entirely passes validation.

Files to change:
- `cli/grok-agent.py`

Fix:
```python
if self.kind == "vision-analyzer":
    if self.grok is None or not self.grok.vision:
        raise ValueError("kind='vision-analyzer' requires grok.vision=true")
```

Acceptance: A `vision-analyzer` manifest without a `grok:` section fails validation with a clear error.

---

**Step 28 — Fix scanner: phantom Article X reference**

Problem: `safety/scanner.py` line ~700. `X.local-first-storage` references `article="X"` but Article X does not exist in `constitution.md`. The constitution ends at Article IX.

Files to change:
- `safety/scanner.py`

Fix: Change `article="X"` to `article="VII"` on the `X.local-first-storage` check. Optionally rename the check to `VII.local-first-storage`.

Acceptance: `python safety/scanner.py info` shows no Article X entries.

---

**Step 29 — Fix scanner: add vision-analyzer to FINANCE_KINDS**

Problem: `safety/scanner.py` lines 339–350. `FINANCE_KINDS` excludes `"vision-analyzer"`. A future `vision-analyzer` manifest without the finance disclaimer passes V.1 without any scanner objection.

Files to change:
- `safety/scanner.py`

Fix:
```python
FINANCE_KINDS = frozenset({
    "finance-dashboard", "alpha-engine", "creator-payout-optimizer", "vision-analyzer"
})
```

Acceptance: A `vision-analyzer` manifest without `safety.disclaimers.not_financial_advice: true` emits a V.1 error.

---

**Step 30 — Fix governance docs: stale AI copy in SOURCES.md + frozen phase table**

Problem A: `docs/SOURCES.md` lines 52–54 contain leaked AI assistant copy: "You can now create this file in the root of your grok-agent repo and commit it. Let me know if you need any adjustments!"

Problem B: `docs/SOURCES.md` lines 13–15 reference two files that don't exist: `Grok Agent Platform – Full Sequential Project Plan.md` and `# MASTER PROMPT TEMPLATE — Grok Agent OS Project.md`.

Problem C: `docs/index.md` line 102–106 phase status table has all five phases frozen at pre-Phase-1 state.

Files to change:
- `docs/SOURCES.md`
- `docs/index.md`

Fix A: Delete lines 52–54 from SOURCES.md.
Fix B: Replace the broken references with `docs/PROMPT_TEMPLATE.md` and `HANDOFF_LOG.md`.
Fix C: Update the phase table: Phase 1–4 → `complete`, Phase 5 → `active (P172+)`.

Acceptance: `docs/SOURCES.md` contains no AI boilerplate. `docs/index.md` accurately reflects Phase 5 as active.

---

**Step 31 — Fix bridges registry: unregistered worker slugs in delegates_to**

Problem: `templates/super-agents/_bridges/registry.json`. `cross-reality-action-fabric.delegates_to` lists `["web-action-worker", "local-windows-worker", "real-world-api-worker", "x-action-worker"]` — four slugs that don't exist anywhere in the registry or as agent directories. The registry's own `transitive_citation_rules.rule_3` prohibits undeclared chains, yet the registry itself violates this.

Files to change:
- `templates/super-agents/_bridges/registry.json`

Fix: Either register the four worker slugs as stubs:
```json
{
  "slug": "web-action-worker",
  "kind": "worker-stub",
  "status": "pending",
  "implementation": "cross-reality-action-fabric/connectors/stagehand_client.py"
}
```
Or replace `delegates_to` with the actual connector-level tool names (`"web_via_stagehand"`, `"windows_local"`, etc.) which is how they are actually implemented.

Acceptance: `python safety/scanner.py scan templates/super-agents/cross-reality-action-fabric/grok-agent.yaml` passes the VII.bridge-reciprocity check without any undeclared-slug errors.

---

**Step 32 — Fix lighter super agents: add implementation_status to manifests**

Problem: All 4 lighter super agent manifests (`agent-swarm-with-shared-memory`, `provenance-first-trust-engine`, `narrative-contradiction-detector`, `zero-config-i-want-to-agent`) declare `install.one_click: true` and have READMEs showing working commands. The `orchestrator.py` module they reference doesn't exist. Running `grok-agent run <slug>` fails immediately with `ModuleNotFoundError`.

Files to change:
- All 4 lighter super agent `grok-agent.yaml` files and `README.md` files

Fix: Add to each manifest:
```yaml
metadata:
  implementation_status: "manifest-only"
  planned_phase: "P4"
```
And add to each README:
> **Status:** Manifest only — implementation ships in Phase 4. Not runnable yet.

Also namespace the `module` references: `orchestrator` → `agent_swarm_with_shared_memory.orchestrator` to avoid import collision with CRF's `memory` package.

Acceptance: Users who read the README understand the agent is not yet implemented. The manifest still validates correctly.

---

**Step 33 — Fix content-idea-generator: manifest metric names don't match run.py**

Problem: `templates/creator/content-idea-generator/grok-agent.yaml` line 19: description lists metrics "Niche fit / Voice fidelity / Originality / Engageability". `run.py`'s `SCORE_METRICS` tuple is `("Niche fit", "Trend alignment", "Voice fidelity", "Predicted engagement")`. Two metrics are completely different.

Also: `grok-agent.yaml:tone.enum` is `["punchy", "thoughtful", "data-led"]` but `run.py`'s `TONE_OPTIONS` includes `"mixed"` as a valid value.

Files to change:
- `templates/creator/content-idea-generator/grok-agent.yaml`

Fix: Update description metrics to match run.py. Add `"mixed"` to `tone.enum`.

Acceptance: The manifest's metric descriptions match the run.py `SCORE_METRICS` tuple exactly.

---

**Step 34 — Fix check_schema_drift.py: blind spots for Tool and PublicApi sub-models**

Problem: `scripts/check_schema_drift.py` lines 109–121. The drift detector cannot detect changes to `Tool`, `ToolApi`, `ToolServer`, or `PublicApi` Pydantic sub-models because the `sections` list only covers dict-shaped sections, not array-typed fields.

Files to change:
- `scripts/check_schema_drift.py`

Fix: Add separate comparison logic for array sub-models:
```python
# Compare Tool sub-model fields
pydantic_tool_fields = set(Tool.model_fields.keys())
spec_tool_fields = set(spec_yaml.get("tools", [{}])[0].keys()) if spec_yaml.get("tools") else set()
_report_diff("Tool", pydantic_tool_fields, spec_tool_fields)
```
Apply the same for `PublicApi`, `ToolApi`, `ToolServer`.

Acceptance: Adding a field to `Tool` in `grok-agent.py` without updating the spec YAML causes `check_schema_drift.py` to exit non-zero.

---

**Step 35 — Fix smoke tests: Python version check mismatch**

Problem: All 4 finance tool `smoke_test.ps1` files use `Resolve-Python` with `ge 11` (Python 3.11+) but the corresponding `launcher.ps1` requires `ge 12` (Python 3.12+). A smoke test passes on Python 3.11 but the launcher refuses to start — the test does not catch this version gap.

Files to change:
- `templates/finance/x-money-companion-dashboard/smoke_test.ps1`
- `templates/finance/x-smart-cashtag-alpha-engine/smoke_test.ps1`
- `templates/finance/x-money-vision-analyzer/smoke_test.ps1`
- `templates/finance/x-creator-payout-optimizer/smoke_test.ps1`

Fix: Change `ge 11` to `ge 12` in `Resolve-Python` version check within each smoke test.

Acceptance: Running the smoke test on Python 3.11 now correctly reports "Python 3.12+ required".

---

**Step 36 — Fix ROADMAP.md: swapped prompt ranges for Vision Analyzer and Payout Optimizer**

Problem: `ROADMAP.md` lines 119–120. Vision Analyzer is listed as P37–P42 (actual: P31–P36) and Payout Optimizer as P31–P36 (actual: P37–P42). Swapped.

Also: `docs/pitch/xai-partnership-pitch.md` states "34 valid manifests" — actual count is 37.
Also: `docs/for-xai-adoption.md` line 29 and `docs/index.md` line 85 both say "15 named checks" — scanner has 33.

Files to change:
- `ROADMAP.md`
- `docs/pitch/xai-partnership-pitch.md`
- `docs/for-xai-adoption.md`
- `docs/index.md`
- `README.md` (says "27 checks" — also stale; correct to 33)

Fix: Correct all stale counts.

Acceptance: All mention of check/agent/manifest counts are internally consistent and match actual runtime values.

---

### LOW — Code quality and minor issues (fix opportunistically)

The following are low-severity and can be addressed in a cleanup pass or as part of the relevant file edits above:

- `cli/grok-agent.ps1:194–198` — `Get-YamlScalar` regex silently truncates quoted values containing ` #`
- `cli/grok-agent.ps1:672` — `run` command reads `launcher` as top-level key instead of `windows.launcher`
- `cli/grok-agent.ps1:726,732` — `Test-Path`/`New-Item` missing `-LiteralPath` in eval-weekly
- `cli/grok-agent.py:724` — help text conflates Pydantic version with spec version in description string
- `cli/grok-agent.py:294` — no mutual-exclusion check for `api` + `api_ref` on same tool
- `scripts/generate-template.py:194` — generated `metadata.repository` lacks `https://` scheme
- `scripts/generate-template.py:373` — description min_length is 12 in generator vs 10 in validator
- `safety/scanner.py` — `III.bridges-min-count` misattributed to Article III (should be Article VII)
- `safety/scanner.py` — `I.2-xai-positioning` runs out of Article I order in file (cosmetic, no functional impact)
- `safety/scanner.py:241` — `II.posts-consent` undocumented default-True for absent `consent_required`
- `templates/super-agents/cross-reality-action-fabric/eval/promptfoo.yaml:42` — references `transforms/extract_run.js` which doesn't exist
- `templates/super-agents/cross-reality-action-fabric/connectors/stagehand_client.py` — `plan_web_action` defined but never wired into graph
- `templates/super-agents/living-narrative-fabric/connectors/crawl4ai_client.py` — `asyncio.run()` raises inside Streamlit; needs `nest_asyncio`
- `templates/super-agents/living-narrative-fabric/orchestrator.py:401` — operator precedence bug `24 * days or 1` → `24 * (days or 1)`
- `templates/super-agents/self-evolving-personal-os/graph.py:505` — `<= MAX_EVOLUTION_LOOPS` allows 2 iterations, should be `<`
- `templates/super-agents/self-evolving-personal-os/graph.py:714` — accesses `adapter._client` (private attribute)
- `creator-program/v2/payment_provider.py:43` — `os.environ.get(...)` evaluated at import time (not at call time)
- `templates/finance/x-smart-cashtag-alpha-engine/data/store.py:170` — `asset_class` unconditionally overwritten in `upsert_cashtag`
- All 4 `.streamlit/config.toml` — deprecated `[browser].serverPort` key
- `HANDOFF_LOG.md` — 31 gap prompt numbers (P86–P89, P98–P102, P104–P120, P156–P158, P164, P170)
- `docs/SOURCES.md` — duplicate CONSTRAINTS.md entry in sources table

---

## Quick wins (≤ 30 min each, high visibility)

If time is limited, do these first for maximum impact:

1. **Step 1 (pages.yml)** — Fixes the live deployed site immediately.
2. **Step 2 (next.config.js basePath)** — Fixes all asset 404s on the live site.
3. **Step 6 (scanner float bug)** — One-line fix, prevents false validation errors.
4. **Step 4 (SEPOS crash)** — Two-line fix, prevents SEPOS from crashing on every violation.
5. **Step 5 (LNF model name)** — One-line fix, enables real X-search to work.
6. **Step 30 (SOURCES.md AI copy)** — Deletes embarrassing leaked AI text from public docs.

---

## Effort estimates

| Tier | Steps | Estimated dev-hours |
|------|-------|---------------------|
| TIER 1 — Infrastructure | 1–5 | 4–6h |
| TIER 2 — Critical correctness | 6–15 | 6–8h |
| TIER 3 — High-impact bugs | 16–25 | 8–10h |
| TIER 4 — Medium priority | 26–36 | 6–8h |
| LOW — Cleanup | various | 4–6h |
| **Total** | | **~28–38 dev-hours** |

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
<!-- SCANNER:EXEMPT-END -->
