# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# scripts/merge-to-main.ps1
#
# Cross-Reality Action Fabric / Grok Agent OS — feature-branch merge runner.
#
# Merges the 9 UNIQUE feature branches identified by P135's diagnostic
# into `main`. Uses `git merge --no-ff` (no squash) so the merge history
# stays readable. Walks the branch list in chronological order (oldest
# first) and reports each merge's outcome individually. Refuses to push
# if any merge produced conflicts that the script could not auto-resolve.
#
# Usage (PowerShell on Windows 11):
#
#     # Read-only dry run (default — safe):
#     .\scripts\merge-to-main.ps1
#
#     # Actually merge + push to origin/main:
#     .\scripts\merge-to-main.ps1 -Apply
#
#     # Merge locally only — don't touch the remote:
#     .\scripts\merge-to-main.ps1 -Apply -LocalOnly
#
# Exit codes:
#   0  — every merge clean (or read-only mode finished successfully)
#   1  — at least one merge produced an unresolvable conflict
#   2  — pre-flight check failed (not a git repo, base branch missing, or similar)
#   3  — push to remote failed (e.g. proxy blocks push to main)

[CmdletBinding()]
param(
    [string] $Base       = "main",
    [string] $RemoteName = "origin",
    [switch] $Apply,
    [switch] $LocalOnly,
    [string[]] $Only = $null   # restrict to a subset of branches
)

$ErrorActionPreference = "Stop"

# --------------------------------------------------------------------------
# Section 1 — pre-flight
# --------------------------------------------------------------------------

function Write-Header($text) {
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host $text   -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor DarkGray
}

function Write-Ok($text)   { Write-Host "  OK    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  WARN  $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ERR   $text" -ForegroundColor Red }

try {
    $null = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) { throw "not a git repo" }
} catch {
    Write-Err "Not inside a git repository."
    exit 2
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
$current  = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Header "merge-to-main — $repoRoot"
Write-Host "Base branch:        $Base"
Write-Host "Remote name:        $RemoteName"
Write-Host "Current branch:     $current"
Write-Host "Apply mode:         $($Apply.IsPresent)"
Write-Host "Local-only mode:    $($LocalOnly.IsPresent)"

# --------------------------------------------------------------------------
# Section 2 — fetch + sync local main
# --------------------------------------------------------------------------

Write-Header "Step 1 — fetch + sync local $Base"
& git fetch --all --prune 2>&1 | ForEach-Object { Write-Host "  $_" }

# Make sure local $Base matches origin/$Base (fast-forward only).
& git checkout $Base 2>&1 | ForEach-Object { Write-Host "  $_" }
& git pull --ff-only $RemoteName $Base 2>&1 | ForEach-Object { Write-Host "  $_" }

if ($LASTEXITCODE -ne 0) {
    Write-Err "Local $Base could not be fast-forwarded to $RemoteName/$Base."
    Write-Err "Resolve the local divergence (e.g. `git reset --hard $RemoteName/$Base`) before re-running."
    exit 2
}

# --------------------------------------------------------------------------
# Section 3 — branch list (the 9 UNIQUE branches from P135)
# --------------------------------------------------------------------------

Write-Header "Step 2 — branch merge plan"

# Default merge order: chronological (oldest commit first), with the
# active branch LAST so its HANDOFF_LOG version wins on conflict.
$branches = @(
    "claude/build-thread-builder-77l7W",
    "claude/build-analytics-summarizer-nSQDa",
    "claude/mention-summarizer-runner-biEVs",
    "claude/content-idea-generator-0MxG6",
    "claude/monetization-optimizer-setup-H8Ypx",
    "claude/build-narrative-orchestration-wgVSY",
    "claude/complete-x-money-tools-XrgAL",
    "claude/create-x-launch-thread-QXcHE",
    "claude/build-api-connector-helpers-ZBcy4"   # active branch — merge LAST
)

if ($Only) {
    $branches = $branches | Where-Object { $Only -contains $_ }
}

Write-Host "Merge order (oldest first; active branch last):"
foreach ($b in $branches) {
    $ahead = (& git rev-list --count "$RemoteName/$Base..$RemoteName/$b" 2>$null) -as [int]
    $date  = (& git log -1 --format='%ai' "$RemoteName/$b" 2>$null).Trim()
    Write-Host ("  - $b  (ahead=$ahead, last commit $date)")
}

if (-not $Apply.IsPresent) {
    Write-Host ""
    Write-Warn "Read-only mode. Pass -Apply to actually merge."
    exit 0
}

# --------------------------------------------------------------------------
# Section 4 — sequential merges
# --------------------------------------------------------------------------

Write-Header "Step 3 — sequential merges"

$results = @()
$conflictCount = 0

foreach ($b in $branches) {
    Write-Host ""
    Write-Host "==> Merging $RemoteName/$b into $Base ..." -ForegroundColor Cyan

    # Re-check ahead count post earlier merges — a previously-unique branch
    # might now be a no-op.
    $ahead = (& git rev-list --count "HEAD..$RemoteName/$b" 2>$null) -as [int]
    if ($ahead -eq 0) {
        Write-Ok "Already merged (ahead=0 vs HEAD). Skipping."
        $results += [PSCustomObject]@{ Branch = $b; Outcome = "skipped (no-op)"; Files = 0 }
        continue
    }

    $msg = "phase-5: merge $b into $Base (P136 cleanup)"
    & git merge --no-ff -m $msg "$RemoteName/$b" 2>&1 | ForEach-Object { Write-Host "    $_" }

    if ($LASTEXITCODE -eq 0) {
        $changed = (& git diff --name-only "HEAD~1..HEAD" 2>$null | Measure-Object).Count
        Write-Ok "Merged cleanly ($changed file(s) changed)."
        $results += [PSCustomObject]@{ Branch = $b; Outcome = "clean"; Files = $changed }
    } else {
        # Detect conflicts.
        $conflicted = & git diff --name-only --diff-filter=U 2>$null
        if ($conflicted) {
            Write-Err "Conflicts in $($conflicted.Count) file(s):"
            foreach ($c in $conflicted) { Write-Err "    - $c" }
            Write-Err "Aborting this merge. Re-run manually after resolving."
            & git merge --abort 2>&1 | Out-Null
            $results += [PSCustomObject]@{ Branch = $b; Outcome = "conflict — aborted"; Files = $conflicted.Count }
            $conflictCount++
            continue
        }
        Write-Err "Merge failed for an unknown reason. Aborting."
        & git merge --abort 2>&1 | Out-Null
        $results += [PSCustomObject]@{ Branch = $b; Outcome = "failed"; Files = 0 }
        $conflictCount++
    }
}

# --------------------------------------------------------------------------
# Section 5 — push (only if every merge was clean OR a no-op)
# --------------------------------------------------------------------------

Write-Header "Step 4 — push $Base to $RemoteName"

if ($conflictCount -gt 0) {
    Write-Err "$conflictCount merge(s) had conflicts. Skipping push to $RemoteName/$Base."
    Write-Err "Resolve conflicts manually, then re-run with -Apply, or push from your shell."
    $exitCode = 1
} elseif ($LocalOnly.IsPresent) {
    Write-Warn "Local-only mode. Local $Base is updated; remote not pushed."
    $exitCode = 0
} else {
    & git push $RemoteName $Base 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Push failed. The local $Base is up to date but $RemoteName/$Base is NOT."
        Write-Err "Push manually from your shell once permissions allow:"
        Write-Err "  git push $RemoteName $Base"
        $exitCode = 3
    } else {
        Write-Ok "Pushed $Base to $RemoteName."
        $exitCode = 0
    }
}

# --------------------------------------------------------------------------
# Section 6 — summary
# --------------------------------------------------------------------------

Write-Header "Summary"
$results | Format-Table -AutoSize -Property Branch, Outcome, Files | Out-String | Write-Host
Write-Host ""
Write-Host "Total branches:   $($results.Count)"
Write-Host "Clean merges:     $(($results | Where-Object Outcome -eq 'clean').Count)"
Write-Host "Skipped (no-op):  $(($results | Where-Object Outcome -eq 'skipped (no-op)').Count)"
Write-Host "Conflicts:        $conflictCount"
Write-Host ""

exit $exitCode
