# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

<#
.SYNOPSIS
    Grok Agent OS — Windows-first CLI for installing, creating, validating,
    listing, and running Grok agents declared via grok-agent.yaml v2.15.

.DESCRIPTION
    Built to help xAI and Grok win the agent platform battle on X.
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
    [switch]$NoBanner
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ============================================================================
# Constants
# ============================================================================

$Script:Version       = '0.1.0'
$Script:Tagline       = 'Built to help xAI and Grok win.'
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

# Windows AppData paths (local-first, no admin required)
$Script:AppDataRoot = Join-Path $env:LOCALAPPDATA 'grok-agent'
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
        # Drop trailing comment if present
        if ($value -match '^(?<v>.*?)(?:\s+#.*)?$') { $value = $matches['v'].Trim() }
        # Strip surrounding quotes
        if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") { $value = $matches[1] }
        return $value
    }
    return $null
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
# Built to help xAI and Grok win.
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

> Built to help xAI and Grok win.

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
        Write-Step 'Reading manifest from stdin (paste YAML, then press Ctrl-Z then Enter)...'
        $manifestText = [Console]::In.ReadToEnd()
        $sourceLabel  = '<stdin>'
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Yaml)) {
        $manifestText = $Yaml
        $sourceLabel  = '<inline>'
    }
    elseif ($Rest -and $Rest.Count -ge 1) {
        $arg = $Rest[0]
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
    $entries | Sort-Object Name | Format-Table -AutoSize -Property Name, Kind, Version, Description
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
    $launcherRel = Get-YamlScalar -YamlText $text -Field 'launcher'
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
# Dispatcher
# ============================================================================

try {
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
        ''         { Show-Help; exit 0 }
        default {
            Write-Err2 ("Unknown command: '{0}'" -f $Command)
            Write-Info 'Run: grok-agent.ps1 help'
            exit 64
        }
    }
}
catch {
    Write-Err2 ('Unexpected error: {0}' -f $_.Exception.Message)
    if ($_.ScriptStackTrace) { Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray }
    exit 70
}
