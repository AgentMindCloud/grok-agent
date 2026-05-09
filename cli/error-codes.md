<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — CLI Error Codes

> Built for xAI, X, Grok and the ecosystem community. ❤️

When `grok-agent.ps1` exits non-zero it tries to print an `E-XXXX-NNN` code. Run `.\cli\grok-agent.ps1 -Explain <code>` (or `python cli/grok-agent.py --explain <code>` once that lands) to see the entry below for any code.

The format mirrors POSIX-style structured error reporting: a stable code, a one-sentence summary, the Constitution Article touched, the most likely root cause, and the exact re-run hint.

---

## E-CLI-001 — Unknown command

- **Article:** I (operating contract)
- **Cause:** The first positional argument wasn't `help`, `new`, `install`, `validate`, `list`, `run`, or `eval-weekly`.
- **Fix:** `.\cli\grok-agent.ps1 help` prints the full verb list. Verbs are case-insensitive but kebab-case in spec docs.
- **Exit:** 64

## E-CLI-002 — Missing required argument

- **Article:** I
- **Cause:** A verb was given without its required positional argument (e.g. `install` with no path / `-Yaml` / `-FromStdin`).
- **Fix:** `.\cli\grok-agent.ps1 help` shows the full verb list with usage. Common shapes: `install <path-or-slug-or-url>`, `validate <path>`, `run <name>`.
- **Exit:** 64

## E-INSTALL-001 — Invalid agent name (kebab-case required)

- **Article:** I
- **Cause:** `new <name>` got a name that doesn't match `^[a-z][a-z0-9-]*$`.
- **Fix:** Use lowercase letters, digits, and hyphens. First character must be a letter. Example: `daily-briefing-agent` ✓ ; `Daily_Brief` ✗ ; `123agent` ✗.
- **Exit:** 64

## E-INSTALL-002 — Path not found

- **Article:** I
- **Cause:** `install <path>` was given a filesystem path that doesn't exist.
- **Fix:** Confirm the path with `Test-Path <path>`. For bare slugs, the CLI already searches `templates/{super-agents,creator,finance,general,x-native}/<slug>/grok-agent.yaml` — typo your slug or check the templates folder.
- **Exit:** 66

## E-INSTALL-003 — URL fetch failed

- **Article:** I (also see Article VII — privacy)
- **Cause:** `install https://...` failed at `Invoke-WebRequest`. Often network, sometimes 404 or 401.
- **Fix:** Confirm the URL is reachable in a browser, then retry. If the URL requires auth, host the manifest on a public raw URL instead. Authenticated scraping is a hard refusal (Article III).
- **Exit:** 66

## E-INSTALL-004 — Slug matched multiple templates

- **Article:** I
- **Cause:** `install <slug>` resolved to two or more templates with the same slug across `templates/<category>/`.
- **Fix:** Disambiguate by passing the full path: `.\cli\grok-agent.ps1 install templates\<category>\<slug>`.
- **Exit:** 66

## E-VALIDATE-001 — Manifest failed v2.15 surface validation

- **Article:** I + IV (provenance — schema enforces append-only declarations)
- **Cause:** A required field is missing, the version isn't `2.14` or `2.15`, the kind isn't a known v2.15 kind, or the license isn't `Apache-2.0`.
- **Fix:** Read the bullet list under the `XX  Manifest failed v2.15 surface validation` line — each bullet names the field. Compare against `spec/v2.15/grok-agent.yaml` for shape.
- **Exit:** 65

## E-VALIDATE-002 — Manifest failed Pydantic deep validation

- **Article:** I + IV
- **Cause:** `cli/grok-agent.py validate <path>` rejected the manifest. Common: nested-section typo (extra=forbid), wrong type for a numeric field, `kind=super-agent` without a `constitution:` section, or `kind=vision-analyzer` without `grok.vision: true`.
- **Fix:** The Pydantic error trace lists `loc` + `msg` for each violation. Fix the offending key/value and re-run. For new top-level kind-specific extension blocks, see [`spec/v2.15/grok-agent.yaml`](../spec/v2.15/grok-agent.yaml).
- **Exit:** 65

## E-SCANNER-001 — Constitution scanner found a CRITICAL violation

- **Article:** Whichever the scanner names (most often II — consent gates, III — provenance append-only, V — disclaimers, VIII — forbidden phrases).
- **Cause:** `safety/scanner.py scan <path>` exited non-zero. The output names the rule (e.g. `HR-003`) and the line.
- **Fix:** Apply the canonical fix for the rule. For `HR-003` (provenance append-only): add `provenance.append_only: true`. For Article V missing disclaimers on a finance agent: add the verbatim banner from CLAUDE.md §12. For Article VIII forbidden-phrase leak: rewrite the offending sentence to enumerate explicitly.
- **Exit:** 65

## E-RUN-001 — Agent not installed

- **Article:** I
- **Cause:** `run <name>` ran before `install <name>` succeeded.
- **Fix:** `.\cli\grok-agent.ps1 list` shows what's installed. Install first, then run.
- **Exit:** 66

## E-RUN-002 — No launcher resolvable

- **Article:** I
- **Cause:** Installed agent has no `launcher.ps1`, no `app.py`, no `main.py`, and no `run.py`.
- **Fix:** Add a launcher file to the agent (typically `launcher.ps1` for Windows-first agents or `app.py` for Streamlit). Re-install. The launcher resolution order is documented in [`cli/grok-agent.ps1`](grok-agent.ps1) `Invoke-Run`.
- **Exit:** 69

## E-RUN-003 — Python not found in PATH

- **Article:** I
- **Cause:** A python launcher was the only resolution path but `python` (or `python3`) isn't on `PATH`.
- **Fix:** Install Python 3.12+ from python.org and re-open PowerShell so the new PATH takes effect.
- **Exit:** 69

## E-INTERNAL-001 — Unexpected error

- **Article:** I
- **Cause:** Something the CLI didn't anticipate. The exception message + script stack trace are printed in DarkGray.
- **Fix:** Re-run with `-Verbose` for more context. If reproducible, open an issue at the repo with the exception text.
- **Exit:** 70

---

## How to add a new code

1. Pick the next free number in the relevant prefix (`E-CLI`, `E-INSTALL`, `E-VALIDATE`, `E-SCANNER`, `E-RUN`, `E-INTERNAL`).
2. Add an entry above with: Article, Cause, Fix, Exit code.
3. At the corresponding `Write-Err2` site in `cli/grok-agent.ps1`, prefix the message with `[E-XXXX-NNN]` so users can find this entry.

Built for xAI, X, Grok and the ecosystem community. ❤️
