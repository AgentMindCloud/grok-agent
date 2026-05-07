# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community — Recipe A Slot 6 smoke test for the
# X Money Companion Dashboard. This script is the "grok install this"
# readiness check for Tool #1.
#
# WHAT IT VERIFIES
# ----------------
# 1. All 12 expected files exist in the dashboard folder.
# 2. A working Python 3.12+ interpreter is on PATH.
# 3. `cli/grok-agent.py validate` accepts the manifest (v2.15 schema).
# 4. `safety/scanner.py scan` returns 0 Constitution findings.
# 5. Every code/config/markdown file has an Apache 2.0 license header.
# 6. Article V.1 + V.2 disclaimers are present in app.py, system.md, README.md.
# 7. All 5 manifest tools + 1 helper are importable from the data package.
# 8. SQLite init + insert + categorize round-trip works.
# 9. `search_x_posts` (the offline stub) returns the expected shape.
# 10. `launcher.ps1` parses cleanly under the current PowerShell engine.
# 11. `.streamlit/config.toml` parses and has the required sections + privacy posture.
#
# USAGE
# -----
#   .\smoke_test.ps1                # human-readable colorized output
#   .\smoke_test.ps1 -Json          # also emit machine-readable JSON for CI
#   .\smoke_test.ps1 -SkipDeps -NoBrowser   # parameter parity with launcher.ps1
#                                            (no-ops: smoke test is offline + non-interactive)
#
# Exit code 0 if all checks pass, 1 otherwise.

#requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipDeps,    # parity with launcher.ps1; smoke test never installs
    [switch]$NoBrowser    # parity with launcher.ps1; smoke test never opens a browser
)

# We collect failures rather than crashing on first one.
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$manifest  = Join-Path $scriptDir "grok-agent.yaml"
$slug      = "x-money-companion-dashboard"

$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Check, [string]$Status, [string]$Detail = "")
    [void]$results.Add([PSCustomObject]@{ Check = $Check; Status = $Status; Detail = $Detail })
    $color = switch ($Status) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        'WARN' { 'Yellow' }
        default { 'Gray' }
    }
    $line = "  [{0,-4}]  {1}" -f $Status, $Check
    if ($Detail) { $line += "  -  $Detail" }
    Write-Host $line -ForegroundColor $color
}

function Resolve-Python {
    foreach ($c in @(@{ Cmd = "python"; Pre = @() }, @{ Cmd = "py"; Pre = @("-3") })) {
        try {
            $verOut = & $c.Cmd @($c.Pre) --version 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0 -and $verOut -match "Python 3\.(\d+)") {
                # Smoke test requires 3.12+ to match launcher.ps1 — keeping these
                # aligned avoids a smoke pass / launcher fail mismatch.
                if ([int]$Matches[1] -ge 12) {
                    return [PSCustomObject]@{
                        Cmd = $c.Cmd; Pre = $c.Pre; Version = $verOut.Trim()
                    }
                }
            }
        } catch { }
    }
    return $null
}

# --- Banner --------------------------------------------------------------

Write-Host ""
Write-Host "  =====================================================" -ForegroundColor DarkCyan
Write-Host "    Tool #1 Smoke Test"                                  -ForegroundColor Cyan
Write-Host "    X Money Companion Dashboard"                         -ForegroundColor Cyan
Write-Host "    Built for xAI, X, Grok and the ecosystem community. ❤️"                     -ForegroundColor DarkCyan
Write-Host "  =====================================================" -ForegroundColor DarkCyan
Write-Host ""

# --- Check 1: required files exist --------------------------------------

$expected = @(
    "grok-agent.yaml", "README.md", "app.py", "requirements.txt",
    "launcher.ps1", "smoke_test.ps1", ".streamlit/config.toml",
    "prompts/system.md", "prompts/user_templates.md",
    "data/__init__.py", "data/store.py", "data/api_clients.py"
)
$missing = @($expected | Where-Object { -not (Test-Path (Join-Path $scriptDir $_)) })
if ($missing.Count -eq 0) {
    Add-Result "All $($expected.Count) required files present" "PASS"
} else {
    Add-Result "Required files present" "FAIL" "missing: $($missing -join ', ')"
}

# --- Check 2: Python interpreter ----------------------------------------

$py = Resolve-Python
if ($py) {
    Add-Result "Python interpreter found" "PASS" $py.Version
} else {
    Add-Result "Python interpreter found" "FAIL" "no python or py -3 (3.12+) on PATH"
}

# --- Check 3: manifest schema validation --------------------------------

if ($py) {
    $validatePy = Join-Path $repoRoot "cli/grok-agent.py"
    $out = & $py.Cmd @($py.Pre) $validatePy validate $manifest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result "Schema validation (cli/grok-agent.py)" "PASS" "v2.15 OK"
    } else {
        Add-Result "Schema validation" "FAIL" (($out | Out-String).Trim() -replace "`n.*", "")
    }
}

# --- Check 4: Constitution scanner --------------------------------------

if ($py) {
    $scannerPy = Join-Path $repoRoot "safety/scanner.py"
    $out = & $py.Cmd @($py.Pre) $scannerPy scan $manifest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result "Constitution scanner (safety/scanner.py)" "PASS" "0 findings"
    } else {
        Add-Result "Constitution scanner" "FAIL" (($out | Out-String).Trim() -replace "`n.*", "")
    }
}

# --- Check 5: Apache 2.0 headers on every file --------------------------

$missingHeaders = @($expected | Where-Object {
    $p = Join-Path $scriptDir $_
    (Test-Path $p) -and ((Get-Content -LiteralPath $p -Raw) -notmatch "Apache License")
})
if ($missingHeaders.Count -eq 0) {
    Add-Result "Apache 2.0 headers on all $($expected.Count) files" "PASS"
} else {
    Add-Result "Apache 2.0 headers" "FAIL" "missing: $($missingHeaders -join ', ')"
}

# --- Check 6: Article V.1 + V.2 disclaimers ------------------------------

$disclaimerSpec = @(
    @{ File = "app.py";           Patterns = @("NOT FINANCIAL ADVICE", "NOT TAX ADVICE") }
    @{ File = "prompts/system.md";Patterns = @("Not financial advice", "Not tax advice") }
    @{ File = "README.md";        Patterns = @("Not financial advice", "Not tax advice") }
)
$dMisses = @()
foreach ($d in $disclaimerSpec) {
    $p = Join-Path $scriptDir $d.File
    if (-not (Test-Path $p)) { $dMisses += "$($d.File) (file missing)" ; continue }
    $content = Get-Content -LiteralPath $p -Raw
    foreach ($pat in $d.Patterns) {
        if ($content -notmatch [regex]::Escape($pat)) {
            $dMisses += "$($d.File) lacks '$pat'"
        }
    }
}
if ($dMisses.Count -eq 0) {
    Add-Result "Article V.1 + V.2 disclaimers in app.py / system.md / README.md" "PASS"
} else {
    Add-Result "Article V disclaimers" "FAIL" ($dMisses -join '; ')
}

# --- Check 7: module imports (5 tools + 1 helper) -----------------------

if ($py) {
    $importTest = @'
from data.store      import init_db, categorize_transaction, build_tax_export, summarize_alerts, insert_transaction, count_transactions
from data.api_clients import fetch_market_quote, fetch_relevant_news, search_x_posts
print("OK")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $importTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Module imports (5 tools + 1 helper)" "PASS"
        } else {
            Add-Result "Module imports" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 8: SQLite round-trip + categorize ----------------------------

if ($py) {
    $dbTest = @'
from data.store import (
    init_db, insert_transaction, count_transactions, categorize_transaction
)
init_db()
n0 = count_transactions()
tx_id = insert_transaction(
    tx_date="2026-01-01", amount=10.0, counterparty="SmokeTest", source="manual"
)
n1 = count_transactions()
cat = categorize_transaction(amount=10.0, counterparty="SmokeTest", memo="from smoke")
assert tx_id > 0,            f"expected new id, got {tx_id}"
assert n1 == n0 + 1,         f"expected n0+1, got {n0}->{n1}"
assert "category" in cat,    "categorize result missing 'category'"
print(f"rows {n0}->{n1} category={cat['category']}/{cat['confidence']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $dbTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "SQLite init + insert + categorize" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "SQLite round-trip" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 9: API offline-safety (search_x_posts stub shape) ------------

if ($py) {
    $apiTest = @'
from data.api_clients import search_x_posts
res = search_x_posts("smoke")
assert isinstance(res, dict),                 "must return dict"
assert "provenance" in res,                    "missing provenance"
assert "error" in res,                         "missing error field"
assert res["provenance"].get("stub") is True,  "stub flag must be True"
print("shape ok:", sorted(res.keys()))
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $apiTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "API client offline-safety (search_x_posts stub)" "PASS"
        } else {
            Add-Result "API client offline-safety" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 10: launcher.ps1 parses cleanly ------------------------------

$launcher = Join-Path $scriptDir "launcher.ps1"
if (Test-Path $launcher) {
    $tokens = $null; $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $launcher, [ref]$tokens, [ref]$errs)
    if ($errs.Count -eq 0) {
        Add-Result "launcher.ps1 parses under PS $($PSVersionTable.PSVersion)" "PASS"
    } else {
        Add-Result "launcher.ps1 parses" "FAIL" "$($errs.Count) parse errors"
    }
}

# --- Check 11: .streamlit/config.toml shape -----------------------------

if ($py) {
    $env:SMOKE_TOML = Join-Path $scriptDir ".streamlit/config.toml"
    $tomlTest = @'
import os, sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open(os.environ["SMOKE_TOML"], "rb") as f:
    cfg = tomllib.load(f)
required = ["theme", "server", "browser", "client", "runner"]
missing = [k for k in required if k not in cfg]
if missing:
    print("missing sections:", missing); sys.exit(1)
if cfg["browser"].get("gatherUsageStats") is not False:
    print("gatherUsageStats must be false (Article VII)"); sys.exit(1)
print("primaryColor=" + cfg["theme"]["primaryColor"])
'@
    $out = & $py.Cmd @($py.Pre) -c $tomlTest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result ".streamlit/config.toml shape + privacy" "PASS" (($out | Out-String).Trim())
    } else {
        Add-Result ".streamlit/config.toml shape" "FAIL" (($out | Out-String).Trim())
    }
    Remove-Item Env:SMOKE_TOML -ErrorAction SilentlyContinue
}

# --- Final summary ------------------------------------------------------

$pass = ($results | Where-Object Status -eq 'PASS').Count
$fail = ($results | Where-Object Status -eq 'FAIL').Count
$warn = ($results | Where-Object Status -eq 'WARN').Count
$total = $results.Count

Write-Host ""
Write-Host "  =====================================================" -ForegroundColor DarkCyan
if ($fail -eq 0) {
    Write-Host "    Tool #1 - X Money Companion Dashboard: PASS"        -ForegroundColor Green
    Write-Host "    $pass/$total checks green; ready for 'grok install this'." -ForegroundColor Green
} else {
    Write-Host "    Tool #1 - X Money Companion Dashboard: FAIL"        -ForegroundColor Red
    Write-Host "    $pass/$total green ; $fail FAIL ; $warn WARN"       -ForegroundColor Red
}
Write-Host "  =====================================================" -ForegroundColor DarkCyan
Write-Host ""

if ($Json) {
    @{
        tool   = $slug
        status = $(if ($fail -eq 0) { "PASS" } else { "FAIL" })
        pass   = $pass; fail = $fail; warn = $warn; total = $total
        checks = $results
    } | ConvertTo-Json -Depth 4
}

if ($fail -eq 0) { exit 0 } else { exit 1 }
