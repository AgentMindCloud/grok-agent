<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# `AgentMindCloud/grok-agent/actions/validate-manifest`

> Reusable GitHub Action — validate `grok-agent.yaml` v2.15 manifests against the canonical Pydantic schema **and** the Constitution scanner. Built for xAI, X, Grok and the ecosystem community. ❤️

Drop into any downstream repo's CI to enforce the v2.15 standard without vendoring `cli/grok-agent.py` or `safety/scanner.py`.

## Usage

### Single manifest

```yaml
- name: Validate manifest
  uses: AgentMindCloud/grok-agent/actions/validate-manifest@main
  with:
    path: grok-agent.yaml
```

### Folder containing one manifest

```yaml
- uses: AgentMindCloud/grok-agent/actions/validate-manifest@main
  with:
    path: my-agent/
```

### Many manifests (glob)

```yaml
- uses: AgentMindCloud/grok-agent/actions/validate-manifest@main
  with:
    path: agents/**/grok-agent.yaml
    strict: 'true'
    severity-floor: 'error'
```

### Pin to a release tag

For reproducible CI, pin to a tag (recommended once `v1` is cut):

```yaml
- uses: AgentMindCloud/grok-agent/actions/validate-manifest@v1
```

## Inputs

| Input            | Required | Default  | Description |
|------------------|----------|----------|-------------|
| `path`           | yes      | —        | A `.yaml` file, a folder containing one, or a glob (`agents/**/grok-agent.yaml`). |
| `strict`         | no       | `false`  | Run validation in strict mode (extra=forbid at the root + schema_meta blocks). |
| `scanner`        | no       | `true`   | Also run the Constitution scanner (`safety/scanner.py`). |
| `severity-floor` | no       | `warn`   | Hide scanner findings below this severity (`info` / `warn` / `error`). |
| `python-version` | no       | `3.12`   | Python version on the runner. |

## Outputs

| Output           | Description |
|------------------|-------------|
| `manifest-count` | Number of manifests this run validated. |
| `status`         | `passed` if all clean, `failed` otherwise. |

## What it actually does

The action is a **composite** that:

1. Sets up Python at `python-version` (default 3.12).
2. Installs `pydantic>=2.7,<3` and `pyyaml>=6.0`.
3. Resolves `path` into one or more `.yaml` files.
4. For each file, runs `python cli/grok-agent.py validate <path>` (the canonical Pydantic v2.15 validator).
5. For each file, optionally runs `python safety/scanner.py scan <path> --severity-floor <floor>` (the 34-check Constitution scanner).
6. Fails the step if **any** file fails either gate.

The `cli/grok-agent.py` and `safety/scanner.py` files come from the action's own clone of `AgentMindCloud/grok-agent` — pinning the action to `@v1` (or any other ref) pins both the validator and scanner to that ref deterministically.

## Why this matters

Every downstream repo that adopts the v2.15 standard otherwise has to vendor 850 lines of Pydantic + 1500 lines of scanner code, then update both whenever the spec evolves. This action makes the standard **portable**: one line in a workflow, full v2.15 compliance, automatic upgrade when the standard advances.

## Example end-to-end workflow

```yaml
name: Manifest CI

on:
  pull_request:
    paths:
      - '**/grok-agent.yaml'
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: AgentMindCloud/grok-agent/actions/validate-manifest@main
        with:
          path: '**/grok-agent.yaml'
          strict: 'true'
          severity-floor: 'warn'
```

## Roadmap

- **v1.0** — first stable release, pinned to a tag.
- **v1.1** — output the full `Finding[]` list as a JSON artifact for downstream automation.
- **v1.2** — optionally post a PR comment summarising the worst findings (gated by a `comment-on-pr: 'true'` input).
- **v2.0** — switch to a published Docker action so cold-start cost falls below 5 seconds.

## License

Apache-2.0. See [LICENSE](https://github.com/AgentMindCloud/grok-agent/blob/main/LICENSE).

Built for xAI, X, Grok and the ecosystem community. ❤️
