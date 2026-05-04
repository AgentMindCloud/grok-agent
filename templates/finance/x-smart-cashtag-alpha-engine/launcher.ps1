# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — one-click Windows launcher for the
# X Smart Cashtag Alpha Engine.
#
# QUICK START
# -----------
# From Windows PowerShell, in this folder:
#
#   .\launcher.ps1
#
# Via the Grok Agent OS CLI:
#
#   grok-agent install x-smart-cashtag-alpha-engine
#   grok-agent run     x-smart-cashtag-alpha-engine
#
# X-native shorthand (in a tweet or DM that mentions @grok):
#
#   grok install this
#
# Optional flags:
#   -Port <int>     Port to run Streamlit on (default 8502 — leaves 8501 for Tool #1)
#   -NoBrowser      Don't auto-open a browser tab
#   -SkipDeps       Skip the `pip install -r requirements.txt` step
#
# WHAT IT DOES
# ------------
# 1. Resolves Python 3.12+ (tries `python` then `py -3`).
# 2. Installs pinned dependencies from requirements.txt (idempotent).
# 3. Creates the AppData folder
#    $env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine
#    if missing, and initialises the SQLite schema via data.store.init_db().
# 4. Launches Streamlit headless on http://localhost:<Port> and opens
#    the URL in your default browser (unless -NoBrowser).
#
# Constitution Articles II + V apply: this engine watches but never posts
# to X (`posts: false` in the manifest is binding), and surfaces NOT
# FINANCIAL ADVICE / NOT TAX ADVICE banners on every screen. The launcher
# itself only sets up + starts the app — it never moves money or tweets.

#requires -Version 5.1

[CmdletBinding()]
param(
    [int]$Port = 8502,
    [switch]$NoBrowser,
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------

function Show-Banner {
    Write-Host ""
    Write-Host "  =====================================================" -ForegroundColor DarkCyan
    Write-Host "    X Smart Cashtag Alpha Engine"                         -ForegroundColor Cyan
    Write-Host "    Cashtag-aware market intelligence for X."             -ForegroundColor DarkCyan
    Write-Host "    Built to help xAI and Grok win."                      -ForegroundColor DarkCyan
    Write-Host "    Watches but never posts. (posts: false)"              -ForegroundColor DarkCyan
    Write-Host "  =====================================================" -ForegroundColor DarkCyan
    Write-Host ""
    Write-Host "  !  NOT financial advice. NOT tax advice."               -ForegroundColor Yellow
    Write-Host "     Constitution v1.0 Articles II + V apply."            -ForegroundColor DarkYellow
    Write-Host ""
}

Show-Banner

# ---------------------------------------------------------------------
# Python 3.12+ detection (python, then py -3)
# ---------------------------------------------------------------------

function Resolve-Python {
    $candidates = @(
        @{ Cmd = "python"; Pre = @() },
        @{ Cmd = "py";     Pre = @("-3") }
    )
    foreach ($c in $candidates) {
        try {
            $verOut = & $c.Cmd @($c.Pre) --version 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0 -and $verOut -match "Python 3\.(\d+)") {
                if ([int]$Matches[1] -ge 12) {
                    return [PSCustomObject]@{
                        Cmd     = $c.Cmd
                        Pre     = $c.Pre
                        Version = $verOut.Trim()
                    }
                }
            }
        } catch { }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Host "  X  Python 3.12+ not found." -ForegroundColor Red
    Write-Host "     Install from https://www.python.org/downloads/ and re-run." -ForegroundColor DarkGray
    exit 1
}
Write-Host "  +  $($py.Version)" -ForegroundColor Green

# ---------------------------------------------------------------------
# Dependencies (idempotent)
# ---------------------------------------------------------------------

if (-not $SkipDeps) {
    $reqFile = Join-Path $scriptDir "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        Write-Host "  X  requirements.txt missing at $reqFile" -ForegroundColor Red
        exit 1
    }
    Write-Host "  >  Verifying dependencies..." -ForegroundColor Yellow
    & $py.Cmd @($py.Pre) -m pip install --quiet -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  X  pip install failed. See output above." -ForegroundColor Red
        exit 1
    }
    Write-Host "  +  Dependencies ready" -ForegroundColor Green
} else {
    Write-Host "  ~  Skipped dependency check (-SkipDeps)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# AppData folder + SQLite schema (idempotent)
# ---------------------------------------------------------------------

if (-not $env:LOCALAPPDATA) {
    Write-Host "  X  `$env:LOCALAPPDATA is not set. Are you on Windows?" -ForegroundColor Red
    exit 1
}

$appData = Join-Path $env:LOCALAPPDATA "grok-agent\x-smart-cashtag-alpha-engine"
if (-not (Test-Path $appData)) {
    New-Item -Path $appData -ItemType Directory -Force | Out-Null
    Write-Host "  +  Created AppData : $appData" -ForegroundColor Green
} else {
    Write-Host "  +  AppData         : $appData" -ForegroundColor Green
}

Push-Location $scriptDir
try {
    & $py.Cmd @($py.Pre) -c "from data.store import init_db; print('  +  SQLite ready    :', init_db())"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  X  Failed to initialise SQLite. See traceback above." -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------
# Launch Streamlit (always headless; we manage the browser ourselves)
# ---------------------------------------------------------------------

$url = "http://localhost:$Port"
Write-Host ""
Write-Host "  >  Launching at $url"            -ForegroundColor Yellow
Write-Host "     Press Ctrl+C in this window to stop." -ForegroundColor DarkGray
Write-Host ""

if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($u) Start-Sleep -Seconds 3 ; Start-Process $u -ErrorAction SilentlyContinue
    } -ArgumentList $url | Out-Null
}

# Constitution Article VII: gatherUsageStats stays off.
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

Push-Location $scriptDir
try {
    & $py.Cmd @($py.Pre) -m streamlit run "app.py" `
        --server.port     $Port `
        --server.headless true
} finally {
    Pop-Location
}
