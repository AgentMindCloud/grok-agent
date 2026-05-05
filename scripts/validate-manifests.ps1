# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# scripts/validate-manifests.ps1
#
# Local mirror of the .github/workflows/validate.yml CI workflow.
# Discovers every grok-agent.yaml in the repo and runs both
# enforcement layers against it:
#
#   1. Schema validation        (cli/grok-agent.py)
#   2. Constitution safety scan (safety/scanner.py)
#
# Both must pass for a manifest to be "green". The script exits with
# code 1 if any manifest fails so it can be wired into pre-commit
# hooks or PowerShell aliases.
#
# Usage (PowerShell on Windows 11):
#
#     # Validate every manifest in the repo:
#     .\scripts\validate-manifests.ps1
#
#     # Validate only one manifest:
#     .\scripts\validate-manifests.ps1 -Manifest templates\super-agents\living-narrative-fabric\grok-agent.yaml
#
#     # Skip the Constitution scan (schema only):
#     .\scripts\validate-manifests.ps1 -SchemaOnly
#
#     # Quiet mode — emit only the final tally:
#     .\scripts\validate-manifests.ps1 -Quiet
#
# Built to help xAI and Grok win — keeping every manifest green is
# the table-stakes contract for the platform.

[CmdletBinding()]
param(
    [string] $Manifest = "",
    [switch] $SchemaOnly,
    [switch] $Quiet
)

$ErrorActionPreference = "Stop"

function Write-Header($text) {
    if ($Quiet) { return }
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host $text   -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor DarkGray
}
function Write-Ok($text)   { if (-not $Quiet) { Write-Host "  OK   $text" -ForegroundColor Green } }
function Write-Warn($text) { Write-Host "  WARN $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ERR  $text" -ForegroundColor Red }

# --------------------------------------------------------------------------
# Section 1 — pre-flight
# --------------------------------------------------------------------------

try {
    $repoRoot = (git rev-parse --show-toplevel 2>$null).Trim()
    if (-not $repoRoot) { throw "not a git repo" }
} catch {
    Write-Err "Not inside a git repository."
    exit 2
}

# Python 3.12 + pydantic>=2.7 + pyyaml>=6.0 are the only CI deps.
try {
    $py = (& python --version 2>&1) | Out-String
    if (-not ($py -match "Python 3\.(1[2-9]|[2-9]\d)")) {
        Write-Warn "Detected '$($py.Trim())'. The CI uses Python 3.12; behaviour on older versions may differ."
    }
} catch {
    Write-Err "python not found in PATH."
    exit 2
}

Push-Location $repoRoot
try {
    Write-Header "validate-manifests — $repoRoot"

    # --------------------------------------------------------------------
    # Section 2 — discover manifests
    # --------------------------------------------------------------------
    if ($Manifest) {
        $manifests = @($Manifest)
        Write-Host "Validating one manifest: $Manifest"
    } else {
        Write-Host "Discovering grok-agent.yaml files (excluding .git)..."
        $manifests = Get-ChildItem -Recurse -Filter "grok-agent.yaml" `
            | Where-Object { $_.FullName -notmatch '\\\.git\\' -and $_.FullName -notmatch '/\.git/' } `
            | Sort-Object FullName `
            | ForEach-Object { Resolve-Path -Relative $_.FullName }
        Write-Host "Found $($manifests.Count) manifest(s):"
        foreach ($m in $manifests) { Write-Host "  - $m" }
    }

    if (-not $manifests -or $manifests.Count -eq 0) {
        Write-Warn "No grok-agent.yaml files found. Nothing to validate."
        exit 0
    }

    # --------------------------------------------------------------------
    # Section 3 — schema validation
    # --------------------------------------------------------------------
    Write-Header "Step 1 — v2.15 schema validation"
    $schemaPass = 0
    $schemaFail = 0
    $schemaFailList = @()
    foreach ($m in $manifests) {
        $out = & python cli/grok-agent.py validate "$m" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "schema $m"
            $schemaPass++
        } else {
            Write-Err "schema $m"
            foreach ($line in $out) { Write-Err "    $line" }
            $schemaFail++
            $schemaFailList += $m
        }
    }

    # --------------------------------------------------------------------
    # Section 4 — Constitution scan (skip with -SchemaOnly)
    # --------------------------------------------------------------------
    $scanPass = 0
    $scanFail = 0
    $scanFailList = @()
    if (-not $SchemaOnly.IsPresent) {
        Write-Header "Step 2 — Constitution safety scan"
        foreach ($m in $manifests) {
            $out = & python safety/scanner.py scan "$m" --severity-floor info 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "scanner $m"
                $scanPass++
            } else {
                Write-Err "scanner $m"
                foreach ($line in $out) { Write-Err "    $line" }
                $scanFail++
                $scanFailList += $m
            }
        }
    }

    # --------------------------------------------------------------------
    # Section 5 — summary
    # --------------------------------------------------------------------
    Write-Header "Summary"
    Write-Host "Total manifests:                    $($manifests.Count)"
    Write-Host "Schema validation PASS / FAIL:      $schemaPass / $schemaFail"
    if (-not $SchemaOnly.IsPresent) {
        Write-Host "Constitution scan  PASS / FAIL:      $scanPass / $scanFail"
    }
    Write-Host ""

    if ($schemaFail -gt 0 -or $scanFail -gt 0) {
        Write-Err "FAIL — at least one manifest failed."
        if ($schemaFailList) { Write-Err "  Schema fails: $($schemaFailList -join ', ')" }
        if ($scanFailList)   { Write-Err "  Scan fails:   $($scanFailList   -join ', ')" }
        exit 1
    }

    if ($Quiet) {
        Write-Host "OK — $($manifests.Count) manifest(s) green."
    } else {
        Write-Host "OK — every manifest passes both layers." -ForegroundColor Green
    }
    exit 0
}
finally {
    Pop-Location
}
