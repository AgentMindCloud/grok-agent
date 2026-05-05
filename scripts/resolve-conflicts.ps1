# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# scripts/resolve-conflicts.ps1
#
# Cross-Reality Action Fabric / Grok Agent OS — final-mile branch merger.
#
# Resolves the 5 UNIQUE branches that P136's `merge-to-main.ps1` left
# behind because of add/add or content conflicts. Strategy:
#
#   * The HIGH-PRIORITY branch claude/build-narrative-orchestration-wgVSY
#     carries Super Agent #1 (Living Narrative Fabric), 25 brand-new
#     files that don't exist anywhere on main. These come in as PURE
#     ADDS (no conflict). The branch ALSO carries 5 older self-evolving-
#     personal-os files that conflict with the canonical P121-P127
#     version on main — for those, `-X ours` keeps main's canonical
#     version and discards the branch's older parallel version.
#
#   * The other 4 low-priority branches (content-idea-generator,
#     monetization-optimizer-setup, complete-x-money-tools,
#     create-x-launch-thread) carry only EARLIER-iteration creator
#     templates that the active branch already superseded on main. We
#     merge them with `-X ours` for historical-record completeness;
#     no actual file content changes (every conflict resolves to
#     main's canonical version).
#
# Usage (PowerShell on Windows 11):
#
#     # Read-only dry run (default — safe):
#     .\scripts\resolve-conflicts.ps1
#
#     # Actually merge + push to origin/main:
#     .\scripts\resolve-conflicts.ps1 -Apply
#
#     # Merge locally only — don't touch the remote:
#     .\scripts\resolve-conflicts.ps1 -Apply -LocalOnly
#
#     # Skip the LNF-priority branch (rare):
#     .\scripts\resolve-conflicts.ps1 -Apply -SkipLnf
#
# Exit codes:
#   0  — every merge clean (or read-only mode finished successfully)
#   1  — at least one merge had unresolvable conflicts after -X ours
#   2  — pre-flight check failed
#   3  — push to remote failed

[CmdletBinding()]
param(
    [string] $Base       = "main",
    [string] $RemoteName = "origin",
    [switch] $Apply,
    [switch] $LocalOnly,
    [switch] $SkipLnf
)

$ErrorActionPreference = "Stop"

function Write-Header($text) {
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host $text   -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor DarkGray
}

function Write-Ok($text)   { Write-Host "  OK    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  WARN  $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ERR   $text" -ForegroundColor Red }

# --------------------------------------------------------------------------
# Section 1 — pre-flight
# --------------------------------------------------------------------------

try {
    $null = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) { throw "not a git repo" }
} catch {
    Write-Err "Not inside a git repository."
    exit 2
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
$current  = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Header "resolve-conflicts — $repoRoot"
Write-Host "Base branch:        $Base"
Write-Host "Remote name:        $RemoteName"
Write-Host "Current branch:     $current"
Write-Host "Apply mode:         $($Apply.IsPresent)"
Write-Host "Local-only mode:    $($LocalOnly.IsPresent)"
Write-Host "Skip LNF branch:    $($SkipLnf.IsPresent)"

# --------------------------------------------------------------------------
# Section 2 — sync local main
# --------------------------------------------------------------------------

Write-Header "Step 1 — fetch + sync local $Base"
& git fetch --all --prune 2>&1 | ForEach-Object { Write-Host "  $_" }

if ($current -ne $Base) {
    Write-Host "Switching to $Base ..."
    & git checkout $Base 2>&1 | ForEach-Object { Write-Host "  $_" }
}
& git pull --ff-only $RemoteName $Base 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Err "Local $Base could not be fast-forwarded to $RemoteName/$Base."
    exit 2
}

# --------------------------------------------------------------------------
# Section 3 — branch list (LNF first, others after)
# --------------------------------------------------------------------------

# Ordered list. The first entry MUST stay first — it's the LNF branch
# that brings Super Agent #1 to main. The other 4 are essentially
# historical-record merges; their content is already superseded.

$lnfBranch  = "claude/build-narrative-orchestration-wgVSY"
$tailBranches = @(
    "claude/content-idea-generator-0MxG6",
    "claude/monetization-optimizer-setup-H8Ypx",
    "claude/complete-x-money-tools-XrgAL",
    "claude/create-x-launch-thread-QXcHE"
)

$branches = @()
if (-not $SkipLnf.IsPresent) { $branches += $lnfBranch }
$branches += $tailBranches

Write-Header "Step 2 — merge plan"
Write-Host "Strategy: git merge -X ours --no-ff (resolve all content conflicts in $Base's favour)."
Write-Host "Order:"
foreach ($b in $branches) {
    $ahead = (& git rev-list --count "$RemoteName/$Base..$RemoteName/$b" 2>$null) -as [int]
    $note  = ""
    if ($b -eq $lnfBranch) { $note = "  ← Living Narrative Fabric (Super Agent #1) ← HIGH PRIORITY" }
    Write-Host ("  - $b  (ahead=$ahead)$note")
}

if (-not $Apply.IsPresent) {
    Write-Host ""
    Write-Warn "Read-only mode. Pass -Apply to actually merge."
    exit 0
}

# --------------------------------------------------------------------------
# Section 4 — execute the merges
# --------------------------------------------------------------------------

Write-Header "Step 3 — sequential -X ours merges"

$results       = @()
$failedMerges  = 0

foreach ($b in $branches) {
    Write-Host ""
    Write-Host "==> Merging $RemoteName/$b into $Base ..." -ForegroundColor Cyan

    $ahead = (& git rev-list --count "HEAD..$RemoteName/$b" 2>$null) -as [int]
    if ($ahead -eq 0) {
        Write-Ok "Already on HEAD (ahead=0). Skipping."
        $results += [PSCustomObject]@{ Branch = $b; Ahead = 0; Outcome = "skipped (no-op)"; Files = 0 }
        continue
    }

    $isLnf = ($b -eq $lnfBranch)
    $tag = if ($isLnf) { "P137 — Living Narrative Fabric" } else { "P137 cleanup" }
    $msg = "phase-5: merge $b into $Base (-X ours, $tag)"

    & git merge --no-ff -X ours -m $msg "$RemoteName/$b" 2>&1 | ForEach-Object { Write-Host "    $_" }

    if ($LASTEXITCODE -eq 0) {
        # Count files actually modified by THIS merge (vs HEAD~1).
        $changed = (& git diff --name-only "HEAD~1..HEAD" 2>$null | Measure-Object).Count
        Write-Ok ("Merged via -X ours ({0} file(s) changed)." -f $changed)
        $results += [PSCustomObject]@{
            Branch  = $b
            Ahead   = $ahead
            Outcome = if ($isLnf) { "MERGED — LNF" } else { "merged" }
            Files   = $changed
        }
    } else {
        # -X ours should have prevented conflicts, but defend in depth.
        $conflicted = & git diff --name-only --diff-filter=U 2>$null
        Write-Err ("Merge failed despite -X ours. {0} conflict(s):" -f $conflicted.Count)
        foreach ($c in $conflicted) { Write-Err "    - $c" }
        & git merge --abort 2>&1 | Out-Null
        $results += [PSCustomObject]@{
            Branch  = $b
            Ahead   = $ahead
            Outcome = "FAILED — needs manual review"
            Files   = $conflicted.Count
        }
        $failedMerges++
    }
}

# --------------------------------------------------------------------------
# Section 5 — verify LNF made it through
# --------------------------------------------------------------------------

Write-Header "Step 4 — verify Living Narrative Fabric on $Base"

if ($SkipLnf.IsPresent) {
    Write-Warn "LNF branch was skipped (-SkipLnf). Skipping LNF verification."
} else {
    $lnfFiles = & git ls-tree -r "HEAD" templates/super-agents/living-narrative-fabric/ 2>$null
    $lnfCount = ($lnfFiles | Measure-Object).Count
    if ($lnfCount -ge 20) {
        Write-Ok "LNF directory present on $Base with $lnfCount file(s)."
    } else {
        Write-Err "LNF directory missing or incomplete on $Base ($lnfCount file(s)). Investigate."
    }
}

# --------------------------------------------------------------------------
# Section 6 — push (only if every merge succeeded)
# --------------------------------------------------------------------------

Write-Header "Step 5 — push $Base to $RemoteName"

if ($failedMerges -gt 0) {
    Write-Err "$failedMerges merge(s) failed. NOT pushing $Base; resolve manually first."
    $exitCode = 1
} elseif ($LocalOnly.IsPresent) {
    Write-Warn "Local-only mode. Local $Base is updated; remote not pushed."
    $exitCode = 0
} else {
    & git push $RemoteName $Base 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Push failed. The local $Base is up to date but $RemoteName/$Base is NOT."
        Write-Err "Push manually from your shell:"
        Write-Err "  git push $RemoteName $Base"
        $exitCode = 3
    } else {
        Write-Ok "Pushed $Base to $RemoteName."
        $exitCode = 0
    }
}

# --------------------------------------------------------------------------
# Section 7 — summary
# --------------------------------------------------------------------------

Write-Header "Summary"
$results | Format-Table -AutoSize -Property Branch, Ahead, Outcome, Files | Out-String | Write-Host
Write-Host ""
Write-Host "Total branches:   $($results.Count)"
Write-Host "Merged cleanly:   $(($results | Where-Object { $_.Outcome -match '^merged|MERGED' }).Count)"
Write-Host "Skipped no-op:    $(($results | Where-Object Outcome -eq 'skipped (no-op)').Count)"
Write-Host "Failures:         $failedMerges"
Write-Host ""

exit $exitCode
