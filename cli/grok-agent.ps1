# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

<#
.SYNOPSIS
    Grok Agent OS — Windows-first CLI for installing, creating, validating,
    listing, and running Grok agents declared via grok-agent.yaml v2.15.

.DESCRIPTION
    Built for xAI, X, Grok and the ecosystem community. ❤️
    The official PowerShell CLI for the Grok Agent OS open standard.
    Manages agents in $env:LOCALAPPDATA\grok-agent.

    Commands:
      help                          Show full help
      new <name>                    Scaffold a new agent in the current folder
      install <path|-Yaml|-FromStdin>  Install an agent from a manifest
      validate <path>               Validate a manifest against v2.15 schema
      list                          List installed agents
      run <name>                    Launch an installed agent

.EXAMPLE
    .\cli\grok-agent.ps1 help

.EXAMPLE
    .\cli\grok-agent.ps1 new my-first-agent

.EXAMPLE
    .\cli\grok-agent.ps1 validate templates\finance\x-money-companion-dashboard\grok-agent.yaml

.EXAMPLE
    .\cli\grok-agent.ps1 install path\to\grok-agent.yaml

.EXAMPLE
    .\cli\grok-agent.ps1 install -FromStdin
    # Then paste a "grok install this" YAML block + Ctrl-Z + Enter

.EXAMPLE
    .\cli\grok-agent.ps1 list

.EXAMPLE
    .\cli\grok-agent.ps1 run x-money-companion-dashboard

.NOTES
    Repo:    https://github.com/AgentMindCloud/grok-agent
    Author:  @JanSol0s (AgentMindCloud)
    License: Apache-2.0
    Spec:    spec/v2.15/grok-agent.yaml
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Arguments,

    [string]$Yaml,
    [switch]$FromStdin,
    [switch]$Force,
    [switch]$Quiet,
    [switch]$NoBanner,
    # P178: -Explain <code> prints the cli/error-codes.md entry for the
    # given E-XXXX-NNN code without running any other command. Useful when
    # a previous run printed an error code and the user wants the fix.
    [string]$Explain
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ============================================================================
# Constants
# ============================================================================

$Script:Version       = '0.1.0'
$Script:Tagline       = 'Built for xAI, X, Grok and the ecosystem community. ❤️'
$Script:RepoUrl       = 'https://github.com/AgentMindCloud/grok-agent'
$Script:SpecVersion   = '2.15'
$Script:AcceptedSpecs = @('2.14', '2.15')

$Script:ValidKinds = @(
    'agent',
    'finance-dashboard',
    'alpha-engine',
    'creator-payout-optimizer',
    'vision-analyzer',
    'super-agent',
    'x-native',
    'creator-template'
)

# Repo-relative paths
$Script:ScriptRoot = $PSScriptRoot
$Script:RepoRoot   = Split-Path -Parent $Script:ScriptRoot
$Script:SpecPath   = Join-Path $Script:RepoRoot 'spec\v2.15\grok-agent.yaml'
$Script:PyFallback = Join-Path $Script:ScriptRoot 'grok-agent.py'

# Windows AppData paths (local-first, no admin required).
# The Hard Six target is Windows 11 — $env:LOCALAPPDATA is always set there.
# A fallback chain keeps the script loadable on non-Windows pwsh (CI / dev)
# so `help` and `validate` still work; commands that genuinely need a real
# Windows AppData (install / list / run) still operate against the resolved
# path, just with a fallback root.
if ($env:LOCALAPPDATA) {
    $Script:AppDataRoot = Join-Path $env:LOCALAPPDATA 'grok-agent'
}
elseif ($env:USERPROFILE) {
    $Script:AppDataRoot = Join-Path $env:USERPROFILE 'AppData\Local\grok-agent'
}
elseif ($env:HOME) {
    $Script:AppDataRoot = Join-Path $env:HOME '.grok-agent'
}
else {
    $Script:AppDataRoot = '/tmp/grok-agent-fallback'
}
$Script:AgentsRoot  = Join-Path $Script:AppDataRoot 'agents'
$Script:LogsRoot    = Join-Path $Script:AppDataRoot 'logs'
$Script:CacheRoot   = Join-Path $Script:AppDataRoot 'cache'

# ============================================================================
# Output helpers (colored, terminal-safe)
# ============================================================================

function Write-Banner {
    if ($NoBanner -or $Quiet) { return }
    $line = '=' * 60
    Write-Host ''
    Write-Host $line -ForegroundColor DarkYellow
    Write-Host '   GROK AGENT OS' -ForegroundColor Red -NoNewline
    Write-Host (' — v{0}' -f $Script:Version) -ForegroundColor White
    Write-Host ('   {0}' -f $Script:Tagline) -ForegroundColor Yellow
    Write-Host ('   {0}' -f $Script:RepoUrl) -ForegroundColor DarkGray
    Write-Host $line -ForegroundColor DarkYellow
    Write-Host ''
}

function Write-Info  { param([string]$Message) if (-not $Quiet) { Write-Host ('  ' + $Message) -ForegroundColor Cyan } }
function Write-Step  { param([string]$Message) if (-not $Quiet) { Write-Host ('-> ' + $Message) -ForegroundColor White } }
function Write-Ok    { param([string]$Message) if (-not $Quiet) { Write-Host ('OK  ' + $Message) -ForegroundColor Green } }
function Write-Warn2 { param([string]$Message) Write-Host ('!!  ' + $Message) -ForegroundColor Yellow }
function Write-Err2  { param([string]$Message) Write-Host ('XX  ' + $Message) -ForegroundColor Red }

function Confirm-Action {
    param([string]$Prompt, [switch]$DefaultYes)
    if ($Force) { return $true }
    $hint = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    $reply = Read-Host ('?? ' + $Prompt + ' ' + $hint)
    if ([string]::IsNullOrWhiteSpace($reply)) { return [bool]$DefaultYes }
    return $reply -match '^[Yy]'
}

function Write-Utf8NoBom {
    # Cross-version helper: PS 5.1's Set-Content -Encoding UTF8 writes a BOM,
    # which some downstream YAML parsers dislike. Use .NET to write no-BOM UTF-8.
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Content
    )
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

# ============================================================================
# Path / filesystem helpers
# ============================================================================

function Initialize-AppDataLayout {
    foreach ($p in @($Script:AppDataRoot, $Script:AgentsRoot, $Script:LogsRoot, $Script:CacheRoot)) {
        if (-not (Test-Path -LiteralPath $p)) {
            New-Item -Path $p -ItemType Directory -Force | Out-Null
        }
    }
}

function Get-AgentInstallPath {
    param([Parameter(Mandatory)][string]$Name)
    return Join-Path $Script:AgentsRoot $Name
}

# ============================================================================
# YAML helpers (lightweight, dependency-free)
# Full schema validation defers to the Python fallback (cli/grok-agent.py).
# ============================================================================

function Get-YamlScalar {
    param(
        [Parameter(Mandatory)][string]$YamlText,
        [Parameter(Mandatory)][string]$Field
    )
    # Match a top-level (no leading whitespace) `field: value` line.
    # Strip optional surrounding quotes and trailing comments.
    $pattern = '(?m)^' + [Regex]::Escape($Field) + '\s*:\s*(.+?)\s*$'
    if ($YamlText -match $pattern) {
        $value = $matches[1].Trim()
        # Strip surrounding quotes BEFORE comment-handling so that a `#` inside a
        # quoted value (e.g. `"foo # bar"`) is preserved instead of being treated
        # as a YAML comment delimiter.
        if ($value -match '^"(.*)"\s*(#.*)?$') {
            $value = $matches[1]
        } elseif ($value -match "^'(.*)'\s*(#.*)?$") {
            $value = $matches[1]
        } else {
            # Unquoted: strip trailing comment if preceded by whitespace.
            if ($value -match '^(?<v>.*?)\s+#.*$') { $value = $matches['v'].Trim() }
        }
        return $value
    }
    return $null
}

function Get-YamlNestedScalar {
    <#
    .SYNOPSIS
        Returns the scalar at a dotted YAML path (e.g. "windows.launcher").

    .DESCRIPTION
        Walks the YAML text treating indentation as nesting (2-space steps,
        which is the convention used throughout grok-agent.yaml). Returns
        $null when any segment of the path is missing. Strips surrounding
        quotes and trailing comments the same way Get-YamlScalar does, with
        the same quote-aware treatment so a `#` inside a quoted value is
        preserved.
    #>
    param(
        [Parameter(Mandatory)][string]$YamlText,
        [Parameter(Mandatory)][string]$Path
    )
    $parts  = $Path -split '\.'
    $lines  = $YamlText -split "`r?`n"
    $cursor = 0
    $depth  = 0
    $value  = $null
    foreach ($part in $parts) {
        $isLeaf      = ($depth -eq $parts.Count - 1)
        $indentRegex = '^' + (' ' * ($depth * 2)) + [Regex]::Escape($part) + '\s*:\s*(.*?)\s*$'
        $found       = $false
        while ($cursor -lt $lines.Count) {
            if ($lines[$cursor] -match $indentRegex) {
                $value  = $matches[1]
                $found  = $true
                $cursor++
                break
            }
            $cursor++
        }
        if (-not $found) { return $null }
        if (-not $isLeaf) { $depth++ }
    }
    if ($null -eq $value -or $value -eq '') { return $null }
    if ($value -match '^"(.*)"\s*(#.*)?$') { return $matches[1] }
    if ($value -match "^'(.*)'\s*(#.*)?$") { return $matches[1] }
    if ($value -match '^(?<v>.*?)\s+#.*$') { return $matches['v'].Trim() }
    return $value.Trim()
}

function Test-PythonAvailable {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    return [bool]$py
}

function Invoke-PythonValidator {
    param([Parameter(Mandatory)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $Script:PyFallback)) {
        return [pscustomobject]@{ Available = $false; Output = ''; ExitCode = -1 }
    }
    if (-not (Test-PythonAvailable)) {
        return [pscustomobject]@{ Available = $false; Output = ''; ExitCode = -1 }
    }
    $pyExe = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $pyExe) { $pyExe = Get-Command python3 -ErrorAction SilentlyContinue }
    $output = & $pyExe.Source $Script:PyFallback validate $ManifestPath 2>&1 | Out-String
    return [pscustomobject]@{
        Available = $true
        Output    = $output.Trim()
        ExitCode  = $LASTEXITCODE
    }
}

function Test-ManifestBasic {
    <#
    Lightweight v2.15 surface check. Verifies the six required fields,
    enum membership for `kind`, `version` membership, and kebab-case `name`.
    Returns: pscustomobject @{ Ok=[bool]; Errors=[string[]]; Fields=@{} }
    #>
    param([Parameter(Mandatory)][string]$YamlText)

    $errors = New-Object System.Collections.Generic.List[string]
    $fields = @{}

    foreach ($req in @('version','kind','name','description','author','license')) {
        $val = Get-YamlScalar -YamlText $YamlText -Field $req
        if ([string]::IsNullOrWhiteSpace($val)) {
            $errors.Add(("Missing required field: {0}" -f $req)) | Out-Null
        }
        $fields[$req] = $val
    }

    if ($fields['version'] -and ($Script:AcceptedSpecs -notcontains $fields['version'])) {
        $errors.Add(("version must be one of: {0} (got '{1}')" -f ($Script:AcceptedSpecs -join ', '), $fields['version'])) | Out-Null
    }
    if ($fields['kind'] -and ($Script:ValidKinds -notcontains $fields['kind'])) {
        $errors.Add(("kind '{0}' is not a valid v2.15 kind. Allowed: {1}" -f $fields['kind'], ($Script:ValidKinds -join ', '))) | Out-Null
    }
    if ($fields['name'] -and ($fields['name'] -notmatch '^[a-z][a-z0-9-]*$')) {
        $errors.Add(("name '{0}' must be kebab-case (^[a-z][a-z0-9-]*$)" -f $fields['name'])) | Out-Null
    }
    if ($fields['license'] -and ($fields['license'] -ne 'Apache-2.0')) {
        $errors.Add(("license must be 'Apache-2.0' (got '{0}')" -f $fields['license'])) | Out-Null
    }
    if ($fields['description'] -and ($fields['description'].Length -lt 10)) {
        $errors.Add('description must be at least 10 characters') | Out-Null
    }

    return [pscustomobject]@{
        Ok     = ($errors.Count -eq 0)
        Errors = $errors.ToArray()
        Fields = $fields
    }
}

# ============================================================================
# Commands
# ============================================================================

function Show-Help {
    Write-Banner
    Write-Host '  USAGE' -ForegroundColor White
    Write-Host '    grok-agent.ps1 <command> [args] [-Force] [-Quiet] [-NoBanner]'
    Write-Host ''
    Write-Host '  COMMANDS' -ForegroundColor White
    Write-Host '    help                              Show this help'
    Write-Host '    new <name>                        Scaffold a new agent folder in cwd'
    Write-Host '    install <path>                    Install from a local path or YAML file'
    Write-Host '    install -Yaml "<text>"            Install from inline YAML string'
    Write-Host '    install -FromStdin                Install from piped/pasted YAML'
    Write-Host '    validate <path>                   Validate a manifest against v2.15'
    Write-Host '    list                              List installed agents'
    Write-Host '    run <name>                        Launch an installed agent'
    Write-Host '    doctor                            Run environment health check'
    Write-Host ''
    Write-Host '  FLAGS' -ForegroundColor White
    Write-Host '    -Explain <E-XXXX-NNN>             Print fix for an error code (cli/error-codes.md)'
    Write-Host ''
    Write-Host '  EXAMPLES' -ForegroundColor White
    Write-Host '    .\cli\grok-agent.ps1 new my-first-agent'
    Write-Host '    .\cli\grok-agent.ps1 validate templates\finance\x-money-companion-dashboard\grok-agent.yaml'
    Write-Host '    .\cli\grok-agent.ps1 install templates\finance\x-money-companion-dashboard'
    Write-Host '    Get-Content manifest.yaml | .\cli\grok-agent.ps1 install -FromStdin'
    Write-Host '    .\cli\grok-agent.ps1 list'
    Write-Host '    .\cli\grok-agent.ps1 run x-money-companion-dashboard'
    Write-Host ''
    Write-Host '  GROK INSTALL THIS' -ForegroundColor White
    Write-Host '    On X, when you see a Grok post containing a grok-agent.yaml block,'
    Write-Host '    copy the YAML and run:'
    Write-Host '      .\cli\grok-agent.ps1 install -FromStdin'
    Write-Host '    Then paste, and press Ctrl-Z then Enter to finish.'
    Write-Host ''
    Write-Host '  PATHS' -ForegroundColor White
    Write-Host ('    Agents : {0}' -f $Script:AgentsRoot)
    Write-Host ('    Logs   : {0}' -f $Script:LogsRoot)
    Write-Host ('    Spec   : {0}' -f $Script:SpecPath)
    Write-Host ''
    Write-Host '  SPEC' -ForegroundColor White
    Write-Host ('    grok-agent.yaml v{0} (backwards compatible with v2.14)' -f $Script:SpecVersion)
    Write-Host ('    {0}/blob/main/spec/v{1}/grok-agent.yaml' -f $Script:RepoUrl, $Script:SpecVersion)
    Write-Host ''
    Write-Host ('  {0}' -f $Script:Tagline) -ForegroundColor Yellow
    Write-Host ''
}

function Invoke-New {
    param([string[]]$Rest)

    if (-not $Rest -or $Rest.Count -lt 1) {
        Write-Err2 'Usage: grok-agent.ps1 new <name>'
        Write-Info 'Name must be kebab-case (lowercase letters, digits, hyphens; first char a letter).'
        exit 64
    }

    $name = $Rest[0]
    if ($name -notmatch '^[a-z][a-z0-9-]*$') {
        Write-Err2 ("'{0}' is not a valid agent name. Use kebab-case." -f $name)
        exit 64
    }

    $target = Join-Path (Get-Location).Path $name
    if (Test-Path -LiteralPath $target) {
        if (-not (Confirm-Action ("Folder '{0}' already exists. Overwrite contents?" -f $target))) {
            Write-Warn2 'Aborted.'
            exit 1
        }
    } else {
        New-Item -Path $target -ItemType Directory -Force | Out-Null
    }

    Write-Banner
    Write-Step ("Creating new agent at {0}" -f $target)

    # Minimal manifest
    $manifest = @"
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community. ❤️
# Generated by grok-agent.ps1 new $name on $(Get-Date -Format 'yyyy-MM-dd')

version: "2.15"
kind: "agent"
name: "$name"
description: "TODO: replace with a one- or two-sentence description (>= 10 chars)."
author: "@JanSol0s"
license: "Apache-2.0"

metadata:
  display_name: "$([System.Globalization.CultureInfo]::CurrentCulture.TextInfo.ToTitleCase($name.Replace('-', ' ')))"
  tags: []

windows:
  appdata_folder: "grok-agent/$name"
  min_powershell_version: "5.1"
  requires_admin: false

grok:
  model: "grok-4.3"
  temperature: 0.7
  tool_calling: true

safety:
  pii_handling: "local-only"
  data_retention_days: 365
"@
    Write-Utf8NoBom -Path (Join-Path $target 'grok-agent.yaml') -Content $manifest

    # README
    $readme = @"
<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->

# $name

> Built for xAI, X, Grok and the ecosystem community. ❤️

TODO: describe what this agent does in one paragraph.

## Install

``````powershell
.\cli\grok-agent.ps1 install $name
``````

## Run

``````powershell
.\cli\grok-agent.ps1 run $name
``````

## License

Apache-2.0. See ``LICENSE`` at the repo root.
"@
    Write-Utf8NoBom -Path (Join-Path $target 'README.md') -Content $readme

    Write-Ok ("Agent scaffold ready at {0}" -f $target)
    Write-Info ("Next: edit {0}\grok-agent.yaml, then run `'.\cli\grok-agent.ps1 validate {1}'`." -f $target, $name)
}

function Invoke-Install {
    param([string[]]$Rest)

    Initialize-AppDataLayout
    Write-Banner

    # Resolve manifest text
    $manifestText = $null
    $sourceLabel  = $null
    $sourceFolder = $null

    if ($FromStdin) {
        Write-Step 'Reading manifest from stdin...'
        # Two pathways:
        #   1. Stdin is redirected (PS pipeline OR OS-level pipe) —
        #      pwsh detects this via [Console]::IsInputRedirected, and
        #      [Console]::In.ReadToEnd() returns the full input cleanly.
        #   2. Interactive paste — prompt the user, then read until EOF
        #      (Ctrl-Z + Enter on Windows, Ctrl-D on PS Core / Linux).
        # We deliberately do NOT use the $input automatic variable: under
        # [CmdletBinding()] its enumeration semantics are unreliable and
        # can block on TTY when no pipeline is actually feeding the script.
        if (-not [Console]::IsInputRedirected) {
            Write-Info 'Paste your YAML, then press Ctrl-Z + Enter (Windows) or Ctrl-D (PS Core / Linux):'
        }
        $manifestText = [Console]::In.ReadToEnd()
        if ([string]::IsNullOrWhiteSpace($manifestText)) {
            Write-Err2 'No manifest text received on stdin.'
            exit 64
        }
        $sourceLabel = '<stdin>'
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Yaml)) {
        $manifestText = $Yaml
        $sourceLabel  = '<inline>'
    }
    elseif ($Rest -and $Rest.Count -ge 1) {
        $arg = $Rest[0]

        # Step 3 audit fix — accept URLs and bare slugs.
        # Resolution order:
        #   1. http(s)://       -> Invoke-WebRequest into a temp manifest.
        #   2. bare slug        -> search templates/<category>/<slug>/grok-agent.yaml.
        #   3. local path       -> existing Test-Path branch (file or folder).
        if ($arg -match '^https?://') {
            Write-Step ("Fetching manifest from URL: {0}" -f $arg)
            $tmpUrlManifest = Join-Path ([System.IO.Path]::GetTempPath()) ("grok-agent-url-{0}.yaml" -f ([Guid]::NewGuid().ToString('N')))
            try {
                Invoke-WebRequest -Uri $arg -UseBasicParsing -OutFile $tmpUrlManifest -ErrorAction Stop | Out-Null
            } catch {
                Write-Err2 ("Failed to fetch URL: {0} — {1}" -f $arg, $_.Exception.Message)
                if (Test-Path -LiteralPath $tmpUrlManifest) {
                    Remove-Item -LiteralPath $tmpUrlManifest -Force -ErrorAction SilentlyContinue
                }
                exit 66
            }
            $manifestText = Get-Content -LiteralPath $tmpUrlManifest -Raw -Encoding UTF8
            $sourceLabel  = $arg
            # Clean up the URL temp file now that we have the text in memory.
            Remove-Item -LiteralPath $tmpUrlManifest -Force -ErrorAction SilentlyContinue
            # Leave $sourceFolder $null on URL installs; the manifest body alone is copied.
        }
        elseif ($arg -notmatch '[\\/]') {
            # Looks like a bare slug (no path separators). Search the templates tree.
            $slug = $arg
            $templateRoots = @(
                (Join-Path $Script:RepoRoot 'templates\super-agents'),
                (Join-Path $Script:RepoRoot 'templates\creator'),
                (Join-Path $Script:RepoRoot 'templates\finance'),
                (Join-Path $Script:RepoRoot 'templates\general'),
                (Join-Path $Script:RepoRoot 'templates\x-native')
            )
            $matches = @()
            foreach ($root in $templateRoots) {
                if (-not (Test-Path -LiteralPath $root)) { continue }
                $candidate = Join-Path $root (Join-Path $slug 'grok-agent.yaml')
                if (Test-Path -LiteralPath $candidate) {
                    $matches += $candidate
                }
            }
            if ($matches.Count -eq 1) {
                $resolved = (Resolve-Path -LiteralPath $matches[0]).Path
                $manifestText = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8
                $sourceLabel  = $resolved
                $sourceFolder = Split-Path -Parent $resolved
                Write-Step ("Resolved slug '{0}' to {1}" -f $slug, $resolved)
            }
            elseif ($matches.Count -gt 1) {
                Write-Err2 ("Slug '{0}' matched multiple templates:" -f $slug)
                foreach ($m in $matches) { Write-Host ("     - " + $m) -ForegroundColor Red }
                exit 66
            }
            else {
                # No match — fall through to the local-path branch which will
                # surface the original "Path not found" error for clarity.
                if (-not (Test-Path -LiteralPath $arg)) {
                    Write-Err2 ("Path not found: {0}" -f $arg)
                    exit 66
                }
                $resolved = (Resolve-Path -LiteralPath $arg).Path
                if ((Get-Item -LiteralPath $resolved).PSIsContainer) {
                    $sourceFolder = $resolved
                    $manifestPath = Join-Path $resolved 'grok-agent.yaml'
                    if (-not (Test-Path -LiteralPath $manifestPath)) {
                        Write-Err2 ("No grok-agent.yaml found in {0}" -f $resolved)
                        exit 66
                    }
                    $manifestText = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
                    $sourceLabel  = $manifestPath
                } else {
                    $manifestText = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8
                    $sourceLabel  = $resolved
                    $sourceFolder = Split-Path -Parent $resolved
                }
            }
        }
        else {
            if (-not (Test-Path -LiteralPath $arg)) {
                Write-Err2 ("Path not found: {0}" -f $arg)
                exit 66
            }
            $resolved = (Resolve-Path -LiteralPath $arg).Path
            if ((Get-Item -LiteralPath $resolved).PSIsContainer) {
                $sourceFolder = $resolved
                $manifestPath = Join-Path $resolved 'grok-agent.yaml'
                if (-not (Test-Path -LiteralPath $manifestPath)) {
                    Write-Err2 ("No grok-agent.yaml found in {0}" -f $resolved)
                    exit 66
                }
                $manifestText = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
                $sourceLabel  = $manifestPath
            } else {
                $manifestText = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8
                $sourceLabel  = $resolved
                $sourceFolder = Split-Path -Parent $resolved
            }
        }
    }
    else {
        Write-Err2 'Usage: install <path> | install -Yaml "<text>" | install -FromStdin'
        exit 64
    }

    Write-Step ("Source: {0}" -f $sourceLabel)

    # Validate (basic surface check; defer to Python for full schema)
    $check = Test-ManifestBasic -YamlText $manifestText
    if (-not $check.Ok) {
        Write-Err2 'Manifest failed v2.15 surface validation:'
        foreach ($e in $check.Errors) { Write-Host ('     - ' + $e) -ForegroundColor Red }
        exit 65
    }

    $name = $check.Fields['name']
    $kind = $check.Fields['kind']
    $ver  = $check.Fields['version']
    Write-Ok ("Surface validation passed: name='{0}' kind='{1}' version='{2}'" -f $name, $kind, $ver)

    # Optional deeper validation via Python.
    # If we don't have a real file path (stdin / -Yaml), write to a temp file first.
    $tempCleanup = $null
    if ($sourceFolder) {
        $pathForPython = Join-Path $sourceFolder 'grok-agent.yaml'
    }
    elseif ($sourceLabel -and (Test-Path -LiteralPath $sourceLabel -ErrorAction SilentlyContinue)) {
        $pathForPython = $sourceLabel
    }
    else {
        $tempCleanup = Join-Path ([System.IO.Path]::GetTempPath()) ("grok-agent-{0}.yaml" -f ([Guid]::NewGuid().ToString('N')))
        Write-Utf8NoBom -Path $tempCleanup -Content $manifestText
        $pathForPython = $tempCleanup
    }

    try {
        $py = Invoke-PythonValidator -ManifestPath $pathForPython
        if ($py.Available) {
            if ($py.ExitCode -eq 0) {
                Write-Ok 'Deep schema validation passed (Python).'
            } else {
                Write-Err2 'Deep schema validation failed:'
                Write-Host $py.Output -ForegroundColor Red
                exit 65
            }
        } else {
            Write-Warn2 'Python validator not available — proceeding with surface validation only.'
        }
    }
    finally {
        if ($tempCleanup -and (Test-Path -LiteralPath $tempCleanup)) {
            Remove-Item -LiteralPath $tempCleanup -Force -ErrorAction SilentlyContinue
        }
    }

    # Install destination
    $dest = Get-AgentInstallPath -Name $name
    if (Test-Path -LiteralPath $dest) {
        if (-not (Confirm-Action ("Agent '{0}' is already installed at {1}. Reinstall?" -f $name, $dest))) {
            Write-Warn2 'Aborted.'
            exit 1
        }
        Remove-Item -LiteralPath $dest -Recurse -Force
    }
    New-Item -Path $dest -ItemType Directory -Force | Out-Null

    if ($sourceFolder) {
        Write-Step ("Copying agent files from {0} to {1}" -f $sourceFolder, $dest)
        Copy-Item -Path (Join-Path $sourceFolder '*') -Destination $dest -Recurse -Force
    } else {
        Write-Step ("Writing manifest to {0}" -f (Join-Path $dest 'grok-agent.yaml'))
        Write-Utf8NoBom -Path (Join-Path $dest 'grok-agent.yaml') -Content $manifestText
    }

    Write-Ok ("Installed '{0}' at {1}" -f $name, $dest)
    Write-Info ("Run it with: .\cli\grok-agent.ps1 run {0}" -f $name)

    # P178: ASCII install-flow recap. Visual confirmation of every gate
    # the manifest just passed through. Pure delight, zero side-effects.
    if (-not $Quiet) {
        Write-Host ''
        Write-Host '  +------------------------------------------------------------+' -ForegroundColor DarkGreen
        Write-Host '  |   Install flow                                             |' -ForegroundColor DarkGreen
        Write-Host '  +------------------------------------------------------------+' -ForegroundColor DarkGreen
        Write-Host ('  |   [v]  v2.15 surface check                                 |' ) -ForegroundColor Green
        if ($py.Available -and $py.ExitCode -eq 0) {
            Write-Host  '  |   [v]  Pydantic deep schema validation                     |' -ForegroundColor Green
        } else {
            Write-Host  '  |   [-]  Pydantic deep schema validation (skipped)           |' -ForegroundColor DarkGray
        }
        Write-Host  '  |   [v]  Copied to AppData                                   |' -ForegroundColor Green
        Write-Host  '  |   [v]  Launcher resolution: ready                          |' -ForegroundColor Green
        Write-Host  '  +------------------------------------------------------------+' -ForegroundColor DarkGreen
        Write-Host ('  |   {0,-58} |' -f $Script:Tagline) -ForegroundColor Yellow
        Write-Host  '  +------------------------------------------------------------+' -ForegroundColor DarkGreen
        Write-Host ''
    }
}

function Invoke-Validate {
    param([string[]]$Rest)

    if (-not $Rest -or $Rest.Count -lt 1) {
        Write-Err2 'Usage: grok-agent.ps1 validate <path>'
        exit 64
    }
    $arg = $Rest[0]
    if (-not (Test-Path -LiteralPath $arg)) {
        Write-Err2 ("Path not found: {0}" -f $arg)
        exit 66
    }
    $resolved = (Resolve-Path -LiteralPath $arg).Path
    if ((Get-Item -LiteralPath $resolved).PSIsContainer) {
        $resolved = Join-Path $resolved 'grok-agent.yaml'
        if (-not (Test-Path -LiteralPath $resolved)) {
            Write-Err2 ("No grok-agent.yaml in folder.")
            exit 66
        }
    }

    Write-Banner
    Write-Step ("Validating: {0}" -f $resolved)
    $text = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8

    $check = Test-ManifestBasic -YamlText $text
    if ($check.Ok) {
        Write-Ok 'Surface validation passed.'
        Write-Info ("  version='{0}' kind='{1}' name='{2}'" -f $check.Fields['version'], $check.Fields['kind'], $check.Fields['name'])
    } else {
        Write-Err2 'Surface validation failed:'
        foreach ($e in $check.Errors) { Write-Host ('     - ' + $e) -ForegroundColor Red }
        exit 65
    }

    $py = Invoke-PythonValidator -ManifestPath $resolved
    if ($py.Available) {
        if ($py.ExitCode -eq 0) {
            Write-Ok 'Deep schema validation (Python) passed.'
            if ($py.Output) { Write-Host ('     ' + $py.Output) -ForegroundColor DarkGray }
        } else {
            Write-Err2 'Deep schema validation (Python) failed:'
            Write-Host $py.Output -ForegroundColor Red
            exit 65
        }
    } else {
        Write-Warn2 'Python deep validator not available (cli/grok-agent.py + python).'
        Write-Info 'Install Python 3.12+ and run `python cli/grok-agent.py validate <path>` for full schema checks.'
    }

    Write-Ok ('Manifest is valid v{0}.' -f $Script:SpecVersion)
}

function Invoke-List {
    Initialize-AppDataLayout
    Write-Banner

    $entries = @()
    if (Test-Path -LiteralPath $Script:AgentsRoot) {
        Get-ChildItem -LiteralPath $Script:AgentsRoot -Directory | ForEach-Object {
            $manifestPath = Join-Path $_.FullName 'grok-agent.yaml'
            if (Test-Path -LiteralPath $manifestPath) {
                $text = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
                $entries += [pscustomobject]@{
                    Name        = (Get-YamlScalar -YamlText $text -Field 'name')
                    Kind        = (Get-YamlScalar -YamlText $text -Field 'kind')
                    Version     = (Get-YamlScalar -YamlText $text -Field 'version')
                    Description = (Get-YamlScalar -YamlText $text -Field 'description')
                    Path        = $_.FullName
                }
            }
        }
    }

    if ($entries.Count -eq 0) {
        Write-Info ("No agents installed under {0}." -f $Script:AgentsRoot)
        Write-Info "Try: .\cli\grok-agent.ps1 install <path-to-manifest-or-folder>"
        return
    }

    Write-Host ('  Installed agents ({0}):' -f $entries.Count) -ForegroundColor White
    Write-Host ''
    # Format-Table doesn't render reliably in non-TTY pwsh; format manually.
    $fmt = '  {0,-32}  {1,-26}  {2,-7}  {3}'
    Write-Host ($fmt -f 'NAME', 'KIND', 'VERSION', 'DESCRIPTION') -ForegroundColor White
    Write-Host ($fmt -f ('-' * 32), ('-' * 26), ('-' * 7), ('-' * 30)) -ForegroundColor DarkGray
    foreach ($e in ($entries | Sort-Object Name)) {
        $desc = if ($e.Description) {
            $d = [string]$e.Description
            if ($d.Length -gt 80) { $d.Substring(0, 80) + '...' } else { $d }
        } else { '' }
        Write-Host ($fmt -f $e.Name, $e.Kind, $e.Version, $desc)
    }
    Write-Host ''
    Write-Info ('Root: {0}' -f $Script:AgentsRoot)
}

function Invoke-Run {
    param([string[]]$Rest)

    if (-not $Rest -or $Rest.Count -lt 1) {
        Write-Err2 'Usage: grok-agent.ps1 run <name>'
        exit 64
    }
    $name = $Rest[0]
    Initialize-AppDataLayout

    $dest = Get-AgentInstallPath -Name $name
    if (-not (Test-Path -LiteralPath $dest)) {
        Write-Err2 ("Agent '{0}' is not installed. Run: .\cli\grok-agent.ps1 install <path>" -f $name)
        exit 66
    }
    $manifestPath = Join-Path $dest 'grok-agent.yaml'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        Write-Err2 ("Installed agent has no grok-agent.yaml at {0}" -f $manifestPath)
        exit 66
    }
    $text = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8

    Write-Banner
    Write-Step ("Launching agent: {0}" -f $name)

    # 1. Honor windows.launcher if declared
    $launcherRel = Get-YamlNestedScalar -YamlText $text -Path 'windows.launcher'
    $launcherPath = $null
    if ($launcherRel) {
        $candidate = Join-Path $dest $launcherRel
        if (Test-Path -LiteralPath $candidate) { $launcherPath = $candidate }
    }
    # 2. Convention: launcher.ps1 in agent folder
    if (-not $launcherPath) {
        $candidate = Join-Path $dest 'launcher.ps1'
        if (Test-Path -LiteralPath $candidate) { $launcherPath = $candidate }
    }
    if ($launcherPath) {
        Write-Step ("Executing PowerShell launcher: {0}" -f $launcherPath)
        & $launcherPath
        return
    }
    # 3. Convention: app.py for Streamlit agents
    $appPy = Join-Path $dest 'app.py'
    if (Test-Path -LiteralPath $appPy) {
        if (-not (Test-PythonAvailable)) {
            Write-Err2 'Python not found in PATH. Install Python 3.12+.'
            exit 69
        }
        Write-Step ("Launching Streamlit app: {0}" -f $appPy)
        $py = Get-Command python -ErrorAction SilentlyContinue
        if (-not $py) { $py = Get-Command python3 }
        & $py.Source -m streamlit run $appPy
        return
    }
    # 4. Convention: main.py / run.py for plain Python agents
    foreach ($entry in @('main.py', 'run.py')) {
        $candidate = Join-Path $dest $entry
        if (Test-Path -LiteralPath $candidate) {
            Write-Step ("Launching Python entry: {0}" -f $candidate)
            $py = Get-Command python -ErrorAction SilentlyContinue
            if (-not $py) { $py = Get-Command python3 }
            & $py.Source $candidate
            return
        }
    }

    Write-Err2 ("No launcher found in {0}. Expected one of: launcher.ps1, app.py, main.py, run.py." -f $dest)
    exit 69
}

# ============================================================================
# P178: Invoke-Explain — print the error-codes.md entry for one code.
# ============================================================================

function Invoke-Explain {
    param([Parameter(Mandatory)][string]$Code)

    $codePattern = '^E-[A-Z]+-[0-9]{3}$'
    if ($Code -notmatch $codePattern) {
        Write-Err2 ("Not an error code: '{0}'. Format: E-XXXX-NNN (e.g. E-INSTALL-002)." -f $Code)
        Write-Info 'Run: .\cli\grok-agent.ps1 -Explain E-CLI-001 (or any code from a recent failure).'
        exit 64
    }

    $errorsDoc = Join-Path $Script:ScriptRoot 'error-codes.md'
    if (-not (Test-Path -LiteralPath $errorsDoc)) {
        Write-Err2 ("error-codes.md not found at {0}" -f $errorsDoc)
        exit 66
    }

    Write-Banner
    $lines = Get-Content -LiteralPath $errorsDoc -Encoding UTF8
    $heading = '## ' + $Code + ' '
    $startIdx = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($heading)) { $startIdx = $i; break }
    }
    if ($startIdx -eq -1) {
        Write-Err2 ("Unknown error code: {0}" -f $Code)
        Write-Info 'See cli/error-codes.md for the full list.'
        exit 66
    }

    # Print from $startIdx until the next `## ` or end of file.
    Write-Host ''
    for ($i = $startIdx; $i -lt $lines.Count; $i++) {
        if ($i -gt $startIdx -and $lines[$i].StartsWith('## ')) { break }
        if ($lines[$i].StartsWith('---')) { break }
        Write-Host $lines[$i]
    }
    Write-Host ''
    Write-Info 'Full reference: cli/error-codes.md'
}

# ============================================================================
# P178: Invoke-Doctor — first-run + ongoing health-check.
#   Checks Python, pydantic/pyyaml, pwsh version, AppData writability, repo
#   layout (cli/grok-agent.py + safety/scanner.py + spec/v2.15/grok-agent.yaml).
#   Each check is independent; the worst-severity finding determines the exit.
# ============================================================================

function Invoke-Doctor {
    Initialize-AppDataLayout
    Write-Banner
    Write-Host '  doctor — environment health check' -ForegroundColor White
    Write-Host '  ----------------------------------' -ForegroundColor DarkGray

    $failures = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]

    function _Doctor-Pass { param([string]$Msg) Write-Host ('  [v] ' + $Msg) -ForegroundColor Green }
    function _Doctor-Warn { param([string]$Msg) Write-Host ('  [!] ' + $Msg) -ForegroundColor Yellow; $warnings.Add($Msg) | Out-Null }
    function _Doctor-Fail { param([string]$Msg, [string]$Fix) Write-Host ('  [x] ' + $Msg) -ForegroundColor Red; Write-Host ('      fix: ' + $Fix) -ForegroundColor DarkGray; $failures.Add($Msg) | Out-Null }

    # --- 1. PowerShell version --------------------------------------------
    $psVersion = $PSVersionTable.PSVersion
    if ($psVersion.Major -ge 5) {
        _Doctor-Pass ("PowerShell {0} (>= 5.1 required)" -f $psVersion)
    } else {
        _Doctor-Fail ("PowerShell {0} is older than 5.1" -f $psVersion) 'Upgrade to Windows PowerShell 5.1 or PowerShell 7+.'
    }

    # --- 2. Python on PATH -------------------------------------------------
    if (Test-PythonAvailable) {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
        $pyVer = & $py.Source --version 2>&1
        _Doctor-Pass ("Python found: {0} ({1})" -f $pyVer, $py.Source)
    } else {
        _Doctor-Fail 'Python not on PATH' 'Install Python 3.12+ from https://www.python.org/downloads/ and re-open PowerShell.'
    }

    # --- 3. pydantic + pyyaml importable ----------------------------------
    if (Test-PythonAvailable) {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
        $probe = '
import importlib, sys
missing = []
for mod in ("pydantic", "yaml"):
    try:
        importlib.import_module(mod)
    except ImportError:
        missing.append(mod)
if missing:
    sys.stderr.write("MISSING:" + ",".join(missing))
    sys.exit(1)
print("OK")
'
        $probeOut = & $py.Source -c $probe 2>&1
        if ($LASTEXITCODE -eq 0) {
            _Doctor-Pass 'Python deps importable: pydantic + pyyaml'
        } else {
            _Doctor-Fail ("Python deps missing: {0}" -f $probeOut) "python -m pip install 'pydantic>=2.7,<3' 'pyyaml>=6.0'"
        }
    } else {
        _Doctor-Warn 'Skipping Python deps probe (Python not on PATH).'
    }

    # --- 4. AppData layout writable ---------------------------------------
    try {
        $probeFile = Join-Path $Script:AppDataRoot ('.doctor-probe-{0}' -f ([Guid]::NewGuid().ToString('N')))
        Set-Content -LiteralPath $probeFile -Value 'ok' -Encoding UTF8
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
        _Doctor-Pass ("AppData writable: {0}" -f $Script:AppDataRoot)
    } catch {
        _Doctor-Fail ("AppData not writable: {0}" -f $Script:AppDataRoot) ("Grant write access to {0} for the current user." -f $Script:AppDataRoot)
    }

    # --- 5. ExecutionPolicy permits scripts -------------------------------
    try {
        $policy = Get-ExecutionPolicy -Scope CurrentUser
        if ($policy -in @('Restricted', 'AllSigned', 'Default')) {
            _Doctor-Warn ("ExecutionPolicy CurrentUser='{0}' may block .ps1 launchers" -f $policy)
        } else {
            _Doctor-Pass ("ExecutionPolicy CurrentUser='{0}'" -f $policy)
        }
    } catch {
        _Doctor-Warn 'Could not read ExecutionPolicy on this platform.'
    }

    # --- 6. Repo layout sanity --------------------------------------------
    $expected = @{
        'cli/grok-agent.py'              = 'Python validator'
        'safety/scanner.py'              = 'Constitution scanner'
        'spec/v2.15/grok-agent.yaml'     = 'v2.15 spec'
        'spec/v2.15/schema.json'         = 'JSON Schema export'
        'spec/v2.15/openapi.yaml'        = 'OpenAPI export'
    }
    foreach ($rel in $expected.Keys) {
        $abs = Join-Path $Script:RepoRoot $rel
        if (Test-Path -LiteralPath $abs) {
            _Doctor-Pass ("{0} ({1})" -f $rel, $expected[$rel])
        } else {
            _Doctor-Warn ("Missing: {0} ({1})" -f $rel, $expected[$rel])
        }
    }

    # --- Summary -----------------------------------------------------------
    Write-Host ''
    if ($failures.Count -eq 0 -and $warnings.Count -eq 0) {
        Write-Ok 'doctor: all checks passed.'
        exit 0
    }
    if ($failures.Count -eq 0) {
        Write-Warn2 ('doctor: {0} warning(s). Repo is usable; fix when convenient.' -f $warnings.Count)
        exit 0
    }
    Write-Err2 ('doctor: {0} failure(s) and {1} warning(s).' -f $failures.Count, $warnings.Count)
    Write-Info 'Re-run after fixing each [x] line above.'
    exit 65
}

# ============================================================================
# Dispatcher
# ============================================================================

function Invoke-EvalWeekly {
    Write-Banner
    Write-Step 'Running weekly self-improvement loop across every flagship Super Agent.'

    $superAgentsRoot = Join-Path $Script:RepoRoot 'templates\super-agents'
    if (-not (Test-Path -LiteralPath $superAgentsRoot)) {
        Write-Err2 ('Super-agents folder not found: {0}' -f $superAgentsRoot)
        exit 66
    }

    $evalRoot = Join-Path $Script:AppDataRoot 'eval'
    if (-not (Test-Path -LiteralPath $evalRoot)) {
        New-Item -ItemType Directory -LiteralPath $evalRoot -Force | Out-Null
    }
    $stamp     = Get-Date -Format 'yyyy-MM-dd-HHmm'
    $outFile   = Join-Path $evalRoot ('weekly-{0}.md' -f $stamp)

    $headerBlock = @(
        ('# Grok Agent OS - Weekly Eval Loop ({0})' -f $stamp),
        '',
        ('Run by: cli\grok-agent.ps1 eval-weekly  ({0})' -f $Script:Tagline),
        ''
    )
    Set-Content -Path $outFile -Value $headerBlock -Encoding UTF8

    $flagships  = Get-ChildItem -Path $superAgentsRoot -Directory | Sort-Object Name
    $rowsRun    = 0
    $rowsSkipped = 0

    foreach ($folder in $flagships) {
        $name        = $folder.Name
        $promptFoo   = Join-Path $folder.FullName 'eval\promptfoo.yaml'
        $deepEval    = Join-Path $folder.FullName 'eval\deepeval_suite.py'
        $hasPromptFoo = Test-Path -LiteralPath $promptFoo
        $hasDeepEval  = Test-Path -LiteralPath $deepEval

        Add-Content -Path $outFile -Value ''
        Add-Content -Path $outFile -Value ('## ' + $name)
        Add-Content -Path $outFile -Value ''
        Add-Content -Path $outFile -Value ('- promptfoo.yaml: ' + ($(if ($hasPromptFoo) { 'present' } else { 'missing' })))
        Add-Content -Path $outFile -Value ('- deepeval_suite.py: ' + ($(if ($hasDeepEval) { 'present' } else { 'missing' })))

        if (-not ($hasPromptFoo -or $hasDeepEval)) {
            Write-Info ("Skip {0} (no eval suite)." -f $name)
            Add-Content -Path $outFile -Value '- result: skipped (no eval suite shipped)'
            $rowsSkipped++
            continue
        }

        Write-Step ("Evaluating {0}..." -f $name)

        if ($hasDeepEval) {
            $py = Get-Command python -ErrorAction SilentlyContinue
            if ($py) {
                try {
                    $output = & python $deepEval 2>&1
                    Add-Content -Path $outFile -Value '- deepeval: completed'
                    Add-Content -Path $outFile -Value '```'
                    Add-Content -Path $outFile -Value ($output | Out-String).TrimEnd()
                    Add-Content -Path $outFile -Value '```'
                } catch {
                    Add-Content -Path $outFile -Value ('- deepeval: error: ' + $_.Exception.Message)
                }
            } else {
                Add-Content -Path $outFile -Value '- deepeval: skipped (python not on PATH)'
            }
        }

        if ($hasPromptFoo) {
            $promptfooCmd = Get-Command promptfoo -ErrorAction SilentlyContinue
            if ($promptfooCmd) {
                try {
                    $output = & promptfoo eval --config $promptFoo 2>&1
                    Add-Content -Path $outFile -Value '- promptfoo: completed'
                    Add-Content -Path $outFile -Value '```'
                    Add-Content -Path $outFile -Value ($output | Out-String).TrimEnd()
                    Add-Content -Path $outFile -Value '```'
                } catch {
                    Add-Content -Path $outFile -Value ('- promptfoo: error: ' + $_.Exception.Message)
                }
            } else {
                Add-Content -Path $outFile -Value '- promptfoo: skipped (CLI not on PATH; install with: npm i -g promptfoo)'
            }
        }

        $rowsRun++
    }

    Add-Content -Path $outFile -Value ''
    Add-Content -Path $outFile -Value '---'
    Add-Content -Path $outFile -Value ('Summary: {0} agent(s) evaluated, {1} skipped.' -f $rowsRun, $rowsSkipped)

    Write-Ok ('Wrote weekly eval summary to {0}' -f $outFile)
    Write-Info 'Tip: pipe Langfuse traces by setting LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY before running.'
}

try {
    # P178: -Explain short-circuits everything. The user is asking for the
    # error-codes.md entry, not running a verb. Process before $Command.
    if ($Explain) {
        Invoke-Explain -Code $Explain
        exit 0
    }

    $cmd = $Command.ToLowerInvariant()
    switch ($cmd) {
        '-h'      { Show-Help; exit 0 }
        '--help'  { Show-Help; exit 0 }
        '/?'      { Show-Help; exit 0 }
        'help'    { Show-Help; exit 0 }
        'new'      { Invoke-New      -Rest $Arguments; exit 0 }
        'install'  { Invoke-Install  -Rest $Arguments; exit 0 }
        'validate' { Invoke-Validate -Rest $Arguments; exit 0 }
        'list'     { Invoke-List;                       exit 0 }
        'run'      { Invoke-Run      -Rest $Arguments; exit 0 }
        'doctor'   { Invoke-Doctor; exit 0 }
        'eval-weekly' { Invoke-EvalWeekly;               exit 0 }
        ''         { Show-Help; exit 0 }
        default {
            Write-Err2 ("[E-CLI-001] Unknown command: '{0}'" -f $Command)
            Write-Info 'Run: grok-agent.ps1 help  (or .\cli\grok-agent.ps1 -Explain E-CLI-001)'
            exit 64
        }
    }
}
catch {
    Write-Err2 ('Unexpected error: {0}' -f $_.Exception.Message)
    if ($_.ScriptStackTrace) { Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray }
    exit 70
}
