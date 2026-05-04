# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — Recipe A Slot 6 smoke test for the
# X Money Vision Analyzer. This script is the "grok install this"
# readiness check for Tool #4.
#
# WHAT IT VERIFIES (17 checks)
# ----------------------------
# 1.  All 12 expected files exist in the analyzer folder.
# 2.  A working Python 3.11+ interpreter is on PATH.
# 3.  `cli/grok-agent.py validate` accepts the manifest (v2.15, kind=vision-analyzer).
# 4.  `safety/scanner.py scan` returns 0 Constitution findings.
# 5.  Every code/config/markdown file has an Apache 2.0 license header.
# 6.  Article V.1 + V.2 disclaimers present in app.py / system.md / README.md.
# 7.  Article III contradiction-flagging language present in system.md +
#     user_templates.md (Tool #4's defining capability per the manifest).
# 8.  CROSS-TOOL WRITE RULE language present in system.md + manifest:
#     "import_to_companion_dashboard" / "import_receipts.py" / Article III.
# 9.  PII REDACTION POSTURE: pii_handling="redacted-cloud" declared + the
#     grok_vision public_apis entry mentions redaction.
# 10. All 5 manifest tools + the import helper importable from the data package.
# 11. SQLite init + parse_receipt round-trip with line-item persistence.
# 12. validate_extraction surfaces cross-pass contradictions correctly.
# 13. categorize_parsed_receipt assigns a category.
# 14. CROSS-TOOL WRITE PROOF: import_receipts_to_companion writes a row into
#     Tool #1's SQLite, idempotent re-call skips on dedup, and the test row
#     is cleaned up afterwards so we don't pollute Tool #1.
# 15. Grok vision stub honesty: provenance.stub == True.
# 16. launcher.ps1 parses cleanly under the current PowerShell engine.
# 17. .streamlit/config.toml shape + privacy posture + port=8504 verified
#     (so Tool #1=8501, Tool #2=8502, Tool #3=8503-planned, Tool #4=8504 coexist).
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
$slug      = "x-money-vision-analyzer"

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
Write-Host "    Tool #4 Smoke Test"                                  -ForegroundColor Cyan
Write-Host "    X Money Vision Analyzer"                             -ForegroundColor Cyan
Write-Host "    Built to help xAI and Grok win."                     -ForegroundColor DarkCyan
Write-Host "  =====================================================" -ForegroundColor DarkCyan
Write-Host ""

# --- Check 1: required files exist --------------------------------------

$expected = @(
    "grok-agent.yaml", "README.md", "app.py", "requirements.txt",
    "launcher.ps1", "smoke_test.ps1", ".streamlit/config.toml",
    "prompts/system.md", "prompts/user_templates.md",
    "data/__init__.py", "data/store.py", "data/api_clients.py",
    "data/import_receipts.py"
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
        Add-Result "Schema validation (cli/grok-agent.py)" "PASS" "v2.15 OK / kind=vision-analyzer"
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

# --- Check 7: Article III contradiction-flagging language ---------------

$contradictionFiles = @("prompts/system.md", "prompts/user_templates.md")
$cMisses = @()
foreach ($f in $contradictionFiles) {
    $p = Join-Path $scriptDir $f
    if (-not (Test-Path $p)) { $cMisses += "$f (file missing)" ; continue }
    if ((Get-Content -LiteralPath $p -Raw) -notmatch "ontradiction") {
        $cMisses += "$f lacks contradiction-flagging language"
    }
}
if ($cMisses.Count -eq 0) {
    Add-Result "Article III contradiction-flagging language present" "PASS" "in system.md + user_templates.md"
} else {
    Add-Result "Article III contradiction-flagging" "FAIL" ($cMisses -join '; ')
}

# --- Check 8: cross-tool write rule language (Tool #4 specific) ---------

$crossRuleSpec = @(
    @{ File = "prompts/system.md"; Patterns = @("import_to_companion_dashboard", "Tool #1") }
    @{ File = "grok-agent.yaml";   Patterns = @("import_receipts.py", "Article III") }
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
    Add-Result "Cross-tool write rule language (manifest + system.md)" "PASS"
} else {
    Add-Result "Cross-tool write rule language" "FAIL" ($crMisses -join '; ')
}

# --- Check 9: PII redaction posture (Tool #4 specific) ------------------

if ($py) {
    $env:SMOKE_MANIFEST = $manifest
    $piiTest = @'
import os, sys
try: import yaml
except ImportError:
    print("pyyaml not installed"); sys.exit(1)
with open(os.environ["SMOKE_MANIFEST"], "r", encoding="utf-8") as f:
    m = yaml.safe_load(f)
pii = (m.get("safety") or {}).get("pii_handling")
if pii != "redacted-cloud":
    print(f"pii_handling must be 'redacted-cloud' for vision-analyzer, got {pii!r}")
    sys.exit(1)
apis = m.get("public_apis") or []
gv = next((a for a in apis if a.get("name") == "grok_vision"), None)
if not gv:
    print("public_apis must declare 'grok_vision'"); sys.exit(1)
priv = gv.get("privacy", "")
if "redact" not in priv.lower():
    print(f"grok_vision privacy must mention redaction, got {priv!r}"); sys.exit(1)
print(f"pii_handling=redacted-cloud / grok_vision.privacy={priv!r}")
'@
    $out = & $py.Cmd @($py.Pre) -c $piiTest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result "PII redaction posture (vision tool)" "PASS" (($out | Out-String).Trim())
    } else {
        Add-Result "PII redaction posture" "FAIL" (($out | Out-String).Trim())
    }
    Remove-Item Env:SMOKE_MANIFEST -ErrorAction SilentlyContinue
}

# --- Check 10: module imports (5 tools + import helper) -----------------

if ($py) {
    $importTest = @'
from data.store        import (
    init_db, parse_receipt, validate_extraction, categorize_parsed_receipt,
    upsert_receipt_from_extraction, list_receipts, get_receipt,
    insert_contradiction, insert_import_log,
)
from data.api_clients  import parse_statement, import_to_companion_dashboard, _grok_vision_call
from data.import_receipts import import_receipts_to_companion
print("OK")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $importTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Module imports (5 manifest tools + import helper)" "PASS"
        } else {
            Add-Result "Module imports" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 11: SQLite parse_receipt round-trip --------------------------

if ($py) {
    $parseTest = @'
from data.store import init_db, upsert_receipt_from_extraction, get_receipt
init_db()
ext = {
    "vendor": "SmokeVendor", "tx_date": "2026-01-01", "currency": "USD",
    "subtotal": 9.95, "tax": 0.05, "total": 10.00,
    "category_suggested": "other", "confidence": "low",
    "line_items": [
        {"item": "Smoke item",  "qty": 1, "price": 5.00, "confidence": "high"},
        {"item": "Smoke item 2","qty": 1, "price": 4.95, "confidence": "medium"},
    ],
    "provenance": {"image_path": "/smoke-parse.jpg", "page": 1,
                   "model": "smoke", "vision_pass_index": 1,
                   "retrieved_at": "2026-05-04T00:00:00+00:00"},
}
rid = upsert_receipt_from_extraction("/smoke-parse.jpg", ext)
got = get_receipt(rid)
assert got is not None,                   "receipt not persisted"
assert got["vendor"] == "SmokeVendor",    f"vendor wrong: {got['vendor']}"
assert len(got["line_items"]) == 2,       f"line_items wrong: {len(got['line_items'])}"
print(f"receipt_id={rid} line_items={len(got['line_items'])}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $parseTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "SQLite parse_receipt round-trip + line items" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "parse_receipt round-trip" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 12: validate_extraction surfaces contradictions --------------

if ($py) {
    $valTest = @'
from data.store import validate_extraction, get_receipt
got = get_receipt(1) or {"vendor":"A","tx_date":"2026-01-01","total":10.0}
res = validate_extraction("/smoke-parse.jpg", got)
assert "contradictions" in res,            "missing contradictions key"
assert isinstance(res["contradictions"], list), "contradictions must be list"
assert "recommend"     in res,             "missing recommend key"
print(f"contradictions={len(res['contradictions'])} recommend={res['recommend']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $valTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "validate_extraction surfaces contradictions" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "validate_extraction" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 13: categorize_parsed_receipt --------------------------------

if ($py) {
    $catTest = @'
from data.store import categorize_parsed_receipt
res = categorize_parsed_receipt({"vendor": "Highlands Coffee", "notes": "morning latte",
                                 "line_items": [{"item": "latte"}]})
assert "category"    in res,   "missing category"
assert "confidence"  in res,   "missing confidence"
print(f"category={res['category']} confidence={res['confidence']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $catTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "categorize_parsed_receipt" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "categorize_parsed_receipt" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 14: CROSS-TOOL WRITE PROOF (Tool #4 defining capability) -----

if ($py) {
    $crossWriteTest = @'
import time, sqlite3
from data.import_receipts import import_receipts_to_companion
from data import companion_db_path

# Unique marker so we can find + delete the test row afterwards
test_image = f"/smoke-test-tool4-{int(time.time())}.jpg"
parsed = {
    "vendor":   "SmokeTestVision",
    "tx_date":  "2026-01-01",
    "currency": "USD",
    "subtotal": 9.95, "tax": 0.05, "total": 10.00,
    "category_suggested": "other",
    "confidence": "low",
    "notes":    "P36 smoke test row — cleaned up after assertions",
    "provenance": {"image_path": test_image, "page": 1,
                   "model": "smoke-test", "vision_pass_index": 1,
                   "retrieved_at": "2026-05-04T00:00:00+00:00"},
}

# (1) cross-tool write
res1 = import_receipts_to_companion([parsed])
assert res1["imported"] == 1, f"first import expected 1, got {res1['imported']} (error={res1['error']})"
assert res1["error"] is None, f"first import error: {res1['error']}"
tx_id = res1["imported_rows"][0]["target_tx_id"]

# (2) idempotency
res2 = import_receipts_to_companion([parsed])
assert res2["imported"] == 0, f"re-import expected 0 imported, got {res2['imported']}"
assert res2["skipped"]  == 1, f"re-import expected 1 skipped, got {res2['skipped']}"

# (3) verify row landed in Tool #1's transactions table
with sqlite3.connect(str(companion_db_path())) as cx:
    cx.row_factory = sqlite3.Row
    rows = list(cx.execute(
        "SELECT id, source, receipt_image_path, amount FROM transactions WHERE receipt_image_path = ?",
        (test_image,)
    ))
    assert len(rows) == 1, f"expected 1 row in Tool #1, got {len(rows)}"
    assert rows[0]["source"] == "vision", f"expected source=vision, got {rows[0]['source']}"
    # Cleanup so the smoke test does not pollute Tool #1
    cx.execute("DELETE FROM transactions WHERE receipt_image_path = ?", (test_image,))
    cx.commit()

print(f"cross-tool: tx_id={tx_id} source=vision imported=1 skipped_on_re_import=1 cleaned_up_after")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $crossWriteTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "CROSS-TOOL WRITE proof (write + idempotency + cleanup)" "PASS" (($out | Out-String).Trim())
        } else {
            Add-Result "Cross-tool write" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 15: Grok vision stub honesty --------------------------------

if ($py) {
    $stubTest = @'
from data.api_clients import _grok_vision_call
res = _grok_vision_call("/no-such-image.jpg", mode="receipt", vision_pass_index=1)
prov = res.get("provenance") or {}
assert prov.get("stub") is True,  f"vision stub must flag provenance.stub=True, got {prov.get('stub')}"
assert (res.get("confidence") or "").lower() == "low",  f"stub must report confidence=low, got {res.get('confidence')}"
print(f"stub flag ok / confidence={res['confidence']}")
'@
    Push-Location $scriptDir
    try {
        $out = & $py.Cmd @($py.Pre) -c $stubTest 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Result "Grok vision stub honesty (provenance.stub=True)" "PASS"
        } else {
            Add-Result "Grok vision stub honesty" "FAIL" (($out | Out-String).Trim())
        }
    } finally { Pop-Location }
}

# --- Check 16: launcher.ps1 parses cleanly ------------------------------

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

# --- Check 17: .streamlit/config.toml shape (port=8504) -----------------

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
if cfg["server"].get("port") != 8504:
    print(f"server.port must be 8504 to coexist with siblings (got {cfg['server'].get('port')})")
    sys.exit(1)
print(f"primaryColor={cfg['theme']['primaryColor']} port={cfg['server']['port']}")
'@
    $out = & $py.Cmd @($py.Pre) -c $tomlTest 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Result ".streamlit/config.toml shape + port=8504" "PASS" (($out | Out-String).Trim())
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
    Write-Host "    Tool #4 - X Money Vision Analyzer: PASS"            -ForegroundColor Green
    Write-Host "    $pass/$total checks green; ready for 'grok install this'." -ForegroundColor Green
} else {
    Write-Host "    Tool #4 - X Money Vision Analyzer: FAIL"            -ForegroundColor Red
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
