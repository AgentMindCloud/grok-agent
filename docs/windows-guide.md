<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Windows Guide — Grok Agent OS

> **Built to help xAI and Grok win.** This guide is the canonical, end-to-end Windows 11 walkthrough for installing, validating, running, and troubleshooting Grok agents. Every command on this page is PowerShell. There are no macOS or Linux instructions here, by design.

---

## 1. Prerequisites

You need three things, all of which install without admin rights using the Microsoft Store or per-user installers.

| Requirement | Version | How to verify |
|---|---|---|
| Windows 11 | Any current build | `Get-ComputerInfo \| Select-Object OsName, OsVersion` |
| PowerShell | 5.1+ (Windows PowerShell) or 7+ (PowerShell Core) | `$PSVersionTable.PSVersion` |
| Python | 3.12+ | `python --version` |
| Google Chrome | latest | (any agent UI assumes Chrome) |
| Git | any current | `git --version` |

If Python is missing, install from the Microsoft Store ("Python 3.12") — no admin needed and PATH is wired automatically.

```powershell
# Check everything in one shot
$PSVersionTable.PSVersion ; python --version ; git --version ; chrome --version 2>$null
```

> If a check fails, fix it before continuing. The CLI assumes all four are present.

---

## 2. Clone the repo

```powershell
# pick a folder you own (no admin)
cd $env:USERPROFILE
New-Item -Path "code" -ItemType Directory -Force | Out-Null
cd code

git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent
```

If `git clone` fails because you're behind a corporate proxy, set:

```powershell
$env:HTTPS_PROXY = "http://your-proxy:port"
$env:HTTP_PROXY  = "http://your-proxy:port"
```

---

## 3. Install Python dependencies (per-user, no admin)

The validator and scanner need `pydantic` v2 and `pyyaml`:

```powershell
python -m pip install --user --upgrade pip
python -m pip install --user 'pydantic>=2.7,<3' 'pyyaml>=6.0'
```

`--user` installs into `$env:APPDATA\Python\` and never touches system Python. If you ever need to clean up, delete that folder.

> If `pip` is not found, install Python via the Microsoft Store (it bundles pip) or run `python -m ensurepip`.

---

## 4. Allow the PowerShell CLI to run

By default, Windows PowerShell blocks unsigned `.ps1` files. Set the **CurrentUser** scope to `RemoteSigned` (no admin needed):

```powershell
Get-ExecutionPolicy -Scope CurrentUser

# If it shows Restricted or Undefined, change it (one-time):
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`RemoteSigned` lets local scripts run unrestricted while still requiring signatures on scripts downloaded from the internet. This is the recommended developer setting.

---

## 5. First commands

From the `grok-agent` repo root:

```powershell
# Show CLI help (banner + commands + paths)
.\cli\grok-agent.ps1 help

# Print scanner version + every Constitution check it enforces
python safety\scanner.py info

# Validate the canonical v2.15 schema file (sanity check)
.\cli\grok-agent.ps1 validate spec\v2.15\grok-agent.yaml
```

Expected output for the validate step:

```
-> Validating: ...\spec\v2.15\grok-agent.yaml
OK Surface validation passed.
OK Deep schema validation (Python) passed.
OK Manifest is valid v2.15.
```

If you see `Python validator not available — proceeding with surface validation only`, your Python install is missing or `pip install` step 3 was skipped.

---

## 6. Scaffold a new agent

```powershell
.\cli\grok-agent.ps1 new my-first-agent
```

This creates `.\my-first-agent\` with a minimal v2.15 `grok-agent.yaml` + `README.md`. Edit `grok-agent.yaml`, then validate:

```powershell
.\cli\grok-agent.ps1 validate my-first-agent
```

When it reports `OK Manifest is valid v2.15.`, your scaffold is good.

---

## 7. Install an agent

Three ways — pick whichever matches how you got the manifest.

### 7.1 — From a local folder (the typical case)

```powershell
.\cli\grok-agent.ps1 install my-first-agent
```

The CLI:

1. Validates the manifest against v2.15.
2. Runs the Constitution scanner.
3. Copies the folder into `$env:LOCALAPPDATA\grok-agent\agents\<name>\`.

### 7.2 — From inline YAML

```powershell
$manifest = @"
version: "2.15"
kind: "agent"
name: "hello-grok"
description: "Minimal example — proves the schema works."
author: "@JanSol0s"
license: "Apache-2.0"
"@

.\cli\grok-agent.ps1 install -Yaml $manifest
```

### 7.3 — "grok install this" paste flow

When you see a Grok post on X containing a `grok-agent.yaml` block, copy the YAML and run:

```powershell
.\cli\grok-agent.ps1 install -FromStdin
# Paste the YAML
# Press Ctrl-Z then Enter to finish input
```

The CLI accepts pasted content via stdin, validates it, scans it, and installs.

---

## 8. List + run installed agents

```powershell
# Show every installed agent under $env:LOCALAPPDATA\grok-agent\agents\
.\cli\grok-agent.ps1 list

# Launch one
.\cli\grok-agent.ps1 run my-first-agent
```

`run` looks for a launcher in this order:

1. `windows.launcher` declared in the manifest (e.g. `launcher.ps1`)
2. `launcher.ps1` in the agent folder
3. `app.py` (auto-runs `python -m streamlit run app.py`)
4. `main.py` or `run.py` (auto-runs `python <entry>`)

If none are found, the CLI tells you exactly what's expected.

---

## 9. Where data lives (Windows-correct paths)

Local-first by design. Nothing leaves your machine without an explicit consent gate.

| Purpose | Path |
|---|---|
| Installed agents | `$env:LOCALAPPDATA\grok-agent\agents\<name>\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\logs\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\cache\` |
| Per-agent SQLite (when applicable) | `$env:LOCALAPPDATA\grok-agent\<name>.db` |
| User configs | `$env:APPDATA\grok-agent\config\` |

To open the agent root in Explorer:

```powershell
explorer $env:LOCALAPPDATA\grok-agent
```

To wipe a single agent (clean reinstall):

```powershell
$name = "my-first-agent"
Remove-Item "$env:LOCALAPPDATA\grok-agent\agents\$name" -Recurse -Force
```

> **Never** delete the parent `grok-agent` folder while an agent is running — you'll lose its in-flight provenance log.

---

## 10. Updating to a new version

```powershell
cd $env:USERPROFILE\code\grok-agent
git pull origin main
python -m pip install --user --upgrade 'pydantic>=2.7,<3' 'pyyaml>=6.0'
```

Re-validating already-installed agents after an update is a good habit:

```powershell
.\cli\grok-agent.ps1 list
# Then for each agent:
python cli\grok-agent.py validate "$env:LOCALAPPDATA\grok-agent\agents\<name>"
```

---

## 11. Troubleshooting

### "cannot be loaded because running scripts is disabled on this system"

You skipped step 4. Fix:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### "python : The term 'python' is not recognized"

Python isn't on PATH. Easiest fix: install Python 3.12 from the Microsoft Store. Or run the standard installer and check **"Add Python to PATH"**.

### "ModuleNotFoundError: No module named 'pydantic'" (or 'yaml')

You skipped step 3. Run:

```powershell
python -m pip install --user 'pydantic>=2.7,<3' 'pyyaml>=6.0'
```

### "Python validator not available — proceeding with surface validation only"

The PowerShell CLI couldn't find `python` or couldn't run `cli\grok-agent.py`. Verify:

```powershell
Get-Command python
Test-Path .\cli\grok-agent.py
python cli\grok-agent.py info
```

All three must succeed.

### Windows Defender blocks an agent's launcher

By design, `windows.requires_admin: true` is rejected by the Constitution scanner. If Defender still flags an agent's `.ps1`, add a per-folder exclusion (Settings → Virus & threat protection → Manage settings → Exclusions). Do **not** disable Defender globally.

### "grok install this" paste hangs forever

The CLI waits for end-of-input. After pasting the YAML, press **Ctrl-Z** then **Enter** (Windows console end-of-stream marker). On PowerShell 7+ in some terminals, **Ctrl-D** also works.

### Streamlit launches but the browser opens in the wrong app

By design, the platform is Windows + Chrome only. Set Chrome as your default browser:

```
Settings → Apps → Default apps → Web browser → Google Chrome
```

### A manifest fails the Constitution scanner

Read the finding line. Each finding includes a `[Const. Art. X.Y]` tag pointing to the offending Constitution article in `safety/constitution.md`. Fix the manifest (or remove the action) to comply. To re-scan:

```powershell
python safety\scanner.py scan path\to\grok-agent.yaml --severity-floor info
```

### "ValidationError: Extra inputs are not permitted"

Your manifest contains a key that v2.15 doesn't define. The error message names the field. Either remove the key or check `spec\v2.15\grok-agent.yaml` for the canonical name (typo / hyphen-vs-underscore is a common cause).

### A v2.14 manifest doesn't validate

It should — v2.15 is 100% backwards compatible. Common gotchas:
- `version: 2.14` (number) instead of `version: "2.14"` (string)
- `license: MIT` instead of `license: "Apache-2.0"` (Apache 2.0 is mandatory in this repo)
- A field in the wrong section (e.g. `model:` outside `grok:`)

---

## 12. Uninstall everything

```powershell
# Remove all installed agents (does NOT touch the cloned repo)
Remove-Item "$env:LOCALAPPDATA\grok-agent" -Recurse -Force

# Remove the cloned repo
Remove-Item "$env:USERPROFILE\code\grok-agent" -Recurse -Force

# (Optional) remove per-user Python deps
python -m pip uninstall -y pydantic pyyaml
```

That's a full rollback. Nothing else was modified — by design.

---

## 13. What to read next

- The schema you'll author against — [`spec/v2.15/grok-agent.yaml`](../spec/v2.15/grok-agent.yaml)
- The rule book every agent must follow — [`safety/constitution.md`](../safety/constitution.md)
- The high-level overview — [`docs/index.md`](index.md)
- The pitch for xAI engineers — [`docs/for-xai-adoption.md`](for-xai-adoption.md)
- The full project plan — [`CLAUDE.md`](../CLAUDE.md)

---

> Built to help xAI and Grok win. 🚀
