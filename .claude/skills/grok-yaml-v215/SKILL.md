---
name: grok-yaml-v215
description: Use this skill whenever working with `grok-agent.yaml` files in the AgentMindCloud/grok-agent repository — creating new manifests for X Money tools, creator templates, x-native agents, general agents, or Super Agents; validating existing manifests; debugging schema errors; converting v2.14 manifests to v2.15; writing the official schema in `spec/v2.15/`; or building Pydantic validation models. Triggers on any task involving the v2.15 manifest format, the unified schema, the public_api tool type, the windows extension section, the multi_agent block, the real_time_x section, the Agent Constitution rules, or any phrase like "build manifest", "validate yaml", "create grok-agent.yaml", "extend schema", "v2.14 to v2.15".
---

# grok-yaml-v215

primary reference for the v2.15 manifest schema. Every agent in the platform declares one of these. The schema is the heart of the project — get this right and every downstream prompt is easier.

## Core principles

1. **v2.14 backwards compatibility is mandatory.** Any v2.14 manifest must validate as v2.15 with no changes. v2.15 is purely additive.
2. **Every field is documented inline** with a comment explaining purpose.
3. **Required fields stay minimal.** Most sections are optional — agents only add what they need.
4. **Pydantic v2 is the validation truth source.** YAML loads to dict, dict feeds Pydantic, Pydantic raises on invalid.

## Required top-level fields

```yaml
version: "2.15"          # Always quoted string. Accepts "2.14" for backwards compat.
kind: "agent"            # Enum — see kinds list below
name: "my-agent"         # kebab-case, must match folder name
description: "..."       # 1-2 sentence purpose
author: "@JanSol0s"      # X handle of creator
license: "Apache-2.0"    # SPDX identifier — Apache-2.0 is mandatory for this project
```

## Kind enum (all valid values)

```yaml
kind:
  - agent                           # generic agent
  - finance-dashboard               # Streamlit-based finance UI (X Money Companion Dashboard)
  - alpha-engine                    # market intelligence agent (Cashtag Alpha)
  - creator-payout-optimizer        # earnings forecasting + content optimization
  - vision-analyzer                 # image/document vision agent (Receipt Analyzer)
  - super-agent                     # flagship orchestrated agent (Living Narrative Fabric and similar)
  - x-native                        # runs primarily via "grok install this" on X
  - creator-template                # creator program templates (content-ideas, reply-drafter, and similar)
```

## Optional sections (declare only what you need)

### `windows:` — Windows-specific extensions
```yaml
windows:
  launcher: "launcher.ps1"                              # PowerShell launcher path (relative to manifest)
  appdata_folder: "grok-agent/{name}"                   # Folder under $env:LOCALAPPDATA
  defender_exclusion_recommended: false                 # Set true if agent needs Defender exclusion
  registry_keys: []                                     # List of registry keys read/written (empty = none)
  min_powershell_version: "5.1"                         # Minimum PS version
  requires_admin: false                                 # Should always be false — admin = bad UX
```

### `grok:` — Grok 4.3 model configuration
```yaml
grok:
  model: "grok-4.3"                                     # Model identifier
  temperature: 0.7                                      # 0.0-2.0
  max_tokens: 4096
  system_prompt_file: "prompts/system.md"               # Path to system prompt
  tool_calling: true                                    # Enable function/tool calling
  vision: false                                         # Enable vision input (true for Tool #4)
```

### `multi_agent:` — Multi-agent coordination
```yaml
multi_agent:
  role: "orchestrator"                                  # orchestrator | worker | observer
  delegates_to:                                         # Agents this one can call
    - "x-money-vision-analyzer"
    - "x-smart-cashtag-alpha-engine"
  shared_memory: "mem0://grok-agent-shared"             # Optional shared memory namespace
```

### `real_time_x:` — X integration (for x-native agents)
```yaml
real_time_x:
  enabled: true
  consent_required: true                                # MANDATORY true for any agent that posts
  triggers:
    - mention                                           # Fires on @mention
    - dm                                                # Fires on DM
    - schedule                                          # Fires on cron schedule
    - cashtag_change                                    # Fires when watched cashtag moves >X%
  schedule_cron: "0 8 * * *"                            # If schedule trigger
  cashtag_threshold_pct: 5.0                            # If cashtag_change trigger
  posts: false                                          # Can this agent post? Default false.
  reply_only: true                                      # If posts true, restrict to replies?
```

### `tools:` — Tool definitions (Grok function calling)
```yaml
tools:
  - name: "fetch_x_money_balance"
    type: "public_api"                                  # public_api | local_function | mcp_server
    description: "Get current X Money balance for the authenticated user"
    parameters:
      schema:                                           # JSON Schema
        type: "object"
        properties:
          user_id: { type: "string" }
        required: ["user_id"]
    api:
      url: "https://api.x.com/v1/payments/balance"
      method: "GET"
      auth: "bearer"
      env_var: "X_API_TOKEN"
      rate_limit: 60                                    # requests per minute
```

### `public_apis:` — Free API integrations (Super Agents use many)
```yaml
public_apis:
  - name: "newsapi"
    base_url: "https://newsapi.org/v2"
    auth_env_var: "NEWSAPI_KEY"
    free_tier_quota: "100/day"
  - name: "semantic_scholar"
    base_url: "https://api.semanticscholar.org/graph/v1"
    auth: "none"                                        # No auth needed
    rate_limit: 100                                     # per 5 minutes
  - name: "data_gov"
    base_url: "https://api.data.gov"
    auth_env_var: "DATA_GOV_KEY"
```

### `constitution:` — Agent Constitution rules
```yaml
constitution:
  rules:
    - "Never publish content without provenance trail"
    - "Always show 'Not financial advice' on finance UI"
    - "Never act on real-world without explicit user consent"
    - "Flag contradictions across sources, do not silently resolve"
    - "Refuse requests that would harm xAI's mission or X's community"
  consent_gates:                                        # Actions requiring explicit user approval
    - publish_to_x
    - send_dm
    - move_funds
    - modify_local_files_outside_appdata
```

### `safety:` — Safety scanner config
```yaml
safety:
  pii_handling: "local-only"                            # local-only | redacted-cloud | none
  data_retention_days: 90                               # Auto-delete user data after N days
  scanner_severity_floor: "warn"                        # info | warn | error
  forbidden_actions:
    - scrape_authenticated_x_content
    - impersonate_user_identity
    - bypass_safety_scanner
```

### `dependencies:` — Python/system deps
```yaml
dependencies:
  python:
    version: "^3.12"
    packages:
      - "streamlit ^1.33"
      - "pandas ^2.2"
      - "pydantic ^2.7"
  system:
    - "powershell >= 5.1"
```

## Three reference examples (copy and adapt)

### Example 1: Minimal agent (smallest valid manifest)
```yaml
version: "2.15"
kind: "agent"
name: "hello-grok"
description: "Minimal example — proves the schema works."
author: "@JanSol0s"
license: "Apache-2.0"
```

### Example 2: X Money tool (finance-dashboard)
```yaml
version: "2.15"
kind: "finance-dashboard"
name: "x-money-companion-dashboard"
description: "Personal X Money command center — overview, transactions, analytics, Grok insights, tax export, alerts."
author: "@JanSol0s"
license: "Apache-2.0"

windows:
  launcher: "launcher.ps1"
  appdata_folder: "grok-agent/x-money-companion-dashboard"
  min_powershell_version: "5.1"
  requires_admin: false

grok:
  model: "grok-4.3"
  temperature: 0.3
  system_prompt_file: "prompts/system.md"
  tool_calling: true

tools:
  - name: "categorize_transaction"
    type: "local_function"
    description: "Categorize an X Money transaction using Grok"
    parameters:
      schema:
        type: "object"
        properties:
          amount: { type: "number" }
          counterparty: { type: "string" }
          memo: { type: "string" }
        required: ["amount", "counterparty"]

constitution:
  rules:
    - "Always show 'Not financial advice' banner on every page"
    - "Never share transaction data outside local SQLite without explicit consent"
  consent_gates:
    - export_tax_report
    - sync_to_cloud

safety:
  pii_handling: "local-only"
  data_retention_days: 365
```

### Example 3: Super Agent (orchestrated)
```yaml
version: "2.15"
kind: "super-agent"
name: "living-narrative-fabric"
description: "Living, versioned synthesis of X + news + academic + government data with full provenance and contradiction detection."
author: "@JanSol0s"
license: "Apache-2.0"

windows:
  launcher: "launcher.ps1"
  appdata_folder: "grok-agent/super-agents/living-narrative-fabric"

grok:
  model: "grok-4.3"
  temperature: 0.5
  system_prompt_file: "prompts/system.md"
  tool_calling: true

multi_agent:
  role: "orchestrator"
  delegates_to: []
  shared_memory: "mem0://grok-agent-shared"

public_apis:
  - name: "newsapi"
    base_url: "https://newsapi.org/v2"
    auth_env_var: "NEWSAPI_KEY"
  - name: "gnews"
    base_url: "https://gnews.io/api/v4"
    auth_env_var: "GNEWS_KEY"
  - name: "semantic_scholar"
    base_url: "https://api.semanticscholar.org/graph/v1"
    auth: "none"
  - name: "data_gov"
    base_url: "https://api.data.gov"
    auth_env_var: "DATA_GOV_KEY"
  - name: "x_search"
    base_url: "via_grok_4.3"
    auth_env_var: "XAI_API_KEY"

constitution:
  rules:
    - "Never publish without provenance"
    - "Flag contradictions, do not resolve them silently"
    - "Source citations are mandatory in every output"
    - "User can rewind to any prior state — synthesis is versioned"
  consent_gates:
    - publish_synthesis
    - export_provenance_log

safety:
  pii_handling: "local-only"
  data_retention_days: 730
  scanner_severity_floor: "warn"
```

## Common mistakes (avoid these)

| ❌ Wrong | ✅ Right | Why |
|---|---|---|
| `version: 2.15` | `version: "2.15"` | Must be string for backwards compat with v2.14 string format |
| `name: My Agent` | `name: "my-agent"` | Must match folder name; kebab-case |
| `license: MIT` | `license: "Apache-2.0"` | Apache 2.0 is mandatory |
| `kind: financeDashboard` | `kind: "finance-dashboard"` | Enum value, kebab-case |
| Missing disclaimer in finance kind | Constitution rule for "Not financial advice" | Required by CONSTRAINTS |
| `posts: true` without `consent_required: true` | Pair them | Posting without consent is forbidden |
| Hardcoded API keys in manifest | `auth_env_var: "X_API_TOKEN"` | Never commit keys |
| `requires_admin: true` | `requires_admin: false` | Admin = bad UX, almost never justified |

## v2.14 → v2.15 migration

What's new in v2.15 vs v2.14:
- `windows:` section (entirely new)
- `multi_agent:` section (entirely new)
- `real_time_x:` section (entirely new)
- `public_apis:` section (entirely new)
- `tools[].type: public_api` (new tool type — v2.14 only had local_function)
- `constitution:` section (entirely new)
- New kinds: `super-agent`, `x-native`, `creator-template` (v2.14 had agent, finance-dashboard, alpha-engine, creator-payout-optimizer, vision-analyzer)

A v2.14 manifest with NONE of these sections validates as v2.15 unchanged. The only required change to "upgrade" is `version: "2.14"` → `version: "2.15"` — and even that's optional (v2.14 strings are accepted).

## Pydantic validation skeleton (use in `cli/grok-agent.py`)

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

KindLiteral = Literal[
    "agent", "finance-dashboard", "alpha-engine",
    "creator-payout-optimizer", "vision-analyzer",
    "super-agent", "x-native", "creator-template"
]

class WindowsSection(BaseModel):
    launcher: Optional[str] = None
    appdata_folder: Optional[str] = None
    defender_exclusion_recommended: bool = False
    registry_keys: list[str] = Field(default_factory=list)
    min_powershell_version: str = "5.1"
    requires_admin: bool = False

class GrokSection(BaseModel):
    model: str = "grok-4.3"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, gt=0)
    system_prompt_file: Optional[str] = None
    tool_calling: bool = True
    vision: bool = False

class GrokAgentManifest(BaseModel):
    version: str  # accepts "2.14" or "2.15"
    kind: KindLiteral
    name: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    description: str = Field(..., min_length=10)
    author: str
    license: Literal["Apache-2.0"]
    windows: Optional[WindowsSection] = None
    grok: Optional[GrokSection] = None
    # ... add other sections as Optional[...]

    @classmethod
    def validate_yaml(cls, path: str) -> "GrokAgentManifest":
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
```

## Validation command

```powershell
python cli/grok-agent.py validate templates/finance/x-money-companion-dashboard/grok-agent.yaml
# Returns:
# ✅ Valid v2.15 manifest
# Or: ❌ ValidationError: <field>: <message>
```

If a manifest fails: read the Pydantic error, fix the field, re-validate. Don't guess.
