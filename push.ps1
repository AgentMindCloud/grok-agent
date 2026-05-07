# push.ps1 — one-shot init + commit + push for grok-pulse-mcp-server v0.1
# Run this from inside the project folder. It handles its own working directory.

$ErrorActionPreference = "Stop"

# Anchor to the script's own directory — survives any cd state.
Set-Location -Path $PSScriptRoot
Write-Host "Working in: $PSScriptRoot" -ForegroundColor Cyan
Write-Host ""

# ---- Step 1: verify gh is authenticated ----
Write-Host "=== Step 1/5: gh auth status ===" -ForegroundColor Yellow
gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "gh is not authenticated yet." -ForegroundColor Red
    Write-Host "Run this once in any terminal, then re-run push.ps1:" -ForegroundColor Red
    Write-Host "    gh auth login" -ForegroundColor White
    Write-Host "Choose: GitHub.com -> HTTPS -> 'Login with a web browser' (it'll print a code)." -ForegroundColor Gray
    exit 1
}

# ---- Step 2: clean any broken .git from earlier sandbox attempts ----
Write-Host ""
Write-Host "=== Step 2/5: clean broken .git if present ===" -ForegroundColor Yellow
if (Test-Path ".git") {
    Write-Host "Removing existing .git folder..."
    Remove-Item -Recurse -Force ".git"
    Write-Host "  done."
} else {
    Write-Host "  no existing .git folder — clean slate."
}

# ---- Step 3: git init + stage + status preview ----
Write-Host ""
Write-Host "=== Step 3/5: git init + stage ===" -ForegroundColor Yellow
git init -b main
git config user.email "AgentMindCloud@users.noreply.github.com"
git config user.name "AgentMindCloud"
git add -A

Write-Host ""
Write-Host "Files staged for first commit:" -ForegroundColor Cyan
git status --short
Write-Host ""

$bad = git status --short | Select-String -Pattern '\.env$|\.gh_token|node_modules/|^A  dist/'
if ($bad) {
    Write-Host "WARNING: Sensitive or build files appear staged:" -ForegroundColor Red
    $bad | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "Aborting. Fix .gitignore before continuing." -ForegroundColor Red
    exit 1
}

# ---- Step 4: commit ----
Write-Host "=== Step 4/5: commit ===" -ForegroundColor Yellow
$msg = @"
feat: scaffold + pulse_today tool (v0.1)

The first MCP server for builders shipping in the xAI / X / Grok ecosystem.

- TypeScript strict + MCP SDK 1.6 + stdio transport
- Apache-2.0 license
- pulse_today: parallel GitHub fetches (notifications, review requests, assigned
  issues, stale own PRs, failing CI) prioritized by Grok in 2-4 sentences
- Token-redacting error handler with per-API-domain messages
- Markdown + JSON response formats, CHARACTER_LIMIT enforcement
- Build-in-public from day 1
"@
git commit -m $msg

# ---- Step 5: create public repo + push ----
Write-Host ""
Write-Host "=== Step 5/5: gh repo create + push ===" -ForegroundColor Yellow
gh repo create AgentMindCloud/grok-pulse-mcp-server `
    --public `
    --description "MCP server using Grok to tell xAI/X/Grok ecosystem builders what needs their attention today across their GitHub repos." `
    --source=. `
    --remote=origin `
    --push

Write-Host ""
Write-Host "Done. Opening repo in browser..." -ForegroundColor Green
gh repo view AgentMindCloud/grok-pulse-mcp-server --web
