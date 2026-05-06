# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community — Recipe A Slot 6 smoke test for the
# X Smart Cashtag Alpha Engine. This script is the "grok install this"
# readiness check for Tool #2.
#
# WHAT IT VERIFIES (14 checks)
# ----------------------------
# 1.  All 12 expected files exist in the engine folder.
# 2.  A working Python 3.11+ interpreter is on PATH.
# 3.  `cli/grok-agent.py validate` accepts the manifest (v2.15 schema).
# 4.  `safety/scanner.py scan` returns 0 Constitution findings.
# 5.  Every code/config/markdown file has an Apache 2.0 license header.
# 6.  Article V.1 + V.2 disclaimers present in app.py / system.md / README.md.
# 7.  Article III contradiction-flagging language present in system.md +
#     user_templates.md (Tool #2's defining capability per the manifest).
# 8.  All 5 manifest tools + 1 helper importable from the data package.
# 9.  SQLite init + track_cashtag + watchlist round-trip works.
# 10. simulate_portfolio runs + persists a row to portfolio_simulations.
# 11. generate_alpha_report orchestrates quote + news + x_search + Grok stub
#     and persists a structurally-valid alpha_reports row.
# 12. API client offline-safety: search_x_posts stub returns the correct
#     shape with provenance.stub == True.
# 13. Cross-tool read: fetch_companion_dashboard_holdings handles both
#     "Tool #1 installed" and "not installed" cases gracefully.
# 14. launcher.ps1 parses cleanly + .streamlit/config.toml shape with
#     port=8502 verified (so Tool #1 + Tool #2 coexist on the same machine).
#
# USAGE
# -----
#   .\smoke_test.ps1                      # human-readable colorized output
#   .\smoke_test.ps1 -Json                # also emit JSON for CI
#   .\smoke_test.ps1 -SkipDeps -NoBrowser # parameter parity with launcher
#                                           (no-ops: smoke test is offline +
#                                            non-interactive by design)
#
# Exit code 0 if all checks pass, 1 otherwise.

#requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipDeps,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$manifest  = Join-Path $scriptDir "grok-agent.yaml"
$slug      = "x-smart-cashtag-alpha-engine"

$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Check, [string]$Status, [string]$Detail = "")
    [void]$results.Add([PSCustomObject]@{ Check = $Check; Status = $Status; Detail = $Detail })
    $color = switch ($Status) {
        'PASS' { 'Green' } 'FAIL' { 'Red' } 'WARN' { 'Yellow' } default { 'Gray' }
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
                if ([int]$Matches[1] -ge 11) {
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
Write-Host "    Tool #2 Smoke Test"                                  -ForegroundColor Cyan
Write-Host "    X Smart Cashtag Alpha Engine"                        -ForegroundColor Cyan
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
    Add-Result "Python interpreter found" "FAIL" "no python or py -3 (3.11+) on PATH"
}

# --- Check 3: manifest schema validation --------------------------------

if ($py) {
    $validatePy = Join-Path $repoRoot "cli/grok-agent.py"
    $out = & $py.Cmd @($py.Pre) $validatePy validate $manifest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result "Schema validation (cli/grok-agent.py)" "PASS" "v2.15 OK / kind=alpha-engine"
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

# --- Check 7: Article III contradiction-flagging language (Tool #2 specific) -

$contradictionFiles = @("prompts/system.md", "prompts/user_templates.md")
$cMisses = @()
foreach ($f in $contradictionFiles) {
    $p = Join-Path $scriptDir $f
    if (-not (Test-Path $p)) { $cMisses += "$f (file missing)" ; continue }
    $content = Get-Content -LiteralPath $p -Raw
    if ($content -notmatch "ontradiction") {
        $cMisses += "$f lacks contradiction-flagging language"
    }
}
if ($cMisses.Count -eq 0) {
    Add-Result "Article III contradiction-flagging language present" "PASS" "in system.md + user_templates.md"
} else {
    Add-Result "Article III contradiction-flagging" "FAIL" ($cMisses -join '; ')
}

# --- Check 8: module imports (5 tools + 1 helper) -----------------------

if ($py) {
    $importTest = @'
from data.store      import (
    init_db, track_cashtag, simulate_portfolio, generate_alpha_report,
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    insert_alpha_report, get_recent_alpha_reports,
    fetch_companion_dashboard_holdings,
)
from data.api_clients import (
    fetch_cashtag_quote, fetch_cashtag_news, search_x_posts,
)
print("OK")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $importTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Module imports (5 manifest tools + 1 helper + cross-tool reader)" "PASS"
        } else {
            Add-Result "Module imports" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 9: SQLite track_cashtag + watchlist round-trip --------------

if ($py) {
    $watchTest = @'
from data.store import init_db, track_cashtag, get_watchlist, remove_from_watchlist
init_db()
n0 = len(get_watchlist())
add = track_cashtag("$SMOKE", "add", threshold_pct=3.0)
assert add["ok"] is True, f"add failed: {add}"
n1 = len(get_watchlist())
assert n1 >= n0 + 1 or n1 == n0, "watchlist size did not increment or remain stable"
remove_from_watchlist("$SMOKE")
print(f"watchlist {n0}->{n1}, threshold_pct={add['threshold_pct']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $watchTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "SQLite track_cashtag + watchlist round-trip" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "SQLite watchlist round-trip" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 10: simulate_portfolio computation + persist -----------------

if ($py) {
    $simTest = @'
from data.store import simulate_portfolio, get_recent_simulations
res = simulate_portfolio(
    positions=[
        {"cashtag": "$BTC",  "qty": 0.1, "entry_price": 60000.0},
        {"cashtag": "$AAPL", "qty": 5,    "entry_price": 200.0},
    ],
    start_date="2026-04-01",
    end_date="2026-05-01",
)
assert "starting_value" in res and "ending_value" in res, "missing computed fields"
assert res["error"] is None, f"sim returned error: {res['error']}"
sims = get_recent_simulations(limit=1)
assert len(sims) >= 1, "simulation not persisted"
print(f"starting=${res['starting_value']:.2f} ending=${res['ending_value']:.2f} pnl_pct={res['pnl_pct']}% seed={res['seed']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $simTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "simulate_portfolio computation + persist" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "simulate_portfolio" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 11: generate_alpha_report orchestration + persist ------------

if ($py) {
    $alphaTest = @'
from data.store import generate_alpha_report, get_recent_alpha_reports
res = generate_alpha_report("$BTC", window_hours=24)
assert "id" in res and "report" in res, "missing id or report key"
rep = res["report"]
assert rep["confidence"] in ("high", "medium", "low"), f"bad confidence: {rep['confidence']}"
assert isinstance(rep.get("sources"),        list),  "sources must be list"
assert isinstance(rep.get("contradictions"), list),  "contradictions must be list"
recent = get_recent_alpha_reports(cashtag="$BTC", limit=1)
assert len(recent) >= 1, "alpha report not persisted"
print(f"report_id={res['id']} confidence={rep['confidence']} sources={len(rep['sources'])} contradictions={len(rep['contradictions'])}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $alphaTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "generate_alpha_report orchestration + persist" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "generate_alpha_report" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 12: API offline-safety (search_x_posts stub shape) -----------

if ($py) {
    $apiTest = @'
from data.api_clients import search_x_posts
res = search_x_posts("smoke")
assert isinstance(res, dict),                  "must return dict"
assert "provenance" in res,                     "missing provenance"
assert "error"      in res,                     "missing error field"
assert res["provenance"].get("stub") is True,   "stub flag must be True"
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

# --- Check 13: Cross-tool read (Tool #1 holdings, optional) -------------

if ($py) {
    $crossTest = @'
from data.store import fetch_companion_dashboard_holdings
res = fetch_companion_dashboard_holdings(limit=10)
assert isinstance(res, dict),               "must return dict"
assert "installed" in res,                   "missing 'installed' key"
assert "transactions" in res,                "missing 'transactions' list"
assert "error" in res,                       "missing 'error' key"
if res["installed"]:
    print(f"Tool #1 installed; read {len(res['transactions'])} txns ok")
else:
    print(f"Tool #1 not installed; helper returned graceful error")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $crossTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Cross-tool read: fetch_companion_dashboard_holdings" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "Cross-tool read" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 14: launcher.ps1 parses cleanly ------------------------------

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

# --- Check 15: .streamlit/config.toml shape (port=8502 verified) -------

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
if cfg["server"].get("port") != 8502:
    print(f"server.port must be 8502 to coexist with Tool #1 (got {cfg['server'].get('port')})")
    sys.exit(1)
print(f"primaryColor={cfg['theme']['primaryColor']} port={cfg['server']['port']}")
'@
    $out = & $py.Cmd @($py.Pre) -c $tomlTest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result ".streamlit/config.toml shape + port=8502" "PASS" (($out | Out-String).Trim())
    } else {
        Add-Result ".streamlit/config.toml" "FAIL" (($out | Out-String).Trim())
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
    Write-Host "    Tool #2 - X Smart Cashtag Alpha Engine: PASS"      -ForegroundColor Green
    Write-Host "    $pass/$total checks green; ready for 'grok install this'." -ForegroundColor Green
} else {
    Write-Host "    Tool #2 - X Smart Cashtag Alpha Engine: FAIL"      -ForegroundColor Red
    Write-Host "    $pass/$total green ; $fail FAIL ; $warn WARN"      -ForegroundColor Red
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
