# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — Windows 11 + PowerShell launcher for the
# Creator Agent Program outreach tracker and weekly report.

<#
.SYNOPSIS
  Creator Agent Program — outreach tracker + weekly report launcher.

.DESCRIPTION
  Thin Windows-native wrapper around outreach-tracker.py and weekly-report.py.
  Stores all data under $env:LOCALAPPDATA\grok-agent\creator-program\. No data
  leaves your machine.

.PARAMETER Action
  One of:
    log       — log a new outreach (passes through extra args to the tracker)
    respond   — mark an outreach as responded
    deliver   — mark an agent as delivered
    decline   — mark an outreach as declined
    list      — list all outreach
    stats     — print live stats
    report    — render this week's report to stdout
    report-7  — render the last-7-days report to a dated file
    report-30 — render the last-30-days report to a dated file
    open-dir  — open the AppData folder in Explorer

.EXAMPLE
  .\launcher.ps1 log --handle JanSol0s --niche "ai-agents" --followers 12500 `
    --template content-idea-generator --consent

.EXAMPLE
  .\launcher.ps1 stats

.EXAMPLE
  .\launcher.ps1 report-7

.NOTES
  Reminder: every monetization-optimizer delivery DM must include
  "Not financial advice. Not tax advice. Vietnam-resident creators with
  international platform earnings — consult a licensed local advisor."
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('log','respond','deliver','decline','list','stats','report','report-7','report-30','open-dir')]
    [string] $Action,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Rest
)

$ErrorActionPreference = 'Stop'

# Resolve script-local Python files (no install needed; run from repo).
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tracker     = Join-Path $ScriptDir 'outreach-tracker.py'
$Report      = Join-Path $ScriptDir 'weekly-report.py'

# AppData paths — match outreach-tracker.py exactly.
$AppDataDir  = Join-Path $env:LOCALAPPDATA 'grok-agent\creator-program'
$ReportDir   = Join-Path $AppDataDir 'reports'

if (-not (Test-Path $Tracker)) { throw "Missing: $Tracker" }
if (-not (Test-Path $Report))  { throw "Missing: $Report"  }

# Ensure Python 3 is available.
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    throw "Python 3 is required. Install Python 3.12 from python.org and re-run."
}

function Invoke-Tracker {
    param([string[]] $Args)
    & $python.Source $Tracker @Args
    if ($LASTEXITCODE -ne 0) {
        throw "outreach-tracker.py exited with code $LASTEXITCODE"
    }
}

function Invoke-Report {
    param([string[]] $Args)
    & $python.Source $Report @Args
    if ($LASTEXITCODE -ne 0) {
        throw "weekly-report.py exited with code $LASTEXITCODE"
    }
}

switch ($Action) {
    'log'       { Invoke-Tracker -Args (@('log')       + $Rest) }
    'respond'   { Invoke-Tracker -Args (@('respond')   + $Rest) }
    'deliver'   { Invoke-Tracker -Args (@('deliver')   + $Rest) }
    'decline'   { Invoke-Tracker -Args (@('decline')   + $Rest) }
    'list'      { Invoke-Tracker -Args @('list') }
    'stats'     { Invoke-Tracker -Args @('stats') }

    'report'    { Invoke-Report -Args @('--days', '7') }

    'report-7' {
        New-Item -Path $ReportDir -ItemType Directory -Force | Out-Null
        $stamp = Get-Date -Format 'yyyy-MM-dd'
        $out   = Join-Path $ReportDir ("weekly-report-7d-$stamp.md")
        Invoke-Report -Args @('--days', '7', '--out', $out)
        Write-Host "Wrote $out"
    }

    'report-30' {
        New-Item -Path $ReportDir -ItemType Directory -Force | Out-Null
        $stamp = Get-Date -Format 'yyyy-MM-dd'
        $out   = Join-Path $ReportDir ("weekly-report-30d-$stamp.md")
        Invoke-Report -Args @('--days', '30', '--out', $out)
        Write-Host "Wrote $out"
    }

    'open-dir' {
        New-Item -Path $AppDataDir -ItemType Directory -Force | Out-Null
        Start-Process explorer.exe $AppDataDir
    }
}
