# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# scripts/diagnose-branches.ps1
#
# Cross-Reality Action Fabric / Grok Agent OS — branch health diagnostic.
#
# Lists every local + remote branch, shows last-commit metadata, classifies
# each branch as MERGED (safe to delete) or UNIQUE (has unmerged work),
# checks for branches that share a tip SHA (true duplicates), and explains
# why `main` may look "old" relative to active feature branches.
#
# Default mode is read-only (REPORT). Pass `-Apply` to actually delete
# branches that the script classifies as MERGED. The script NEVER deletes:
#   - main
#   - the currently-checked-out branch
#   - any branch that has commits not present in main
#
# Built for xAI, X, Grok and the ecosystem community — keeping the repo's branch list honest is
# part of running an OS-grade agent platform on X.
#
# Usage (PowerShell on Windows 11):
#
#     # Read-only diagnostic (the safe default):
#     .\scripts\diagnose-branches.ps1
#
#     # Actually delete remote+local branches that classify as MERGED:
#     .\scripts\diagnose-branches.ps1 -Apply
#
#     # Local-only deletion (don't touch the remote):
#     .\scripts\diagnose-branches.ps1 -Apply -LocalOnly
#
#     # Compare against a different base (e.g. a release branch):
#     .\scripts\diagnose-branches.ps1 -Base "release/v1"
#
# Exit codes:
#   0  — clean (no branches needed deletion, or all deletions succeeded)
#   1  — at least one deletion failed (network / permission / non-fast-forward)
#   2  — pre-flight check failed (not in a git repo, base branch missing, or similar)

[CmdletBinding()]
param(
    [string] $Base       = "main",
    [string] $RemoteName = "origin",
    [switch] $Apply,
    [switch] $LocalOnly,
    [switch] $Quiet
)

# --------------------------------------------------------------------------
# Section 1 — pre-flight
# --------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

function Write-Header($text) {
    if ($Quiet) { return }
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host $text   -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor DarkGray
}

function Write-Info($text) {
    if (-not $Quiet) { Write-Host $text }
}

function Write-Ok($text)   { Write-Host "  OK    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  WARN  $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ERR   $text" -ForegroundColor Red }

# Confirm we're inside a git working tree.
try {
    $null = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) { throw "not a git repo" }
} catch {
    Write-Err "Not inside a git repository. Run this script from the repo root."
    exit 2
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
$current  = (git rev-parse --abbrev-ref HEAD).Trim()

Write-Header "Branch diagnostic — $repoRoot"
Write-Info "Base branch:        $Base"
Write-Info "Remote name:        $RemoteName"
Write-Info "Current branch:     $current"
Write-Info "Apply mode:         $($Apply.IsPresent)"
Write-Info "Local-only mode:    $($LocalOnly.IsPresent)"
Write-Info ""

# --------------------------------------------------------------------------
# Section 2 — fetch latest remote refs
# --------------------------------------------------------------------------

Write-Header "Step 1 — fetch + prune"
& git fetch --all --prune 2>&1 | ForEach-Object { Write-Info "  $_" }

# Confirm Base exists.
$null = git rev-parse --verify "refs/remotes/$RemoteName/$Base" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Base branch '$RemoteName/$Base' does not exist on the remote."
    exit 2
}

$baseRemote = "$RemoteName/$Base"
$baseSha    = (git rev-parse $baseRemote).Trim()
$baseDate   = (git log -1 --format="%ai" $baseRemote).Trim()
$baseSubj   = (git log -1 --format="%s"   $baseRemote).Trim()

Write-Info ""
Write-Info "$baseRemote tip:"
Write-Info "  sha:     $baseSha"
Write-Info "  date:    $baseDate"
Write-Info "  subject: $baseSubj"

# --------------------------------------------------------------------------
# Section 3 — enumerate every remote branch
# --------------------------------------------------------------------------

Write-Header "Step 2 — branch inventory"

$branches = git for-each-ref --format='%(refname:short)|%(objectname)|%(committerdate:iso8601)|%(authoremail)|%(subject)' "refs/remotes/$RemoteName/" |
    Where-Object { $_ -notmatch '^[^|]+/HEAD\|' } |
    ForEach-Object {
        $parts = $_ -split '\|', 5
        [PSCustomObject]@{
            Ref     = $parts[0]
            Sha     = $parts[1]
            Date    = $parts[2]
            Author  = $parts[3]
            Subject = $parts[4]
            Name    = ($parts[0] -replace "^$RemoteName/", "")
        }
    }

$total = $branches.Count
Write-Info ""
Write-Info "Total remote branches: $total"
Write-Info ""

# --------------------------------------------------------------------------
# Section 4 — classify each branch
# --------------------------------------------------------------------------

$classified = @()
$tipSha = @{}

foreach ($b in $branches) {
    if ($b.Name -eq $Base) {
        $kind = "BASE"
        $ahead  = 0
        $behind = 0
    } else {
        $ahead  = [int]((git rev-list --count "$baseRemote..$($b.Ref)" 2>$null) -as [int])
        $behind = [int]((git rev-list --count "$($b.Ref)..$baseRemote" 2>$null) -as [int])
        if ($ahead -eq 0) {
            $kind = "MERGED"
        } else {
            $kind = "UNIQUE"
        }
    }

    $classified += [PSCustomObject]@{
        Name     = $b.Name
        Sha      = $b.Sha.Substring(0,7)
        FullSha  = $b.Sha
        Date     = $b.Date
        Subject  = $b.Subject
        Ahead    = $ahead
        Behind   = $behind
        Kind     = $kind
        Ref      = $b.Ref
    }

    # Track tip SHAs for the duplicate-tip check below.
    if (-not $tipSha.ContainsKey($b.Sha)) {
        $tipSha[$b.Sha] = @()
    }
    $tipSha[$b.Sha] += $b.Name
}

# Print the inventory table.
$classified |
    Sort-Object @{Expression={$_.Kind}; Descending=$false}, Name |
    Format-Table -AutoSize -Property Name, Sha, Date, Kind, Ahead, Behind, Subject |
    Out-String | Write-Info

# --------------------------------------------------------------------------
# Section 5 — exact-tip duplicate check (true duplicates)
# --------------------------------------------------------------------------

Write-Header "Step 3 — exact-tip duplicate scan"

$exactDupes = $tipSha.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 }
if (-not $exactDupes) {
    Write-Ok "No two branches share a tip SHA — no exact-tip duplicates."
} else {
    foreach ($e in $exactDupes) {
        Write-Warn "Branches sharing tip $($e.Key.Substring(0,7)): $($e.Value -join ', ')"
    }
}

# --------------------------------------------------------------------------
# Section 6 — main-age explanation
# --------------------------------------------------------------------------

Write-Header "Step 4 — explain why $Base may look 'old'"

$now      = Get-Date
$baseTs   = [datetime]::Parse($baseDate)
$baseAgeH = [math]::Round(($now - $baseTs).TotalHours, 1)

$newest = $classified |
    Where-Object { $_.Name -ne $Base } |
    Sort-Object Date -Descending |
    Select-Object -First 1

if ($newest) {
    $newestTs   = [datetime]::Parse($newest.Date)
    $newestAgeH = [math]::Round(($now - $newestTs).TotalHours, 1)
    Write-Info "  $baseRemote last commit:        $baseDate ($baseAgeH h ago)"
    Write-Info "  Newest feature branch:          $($newest.Name)"
    Write-Info "  Newest feature commit:          $($newest.Date) ($newestAgeH h ago)"
    Write-Info ""
    if ($newest.Ahead -gt 0) {
        Write-Warn "$Base is $($newest.Ahead) commit(s) BEHIND the newest feature branch."
        Write-Warn "Recommendation: merge feature branches into $Base before re-running -Apply,"
        Write-Warn "or accept that the feature branches will stay UNIQUE and not be deletable."
    }
}

# --------------------------------------------------------------------------
# Section 7 — deletion plan
# --------------------------------------------------------------------------

Write-Header "Step 5 — deletion plan"

$deletable = $classified | Where-Object {
    $_.Kind -eq "MERGED" -and $_.Name -ne $Base -and $_.Name -ne $current
}
$keepUnique = $classified | Where-Object { $_.Kind -eq "UNIQUE" }
$activeProtected = $classified | Where-Object { $_.Name -eq $current }

Write-Info "  Branches classified MERGED (deletable): $($deletable.Count)"
Write-Info "  Branches classified UNIQUE (kept):      $($keepUnique.Count)"
Write-Info "  Active branch (always kept):            $current"
Write-Info ""

if ($deletable.Count -eq 0) {
    Write-Ok "Nothing to delete. Every non-base branch carries unique unmerged work,"
    Write-Ok "and no two branches share a tip SHA. Repo is in a healthy state."
    Write-Info ""
    if ($keepUnique.Count -gt 0) {
        Write-Info "If you want to clean up the $($keepUnique.Count) UNIQUE branches, the safe path is:"
        Write-Info "  1. Merge each one's PR into $Base (or close it if abandoned)."
        Write-Info "  2. Re-run this script — they'll reclassify to MERGED."
        Write-Info "  3. Re-run with -Apply to delete."
    }
    exit 0
}

Write-Info "MERGED branches that will be deleted with -Apply:"
foreach ($d in $deletable) {
    Write-Info "  - $($d.Name)  (sha=$($d.Sha), date=$($d.Date))"
}
Write-Info ""

if (-not $Apply.IsPresent) {
    Write-Warn "Read-only mode. Pass -Apply to actually delete the $($deletable.Count) MERGED branch(es)."
    Write-Warn "Pass -Apply -LocalOnly to leave the remote untouched."
    exit 0
}

# --------------------------------------------------------------------------
# Section 8 — actually delete (only with -Apply)
# --------------------------------------------------------------------------

Write-Header "Step 6 — applying deletions (-Apply mode)"

$failures = 0

foreach ($d in $deletable) {
    Write-Info ""
    Write-Info "Deleting $($d.Name) ..."

    # Local copy (if any) — safe -d (refuses if unmerged); -D is never used.
    $localExists = $false
    & git rev-parse --verify "refs/heads/$($d.Name)" 2>$null > $null
    if ($LASTEXITCODE -eq 0) { $localExists = $true }

    if ($localExists) {
        & git branch -d $d.Name 2>&1 | ForEach-Object { Write-Info "    [local]  $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Err "  Failed to delete local branch '$($d.Name)'. Skipping."
            $failures++
            continue
        }
    } else {
        Write-Info "    [local]  no local copy"
    }

    # Remote — only if not -LocalOnly.
    if (-not $LocalOnly.IsPresent) {
        & git push --delete $RemoteName $d.Name 2>&1 | ForEach-Object { Write-Info "    [remote] $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Err "  Failed to delete remote branch '$RemoteName/$($d.Name)'."
            $failures++
            continue
        }
    } else {
        Write-Info "    [remote] skipped (-LocalOnly)"
    }

    Write-Ok "Deleted $($d.Name)."
}

Write-Header "Summary"
Write-Info "  Branches deleted: $($deletable.Count - $failures)"
Write-Info "  Failures:         $failures"

if ($failures -gt 0) { exit 1 }
exit 0
