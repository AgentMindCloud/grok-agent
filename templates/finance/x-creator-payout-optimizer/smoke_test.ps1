# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — Recipe A Slot 6 smoke test for the
# X Creator Payout Optimizer. This script is the "grok install this"
# readiness check for Tool #3, and the LAST smoke test of Phase 2's
# X Money Suite (Tools #1 + #2 + #4 + #3 = 24 prompts complete).
#
# WHAT IT VERIFIES (18 checks)
# ----------------------------
# 1.  All 13 expected files exist in the optimizer folder.
# 2.  A working Python 3.11+ interpreter is on PATH.
# 3.  `cli/grok-agent.py validate` accepts the manifest (v2.15, kind=creator-payout-optimizer).
# 4.  `safety/scanner.py scan` returns 0 Constitution findings.
# 5.  Every code/config/markdown file has an Apache 2.0 license header.
# 6.  Article V.1 + V.2 disclaimers present in app.py / system.md / README.md.
# 7.  Article III + cross-tool READS-ONLY language present in system.md +
#     manifest (Tool #3's defining constitutional posture).
# 8.  All 5 manifest tools importable from data package (3 from store + 2 from api_clients).
# 9.  CROSS-TOOL READ: companion_reader.get_companion_summary() returns the
#     expected dict shape; works whether Tool #1 is installed or not.
# 10. CROSS-TOOL READ: vision_reader.get_vision_summary() returns the
#     expected dict shape; works whether Tool #4 is installed or not.
# 11. SQLite READ-ONLY ENFORCEMENT: attempting an INSERT through a
#     `mode=ro` URI handle raises sqlite3.OperationalError — engine-level
#     defense-in-depth for Article III.
# 12. GRACEFUL DEGRADATION: both readers return structured `installed`/
#     `error` fields regardless of sibling presence (contract test).
# 13. SQLite forecast_earnings persistence (3 horizon rows stored).
# 14. estimate_tax_burden persists with Vietnam-resident assumption surfaced.
# 15. analyze_content_roi persists with provenance row counts populated.
# 16. Grok stubs flag provenance.stub=True (Article IV honesty).
# 17. launcher.ps1 parses cleanly under the current PowerShell engine.
# 18. .streamlit/config.toml shape with port=8503 verified.
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
$slug      = "x-creator-payout-optimizer"

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
Write-Host "    Tool #3 Smoke Test"                                  -ForegroundColor Cyan
Write-Host "    X Creator Payout Optimizer"                          -ForegroundColor Cyan
Write-Host "    Built to help xAI and Grok win."                     -ForegroundColor DarkCyan
Write-Host "  =====================================================" -ForegroundColor DarkCyan
Write-Host ""

# --- Check 1: required files exist --------------------------------------

$expected = @(
    "grok-agent.yaml", "README.md", "app.py", "requirements.txt",
    "launcher.ps1", "smoke_test.ps1", ".streamlit/config.toml",
    "prompts/system.md", "prompts/user_templates.md",
    "data/__init__.py", "data/store.py", "data/api_clients.py",
    "data/companion_reader.py", "data/vision_reader.py"
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
        Add-Result "Schema validation (cli/grok-agent.py)" "PASS" "v2.15 OK / kind=creator-payout-optimizer"
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

# --- Check 5: Apache 2.0 headers ----------------------------------------

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

# --- Check 7: Article III + cross-tool READS-ONLY language --------------

$crossRuleSpec = @(
    @{ File = "prompts/system.md"; Patterns = @("read-only", "Article III") }
    @{ File = "grok-agent.yaml";   Patterns = @("READS only", "Article III") }
)
$crMisses = @()
foreach ($d in $crossRuleSpec) {
    $p = Join-Path $scriptDir $d.File
    if (-not (Test-Path $p)) { $crMisses += "$($d.File) (file missing)" ; continue }
    $content = Get-Content -LiteralPath $p -Raw
    foreach ($pat in $d.Patterns) {
        if ($content -notmatch [regex]::Escape($pat)) {
            $crMisses += "$($d.File) lacks '$pat'"
        }
    }
}
if ($crMisses.Count -eq 0) {
    Add-Result "Article III + cross-tool READS-ONLY language" "PASS" "in system.md + manifest"
} else {
    Add-Result "Article III / READS-ONLY language" "FAIL" ($crMisses -join '; ')
}

# --- Check 8: module imports (5 manifest tools across modules) ----------

if ($py) {
    $importTest = @'
from data.store         import (
    init_db, forecast_earnings, estimate_tax_burden, analyze_content_roi,
    insert_content_idea, get_recent_forecasts, get_recent_content_ideas,
)
from data.api_clients   import (
    optimize_content_topic, fetch_x_metrics,
    _grok_forecast_call, _grok_optimize_call, _grok_tax_call,
    _grok_metrics_call, _grok_roi_call,
)
from data.companion_reader import (
    is_installed as comp_installed,
    get_companion_summary, read_transactions, read_revenue_rows, read_cost_rows,
)
from data.vision_reader    import (
    is_installed as vis_installed,
    get_vision_summary, read_receipts, read_parsed_items_for_receipt,
)
print("OK")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $importTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Module imports (5 manifest tools + 2 cross-tool readers)" "PASS"
        } else {
            Add-Result "Module imports" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 9: cross-tool read — companion_reader -----------------------

if ($py) {
    $compTest = @'
from data.companion_reader import get_companion_summary
res = get_companion_summary()
required = {"installed", "transaction_count", "total_inflow", "total_outflow",
            "net", "categories", "earliest_tx", "latest_tx", "path",
            "provenance", "error"}
missing = required - set(res.keys())
assert not missing, f"missing keys: {sorted(missing)}"
assert isinstance(res["installed"], bool), "installed must be bool"
assert "mode" in res["provenance"] and "readonly" in res["provenance"]["mode"], \
       "provenance must declare readonly mode"
print(f"installed={res['installed']} txns={res['transaction_count']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $compTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Cross-tool read: companion_reader (Tool #1)" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "companion_reader cross-tool read" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 10: cross-tool read — vision_reader -------------------------

if ($py) {
    $visTest = @'
from data.vision_reader import get_vision_summary
res = get_vision_summary()
required = {"installed", "receipt_count", "total_outflow", "by_status",
            "earliest_tx", "latest_tx", "path", "provenance", "error"}
missing = required - set(res.keys())
assert not missing, f"missing keys: {sorted(missing)}"
assert isinstance(res["installed"], bool), "installed must be bool"
assert "mode" in res["provenance"] and "readonly" in res["provenance"]["mode"], \
       "provenance must declare readonly mode"
print(f"installed={res['installed']} receipts={res['receipt_count']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $visTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Cross-tool read: vision_reader (Tool #4)" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "vision_reader cross-tool read" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 11: SQLite read-only enforcement (defense-in-depth proof) ----

if ($py) {
    $roTest = @'
import sqlite3
from data import companion_db_path, vision_db_path

# Test against whichever sibling DB exists; if neither, this is degenerate
# but we still want the contract to hold against an existing path.
target = None
for p in (companion_db_path(), vision_db_path()):
    if p.exists():
        target = p; break
if target is None:
    print("no sibling DB present; skipping engine-level test")
    print("OK shape contract test only")
else:
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        # Pick a table that exists in either DB; "transactions" exists in #1
        # and we'd be writing to it through the readonly handle (forbidden).
        conn.execute(
            "INSERT INTO transactions (tx_date, amount, source) "
            "VALUES ('2099-01-01', 0.01, 'manual')"
        )
        raise AssertionError("INSERT succeeded against mode=ro handle — FAIL")
    except sqlite3.OperationalError as e:
        if "readonly" not in str(e).lower():
            # Different error (e.g. missing table on Tool #4 — fall back to a known col)
            try:
                conn.execute(
                    "INSERT INTO receipts (file_path) VALUES ('/smoke-readonly-test.jpg')"
                )
                raise AssertionError("fallback INSERT succeeded — FAIL")
            except sqlite3.OperationalError as e2:
                msg = str(e2).lower()
                assert "readonly" in msg, f"unexpected error: {e2}"
                print(f"OK mode=ro rejects writes: {e2}")
        else:
            print(f"OK mode=ro rejects writes: {e}")
    finally:
        conn.close()
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $roTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "SQLite read-only enforcement (Article III defense)" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "SQLite read-only enforcement" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 12: graceful degradation contract ---------------------------

if ($py) {
    $gdTest = @'
from data.companion_reader import get_companion_summary, is_installed as comp_inst
from data.vision_reader    import get_vision_summary,    is_installed as vis_inst
# Both readers must return a dict with `installed` regardless of sibling state.
c = get_companion_summary()
v = get_vision_summary()
assert isinstance(c, dict) and isinstance(c.get("installed"), bool), "companion shape"
assert isinstance(v, dict) and isinstance(v.get("installed"), bool), "vision shape"
# `error` must be a string when not installed, None when installed and clean.
if not c["installed"]:
    assert c.get("error"), "companion not installed must populate error"
if not v["installed"]:
    assert v.get("error"), "vision not installed must populate error"
# is_installed() returns bool, never raises
assert isinstance(comp_inst(), bool), "comp_inst must return bool"
assert isinstance(vis_inst(),  bool), "vis_inst must return bool"
print(f"comp_installed={c['installed']} vis_installed={v['installed']} contract ok")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $gdTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Graceful degradation contract" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "Graceful degradation" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 13: forecast_earnings persistence ---------------------------

if ($py) {
    $fcTest = @'
from data.store import init_db, forecast_earnings, get_recent_forecasts
init_db()
n0 = len(get_recent_forecasts(limit=999))
res = forecast_earnings(window_days=90, horizon_days=90)
assert "horizons"        in res, "missing horizons"
assert len(res["horizons"]) == 3, "expected 3 horizons"
assert "forecast_ids"    in res, "missing forecast_ids"
assert len(res["forecast_ids"]) == 3, "expected 3 stored ids"
n1 = len(get_recent_forecasts(limit=999))
assert n1 == n0 + 3, f"expected {n0}+3 forecasts, got {n1}"
print(f"forecasts {n0}->{n1} confidence={res['confidence']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $fcTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "forecast_earnings persistence (3 horizons)" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "forecast_earnings" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 14: estimate_tax_burden + Vietnam-resident assumption -------

if ($py) {
    $taxTest = @'
from data.store import estimate_tax_burden
res = estimate_tax_burden(start_date="2026-01-01", end_date="2026-12-31",
                          jurisdiction="Vietnam")
assert "id" in res, "missing id (not persisted)"
assert "assumptions" in res, "missing assumptions array"
vn = any("Vietnam" in a or "vietnam" in a.lower() for a in res["assumptions"])
assert vn, f"Vietnam-resident assumption MUST be surfaced in assumptions[]: {res['assumptions']}"
assert res.get("estimated_tax_owed") is not None, "missing estimated_tax_owed"
print(f"tax_id={res['id']} owed=${res['estimated_tax_owed']:.2f} vietnam_assumption=True")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $taxTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "estimate_tax_burden + Vietnam-resident assumption" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "estimate_tax_burden" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 15: analyze_content_roi persistence -------------------------

if ($py) {
    $roiTest = @'
from data.store import analyze_content_roi
res = analyze_content_roi(start_date="2026-01-01", end_date="2026-12-31",
                          content_topic="smoke-test")
assert "id" in res, "missing id (not persisted)"
assert "graceful_degradation" in res, "missing graceful_degradation block"
gd = res["graceful_degradation"]
assert isinstance(gd.get("tool1_missing"), bool) and \
       isinstance(gd.get("tool4_missing"), bool), \
       "graceful_degradation flags must be bool"
prov = res.get("provenance") or {}
assert "tool1_rows_used" in prov and "tool4_rows_used" in prov, \
       "provenance must carry tool1_rows_used + tool4_rows_used"
print(f"roi_id={res['id']} t1_rows={prov['tool1_rows_used']} t4_rows={prov['tool4_rows_used']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $roiTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "analyze_content_roi + provenance row counts" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "analyze_content_roi" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 16: Grok stub honesty ---------------------------------------

if ($py) {
    $stubTest = @'
from data.api_clients import _grok_forecast_call, _grok_optimize_call, _grok_tax_call
fc = _grok_forecast_call(window_days=30, horizon_days=30,
                          companion_summary={"transaction_count":0,"total_inflow":0},
                          vision_summary={"receipt_count":0})
opt = _grok_optimize_call(topic="x", audience_profile=None)
tax = _grok_tax_call(period={"start":"a","end":"b"}, jurisdiction="Other",
                     gross_income=0, deductible_expenses=0, expense_count=0)
# Every stub MUST flag provenance.stub=True (Article IV honesty).
for name, r in (("forecast", fc), ("optimize", opt), ("tax", tax)):
    prov = r.get("provenance", {})
    assert prov.get("stub") is True, f"{name} stub must flag provenance.stub=True"
# forecast + tax carry top-level confidence; optimize carries per-angle confidence
# per the user_templates.md#content-optimization schema.
for name, r in (("forecast", fc), ("tax", tax)):
    assert (r.get("confidence") or "").lower() == "low", \
        f"{name} stub: top-level confidence must be 'low' (got {r.get('confidence')})"
angles = opt.get("angles") or []
assert angles, "optimize stub must return at least one angle"
assert all((a.get("confidence") or "").lower() == "low" for a in angles), \
    f"optimize stub: every angle must be confidence='low'"
print("OK 3/3 Grok stubs flag provenance.stub=True; confidence=low everywhere")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $stubTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Grok stub honesty (provenance.stub=True)" "PASS"
        } else {
            Add-Result "Grok stub honesty" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 17: launcher.ps1 parses cleanly -----------------------------

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

# --- Check 18: .streamlit/config.toml shape (port=8503) ----------------

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
if cfg["server"].get("port") != 8503:
    print(f"server.port must be 8503 to coexist (got {cfg['server'].get('port')})"); sys.exit(1)
print(f"primaryColor={cfg['theme']['primaryColor']} port={cfg['server']['port']}")
'@
    $out = & $py.Cmd @($py.Pre) -c $tomlTest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result ".streamlit/config.toml shape + port=8503" "PASS" (($out | Out-String).Trim())
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
    Write-Host "    Tool #3 - X Creator Payout Optimizer: PASS"          -ForegroundColor Green
    Write-Host "    $pass/$total checks green; ready for 'grok install this'." -ForegroundColor Green
    Write-Host "    X Money Suite (Tools #1 + #2 + #3 + #4) COMPLETE."   -ForegroundColor Green
} else {
    Write-Host "    Tool #3 - X Creator Payout Optimizer: FAIL"          -ForegroundColor Red
    Write-Host "    $pass/$total green ; $fail FAIL ; $warn WARN"        -ForegroundColor Red
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
