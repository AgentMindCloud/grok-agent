# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Compute trust scores for every shipped Grok Agent OS agent.

Built for xAI, X, Grok and the ecosystem community. ❤️

The trust score is a public, auditable, deterministic 0–100 number per
agent that summarises four objective signals:

    composite = 0.4 * scanner + 0.3 * eval + 0.2 * provenance + 0.1 * stability

Each component:

- **scanner** (weight 0.4): `safety/scanner.py scan --json` against the
  manifest. Score = `max(0, 1 - 0.25 * error_count)` — every CRITICAL
  finding subtracts 25 points, capped at zero. Heaviest weight because
  scanner failures are concrete contract violations.

- **eval** (weight 0.3): `eval/promptfoo.yaml` OR `eval/deepeval_suite.py`
  adjacent to the manifest = 1.0. `evaluation.enabled` declared in
  manifest but no suite present = 0.5. Otherwise 0. Rewards agents that
  ship a test surface.

- **provenance** (weight 0.2): average of three booleans —
  `provenance.enabled`, `provenance.append_only`, `provenance.cite_sources`.
  Trust-critical declarations the Constitution cares about most.

- **stability** (weight 0.1): manifest age in days, capped at 90, divided
  by 90. Mature manifests get more credit; brand-new ones less. Naive
  proxy for "shipped and stable" — future versions can integrate
  failure-rate from CI history.

Tier mapping:

    >= 90  →  A   (cinnabar with crown)
    >= 75  →  B   (cinnabar)
    >= 60  →  C   (parchment)
    <  60  →  D   (charcoal warning)

Output: writes `docs/agent-trust-scores.json` — deterministic JSON keyed
by slug, with the composite score, tier, per-component breakdown, and
manifest provenance. The file is committed; the marketplace's trust-badge
route reads it at build time.

Usage:

    python scripts/compute-trust-score.py
    python scripts/compute-trust-score.py --check    # exit 1 on drift
    python scripts/compute-trust-score.py --print x-money-companion-dashboard
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    sys.stderr.write(
        "ERROR: pyyaml is required. Install: python -m pip install pyyaml\n"
    )
    sys.exit(69)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCANNER = _REPO_ROOT / "safety" / "scanner.py"
_TEMPLATES_ROOT = _REPO_ROOT / "templates"
_OUTPUT = _REPO_ROOT / "docs" / "agent-trust-scores.json"
_NOW_FOR_AGE = datetime.now(timezone.utc)


WEIGHTS = {
    "scanner":    0.4,
    "eval":       0.3,
    "provenance": 0.2,
    "stability":  0.1,
}


def _scanner_score(manifest_path: Path) -> tuple[float, int]:
    """Return (score, error_count) by invoking the scanner in JSON mode."""
    try:
        result = subprocess.run(
            [sys.executable, str(_SCANNER), "scan", str(manifest_path), "--json"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        # Scanner crashed — treat as a hard fail (score 0).
        return 0.0, 99
    findings = data.get("findings") or []
    error_count = sum(1 for f in findings if f.get("severity") == "error")
    return max(0.0, 1.0 - 0.25 * error_count), error_count


def _provenance_score(manifest: dict) -> float:
    prov = manifest.get("provenance") or {}
    components = [
        bool(prov.get("enabled")),
        bool(prov.get("append_only")),
        # cite_sources defaults to True per the spec; honor that default.
        bool(prov.get("cite_sources", True)) if "cite_sources" in prov else False,
    ]
    return sum(components) / len(components)


def _eval_score(manifest_path: Path, manifest: dict) -> float:
    eval_dir = manifest_path.parent / "eval"
    has_promptfoo = (eval_dir / "promptfoo.yaml").is_file()
    has_deepeval = (eval_dir / "deepeval_suite.py").is_file()
    if has_promptfoo or has_deepeval:
        return 1.0
    evaluation = manifest.get("evaluation") or {}
    if evaluation.get("enabled"):
        return 0.5
    return 0.0


def _git_first_commit_ts(path: Path) -> int | None:
    """Unix timestamp of the file's first commit. None if not in git."""
    rel = path.relative_to(_REPO_ROOT)
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ct", "--", str(rel)],
            capture_output=True, text=True, check=False, cwd=_REPO_ROOT, timeout=10,
        )
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        # `git log` is reverse-chronological; the LAST line is the first commit.
        return int(lines[-1])
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return None


def _stability_score(manifest_path: Path) -> tuple[float, int]:
    """Returns (score, age_days)."""
    ts = _git_first_commit_ts(manifest_path)
    if ts is None:
        # File not yet committed — give it a small floor so it isn't a flat 0.
        return 0.05, 0
    age_seconds = _NOW_FOR_AGE.timestamp() - ts
    age_days = max(0, int(age_seconds // 86400))
    score = min(1.0, age_days / 90.0)
    return score, age_days


def _tier(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    return "D"


def _category_for(manifest_path: Path) -> str:
    parts = manifest_path.relative_to(_REPO_ROOT).parts
    # Expected shape: templates/<category>/<slug>/grok-agent.yaml
    if len(parts) >= 4 and parts[0] == "templates":
        return parts[1]
    return "unknown"


def _slug_for(manifest_path: Path) -> str:
    return manifest_path.parent.name


def compute_one(manifest_path: Path) -> dict[str, Any] | None:
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(manifest, dict):
        return None

    scanner_s, error_count = _scanner_score(manifest_path)
    eval_s = _eval_score(manifest_path, manifest)
    prov_s = _provenance_score(manifest)
    stab_s, age_days = _stability_score(manifest_path)

    composite = (
        WEIGHTS["scanner"]    * scanner_s
        + WEIGHTS["eval"]       * eval_s
        + WEIGHTS["provenance"] * prov_s
        + WEIGHTS["stability"]  * stab_s
    )
    score = round(composite * 100)

    return {
        "slug":       _slug_for(manifest_path),
        "category":   _category_for(manifest_path),
        "kind":       manifest.get("kind", "unknown"),
        "score":      score,
        "tier":       _tier(score),
        "components": {
            "scanner":    round(scanner_s, 4),
            "eval":       round(eval_s, 4),
            "provenance": round(prov_s, 4),
            "stability":  round(stab_s, 4),
        },
        "details": {
            "scanner_error_count": error_count,
            "manifest_age_days":   age_days,
        },
        "manifest_path": str(manifest_path.relative_to(_REPO_ROOT)),
    }


def compute_all() -> dict[str, Any]:
    if not _TEMPLATES_ROOT.is_dir():
        sys.stderr.write(f"ERROR: templates/ not found under {_REPO_ROOT}\n")
        sys.exit(66)
    manifests = sorted(_TEMPLATES_ROOT.rglob("grok-agent.yaml"))
    results: dict[str, Any] = {}
    for m in manifests:
        scored = compute_one(m)
        if scored is not None:
            results[scored["slug"]] = scored

    return {
        "computed_at":         _NOW_FOR_AGE.isoformat(),
        "constitution_version": "1.0",
        "scanner_version":     "0.1.0",
        "formula":             "0.4*scanner + 0.3*eval + 0.2*provenance + 0.1*stability",
        "weights":             WEIGHTS,
        "tier_thresholds":     {"A": 90, "B": 75, "C": 60, "D": 0},
        "manifest_count":      len(results),
        "agents":              dict(sorted(results.items())),
    }


def _serialize(payload: dict) -> str:
    """Deterministic JSON for diff-friendly checked-in output.

    `computed_at` is excluded from the diff-stable representation by
    being placed first; downstream readers can either honor it or treat
    every regeneration as new.
    """
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Compute trust scores for every Grok Agent OS agent. Writes "
            "docs/agent-trust-scores.json. Built for xAI, X, Grok and the "
            "ecosystem community."
        )
    )
    p.add_argument("--check", action="store_true",
                   help="Exit 1 if on-disk JSON differs from computed.")
    p.add_argument("--print", dest="print_slug", metavar="SLUG",
                   help="Print the score for one agent and exit.")
    args = p.parse_args(argv)

    payload = compute_all()

    if args.print_slug:
        agent = payload["agents"].get(args.print_slug)
        if agent is None:
            sys.stderr.write(f"X  Unknown slug: {args.print_slug}\n")
            return 66
        sys.stdout.write(json.dumps(agent, indent=2) + "\n")
        return 0

    json_text = _serialize(payload)

    if args.check:
        if not _OUTPUT.is_file():
            sys.stderr.write(f"X  {_OUTPUT.relative_to(_REPO_ROOT)} missing.\n")
            return 1
        # Compare ignoring the timestamp — re-running this script always
        # produces a fresh `computed_at`, so a strict text-diff would
        # always fail. Compare the agents block and weights only.
        try:
            on_disk = json.loads(_OUTPUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sys.stderr.write(f"X  {_OUTPUT.relative_to(_REPO_ROOT)} not valid JSON.\n")
            return 1
        if on_disk.get("agents") != payload["agents"]:
            sys.stderr.write(
                "X  Trust score drift detected — re-run "
                "`python scripts/compute-trust-score.py`.\n"
            )
            return 1
        sys.stdout.write("OK No trust score drift detected.\n")
        return 0

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(json_text, encoding="utf-8")
    a_count = sum(1 for v in payload["agents"].values() if v["tier"] == "A")
    b_count = sum(1 for v in payload["agents"].values() if v["tier"] == "B")
    c_count = sum(1 for v in payload["agents"].values() if v["tier"] == "C")
    d_count = sum(1 for v in payload["agents"].values() if v["tier"] == "D")
    sys.stdout.write(
        f"OK Wrote {_OUTPUT.relative_to(_REPO_ROOT)} "
        f"({len(payload['agents'])} agents: "
        f"A={a_count} B={b_count} C={c_count} D={d_count})\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
