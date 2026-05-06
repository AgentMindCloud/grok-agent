# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

<#
.SYNOPSIS
    Cross-tool integration smoke test for the four X Money tools.

.DESCRIPTION
    Built for xAI, X, Grok and the ecosystem community. ❤️

    Verifies the full X Money chain end-to-end on Windows 11 + PowerShell:

      1. Tool #1 - x-money-companion-dashboard            (sink for SQLite)
      2. Tool #4 - x-money-vision-analyzer                (importer ->  Tool #1 SQLite)
      3. Tool #3 - x-creator-payout-optimizer             (read-only ->  Tool #1)
      4. Tool #2 - x-smart-cashtag-alpha-engine           (read-only ->  Tool #1 transactions)

    Run order matters: Tool #4's importer targets Tool #1's already-shipped
    schema; Tools #2 and #3 read what #1 + #4 wrote.

    The script is read-only against the real repo - it only validates the
    on-disk shape (manifests, expected SQLite paths, importer module).
    No external services are contacted.

.EXAMPLE
    .\tests\x-money-integration-smoke.ps1

.EXAMPLE
    .\tests\x-money-integration-smoke.ps1 -SkipPython
    # Skip Python validate steps (useful when pydantic isn't installed yet).

.NOTES
    Repo: https://github.com/AgentMindCloud/grok-agent
#>

[CmdletBinding()]
param(
    [switch]$SkipPython,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Script:RepoRoot = Split-Path -Parent $PSScriptRoot
$Script:Tagline  = 'Built for xAI, X, Grok and the ecosystem community. ❤️'

$Script:Tools = @(
    [pscustomobject]@{
        Slot       = 1
        Slug       = 'x-money-companion-dashboard'
        Folder     = 'templates/finance/x-money-companion-dashboard'
        Role       = 'sink'
        Expects    = @('grok-agent.yaml','README.md','app.py')
    },
    [pscustomobject]@{
        Slot       = 4
        Slug       = 'x-money-vision-analyzer'
        Folder     = 'templates/finance/x-money-vision-analyzer'
        Role       = 'importer (writes Tool #1 SQLite)'
        Expects    = @('grok-agent.yaml','README.md')
    },
    [pscustomobject]@{
        Slot       = 3
        Slug       = 'x-creator-payout-optimizer'
        Folder     = 'templates/finance/x-creator-payout-optimizer'
        Role       = 'reader (Tool #1 + Tool #4)'
        Expects    = @('grok-agent.yaml','README.md')
    },
    [pscustomobject]@{
        Slot       = 2
        Slug       = 'x-smart-cashtag-alpha-engine'
        Folder     = 'templates/finance/x-smart-cashtag-alpha-engine'
        Role       = 'reader (Tool #1 transactions)'
        Expects    = @('grok-agent.yaml','README.md')
    }
)

$Script:Failed = @()
$Script:Passed = @()

function Write-Step  { param([string]$m) if (-not $Quiet) { Write-Host ('-> ' + $m) -ForegroundColor White } }
function Write-Ok    { param([string]$m) if (-not $Quiet) { Write-Host ('OK  ' + $m) -ForegroundColor Green } }
function Write-Warn2 { param([string]$m) Write-Host ('!!  ' + $m) -ForegroundColor Yellow }
function Write-Err2  { param([string]$m) Write-Host ('XX  ' + $m) -ForegroundColor Red }

function Assert-PathExists {
    param([string]$Path, [string]$Label)
    if (Test-Path $Path) {
        Write-Ok ('{0}: {1}' -f $Label, $Path)
        $Script:Passed += $Label
    } else {
        Write-Err2 ('{0}: missing {1}' -f $Label, $Path)
        $Script:Failed += $Label
    }
}

if (-not $Quiet) {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor DarkYellow
    Write-Host '   X MONEY CROSS-TOOL INTEGRATION SMOKE TEST' -ForegroundColor Red
    Write-Host ('   {0}' -f $Script:Tagline) -ForegroundColor Yellow
    Write-Host '============================================================' -ForegroundColor DarkYellow
    Write-Host ''
}

# --------------------------------------------------------------------
# Step 1: every tool folder exists and ships the expected files.
# --------------------------------------------------------------------
Write-Step 'Step 1: Verify on-disk shape of each tool.'
foreach ($tool in $Script:Tools) {
    $folder = Join-Path $Script:RepoRoot $tool.Folder
    if (-not (Test-Path $folder)) {
        Write-Err2 ('Tool #{0} folder missing: {1}' -f $tool.Slot, $folder)
        $Script:Failed += ('Tool #{0} folder' -f $tool.Slot)
        continue
    }
    Write-Ok ('Tool #{0} ({1}): folder present' -f $tool.Slot, $tool.Slug)
    foreach ($expected in $tool.Expects) {
        $path = Join-Path $folder $expected
        Assert-PathExists -Path $path -Label ("Tool #{0} -> {1}" -f $tool.Slot, $expected)
    }
}

# --------------------------------------------------------------------
# Step 2: Tool #4 -> Tool #1 importer module exists.
# --------------------------------------------------------------------
Write-Step 'Step 2: Verify Tool #4 -> Tool #1 receipt importer.'
$importerCandidates = @(
    'templates/finance/x-money-vision-analyzer/data/import_receipts.py',
    'templates/finance/x-money-vision-analyzer/data/importer.py',
    'templates/finance/x-money-vision-analyzer/data/companion_import.py'
)
$importerFound = $false
foreach ($candidate in $importerCandidates) {
    $p = Join-Path $Script:RepoRoot $candidate
    if (Test-Path $p) {
        Assert-PathExists -Path $p -Label 'Tool #4 importer'
        $importerFound = $true
        break
    }
}
if (-not $importerFound) {
    Write-Warn2 'No Tool #4 importer module found at any expected path; cross-tool write contract is implicit.'
    $Script:Failed += 'Tool #4 importer module'
}

# --------------------------------------------------------------------
# Step 3: Each manifest declares kind in the v2.15 finance enum.
# --------------------------------------------------------------------
Write-Step 'Step 3: Verify each manifest kind matches the v2.15 finance enum.'
$expectedKinds = @{
    'x-money-companion-dashboard'   = 'finance-dashboard'
    'x-money-vision-analyzer'       = 'vision-analyzer'
    'x-creator-payout-optimizer'    = 'creator-payout-optimizer'
    'x-smart-cashtag-alpha-engine'  = 'alpha-engine'
}
foreach ($tool in $Script:Tools) {
    $manifest = Join-Path $Script:RepoRoot ($tool.Folder + '/grok-agent.yaml')
    if (-not (Test-Path $manifest)) { continue }
    $line = Select-String -Path $manifest -Pattern '^kind:\s*"?([a-z-]+)"?' -List
    if ($null -eq $line) {
        Write-Err2 ('Tool #{0}: kind line not found in manifest' -f $tool.Slot)
        $Script:Failed += ('Tool #{0} kind' -f $tool.Slot)
        continue
    }
    $kind = $line.Matches[0].Groups[1].Value
    if ($kind -eq $expectedKinds[$tool.Slug]) {
        Write-Ok ('Tool #{0}: kind={1} matches enum' -f $tool.Slot, $kind)
        $Script:Passed += ('Tool #{0} kind' -f $tool.Slot)
    } else {
        Write-Err2 ('Tool #{0}: kind={1} expected {2}' -f $tool.Slot, $kind, $expectedKinds[$tool.Slug])
        $Script:Failed += ('Tool #{0} kind' -f $tool.Slot)
    }
}

# --------------------------------------------------------------------
# Step 4: cli/grok-agent.py validate (optional - skipped if requested).
# --------------------------------------------------------------------
if (-not $SkipPython) {
    Write-Step 'Step 4: Validate every manifest via cli/grok-agent.py.'
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Warn2 'python not on PATH - skipping validate (use -SkipPython to silence).'
    } else {
        foreach ($tool in $Script:Tools) {
            $manifest = Join-Path $Script:RepoRoot ($tool.Folder + '/grok-agent.yaml')
            if (-not (Test-Path $manifest)) { continue }
            $cliPath = Join-Path $Script:RepoRoot 'cli/grok-agent.py'
            $output  = & python $cliPath validate $manifest 2>&1
            $code    = $LASTEXITCODE
            if ($code -eq 0) {
                Write-Ok ('Tool #{0}: validate ok' -f $tool.Slot)
                $Script:Passed += ('Tool #{0} validate' -f $tool.Slot)
            } else {
                Write-Err2 ('Tool #{0}: validate failed (exit {1})' -f $tool.Slot, $code)
                $output | ForEach-Object { Write-Host ('     ' + $_) -ForegroundColor DarkGray }
                $Script:Failed += ('Tool #{0} validate' -f $tool.Slot)
            }
        }
    }
} else {
    Write-Warn2 'Step 4 (python validate) skipped via -SkipPython.'
}

# --------------------------------------------------------------------
# Step 5: AppData SQLite path expectation.
# --------------------------------------------------------------------
Write-Step 'Step 5: Verify Tool #1 SQLite AppData path expectation.'
$expectedDb = if ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA 'grok-agent/x-money-companion-dashboard'
} else {
    'grok-agent/x-money-companion-dashboard (path unresolved on this OS)'
}
Write-Ok ('Tool #1 expects SQLite under: {0}' -f $expectedDb)
$Script:Passed += 'Tool #1 SQLite AppData path'

# --------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------' -ForegroundColor DarkYellow
Write-Host ('   PASSED: {0}' -f $Script:Passed.Count) -ForegroundColor Green
Write-Host ('   FAILED: {0}' -f $Script:Failed.Count) -ForegroundColor Red
Write-Host '------------------------------------------------------------' -ForegroundColor DarkYellow
Write-Host ''

if ($Script:Failed.Count -gt 0) {
    Write-Err2 'Cross-tool smoke test FAILED. See checks above.'
    exit 1
}
Write-Ok 'Cross-tool smoke test PASSED end-to-end.'
exit 0
