# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Aggregate every Constitution scanner finding into a single audit log.

Built for xAI, X, Grok and the ecosystem community. ❤️

This script is the BUILD-TIME aggregator behind the marketplace's live
"Constitution Audit Log" dashboard. Pure transparency moat: every finding
the scanner emits, for every shipped agent, is persisted into a single
deterministic JSON document that the marketplace UI reads at build time.

Pipeline:

1. Walk every `templates/<category>/<slug>/grok-agent.yaml`.
2. For each manifest, invoke `python safety/scanner.py scan <path> --json`
   in a subprocess (hard isolation: a scanner crash on one manifest never
   blocks aggregation across the rest).
3. Normalize each finding to the dashboard's expected shape
   (`check`, `severity`, `message`, `article`) — the scanner emits `code`,
   `severity`, `message`, `location`, `article`; we map `code -> check`
   and preserve `location` as a sibling.
4. Produce one aggregated `docs/audit-log.json` with summary counts plus
   a per-manifest block plus a flat findings list (so the marketplace
   index page and per-slug drill-down can both render from one fetch).

Modes:

    python scripts/build-audit-log.py
        Build + write `docs/audit-log.json`. Default mode.

    python scripts/build-audit-log.py --check
        Re-build in memory and diff against the on-disk JSON. Exit 1 if
        drift is detected (i.e. the on-disk audit log is stale). The
        `computed_at` field is excluded from the diff so a fresh re-run
        does not trigger drift purely on a refreshed timestamp.

    python scripts/build-audit-log.py --print <slug>
        Print one agent's audit block (manifest path, max severity,
        findings) and exit. Useful for debugging a single agent without
        regenerating the whole file.

Mirrors the patterns in `scripts/compute-trust-score.py` and
`scripts/export-openapi.py` for consistency: pure stdlib + pyyaml,
deterministic JSON output (sorted slugs, sorted findings within each
manifest by check name), Apache 2.0 header, ecosystem-ally tagline.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from collections import Counter
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
_OUTPUT = _REPO_ROOT / "docs" / "audit-log.json"
_NOW = datetime.now(timezone.utc)

_SCANNER_VERSION = "0.1.0"
_CONSTITUTION_VERSION = "1.0"
_TIMESTAMP_FIELD = "computed_at"


def _category_for(manifest_path: Path) -> str:
    parts = manifest_path.relative_to(_REPO_ROOT).parts
    # Expected shape: templates/<category>/<slug>/grok-agent.yaml
    if len(parts) >= 4 and parts[0] == "templates":
        return parts[1]
    return "unknown"


def _slug_for(manifest_path: Path) -> str:
    return manifest_path.parent.name


def _load_manifest_kind(manifest_path: Path) -> str:
    """Read `kind` from the manifest. Failures degrade to 'unknown' so a
    malformed manifest never blocks the aggregator (the scanner will
    independently surface the YAML problem as a finding).
    """
    try:
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, OSError):
        return "unknown"
    if not isinstance(loaded, dict):
        return "unknown"
    return str(loaded.get("kind", "unknown"))


def _normalize_finding(raw: dict[str, Any]) -> dict[str, Any]:
    """Map scanner finding shape onto the dashboard's expected shape.

    Scanner emits: severity, code, message, location, article
    Dashboard wants: check, severity, message, article (+ location for UX)
    """
    return {
        "check": str(raw.get("code") or raw.get("check") or "unknown"),
        "severity": str(raw.get("severity") or "info"),
        "message": str(raw.get("message") or ""),
        "article": str(raw.get("article") or ""),
        "location": str(raw.get("location") or ""),
    }


def _scan_one(manifest_path: Path) -> dict[str, Any]:
    """Run the scanner against a single manifest and return its block.

    A scanner crash (non-zero exit with no JSON, timeout, JSON parse error)
    is captured as a synthetic critical finding so the aggregator never
    silently loses a manifest.
    """
    rel = str(manifest_path.relative_to(_REPO_ROOT))
    try:
        result = subprocess.run(
            [sys.executable, str(_SCANNER), "scan", str(manifest_path), "--json"],
            capture_output=True, text=True, check=False, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return _synthetic_crash_block(
            manifest_path,
            "scanner-timeout",
            "Scanner exceeded the 60s subprocess timeout for this manifest.",
        )
    except OSError as exc:
        return _synthetic_crash_block(
            manifest_path,
            "scanner-oserror",
            f"Scanner subprocess failed to launch: {exc}",
        )

    raw_stdout = result.stdout or ""
    try:
        data = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        # Surface the stderr tail so the operator can debug the crash.
        tail = (result.stderr or "").strip().splitlines()[-3:]
        return _synthetic_crash_block(
            manifest_path,
            "scanner-bad-json",
            (
                f"Scanner did not return valid JSON (parse error: {exc}). "
                f"Last stderr: {' | '.join(tail) or '<empty>'}"
            ),
        )

    raw_findings = data.get("findings") or []
    findings = [_normalize_finding(f) for f in raw_findings if isinstance(f, dict)]
    findings.sort(key=lambda f: (f["check"], f["location"], f["message"]))

    block = {
        "manifest_path": rel,
        "category": _category_for(manifest_path),
        "kind": _load_manifest_kind(manifest_path),
        "max_severity": str(data.get("max_severity") or "info"),
        "has_errors": bool(data.get("has_errors")),
        "findings": findings,
    }
    return block


def _synthetic_crash_block(
    manifest_path: Path, check_id: str, message: str
) -> dict[str, Any]:
    """Build a per-manifest block representing a scanner failure.

    The synthetic finding is severity=error so audit log readers (and the
    `manifests_with_findings` count) treat the crash as a real problem.
    """
    rel = str(manifest_path.relative_to(_REPO_ROOT))
    crash = {
        "check": f"meta.{check_id}",
        "severity": "error",
        "message": message,
        "article": "VIII",
        "location": "<scanner-subprocess>",
    }
    return {
        "manifest_path": rel,
        "category": _category_for(manifest_path),
        "kind": _load_manifest_kind(manifest_path),
        "max_severity": "error",
        "has_errors": True,
        "findings": [crash],
    }


def _count_registered_checks() -> int:
    """Count `@register(...)` decorators in safety/scanner.py.

    The dashboard needs to display "checks per manifest" so creators
    understand the audit surface. We count the decorators rather than
    parsing the scanner's `info` output so this script stays cheap and
    deterministic (no extra subprocess just for the count).
    """
    text = _SCANNER.read_text(encoding="utf-8")
    return sum(
        1 for line in text.splitlines() if line.lstrip().startswith("@register(")
    )


def build_payload() -> dict[str, Any]:
    if not _TEMPLATES_ROOT.is_dir():
        sys.stderr.write(f"ERROR: templates/ not found under {_REPO_ROOT}\n")
        sys.exit(66)

    manifests = sorted(_TEMPLATES_ROOT.rglob("grok-agent.yaml"))
    by_manifest: dict[str, dict[str, Any]] = {}
    flat_findings: list[dict[str, Any]] = []

    severity_counts: Counter[str] = Counter()
    article_counts: Counter[str] = Counter()
    check_counts: Counter[str] = Counter()
    manifests_clean = 0
    manifests_with_findings = 0

    for manifest_path in manifests:
        block = _scan_one(manifest_path)
        slug = _slug_for(manifest_path)
        by_manifest[slug] = block

        if block["findings"]:
            manifests_with_findings += 1
        else:
            manifests_clean += 1

        for f in block["findings"]:
            severity_counts[f["severity"]] += 1
            if f["article"]:
                article_counts[f["article"]] += 1
            check_counts[f["check"]] += 1
            flat_findings.append({
                "slug": slug,
                "category": block["category"],
                "manifest_path": block["manifest_path"],
                "check": f["check"],
                "severity": f["severity"],
                "message": f["message"],
                "article": f["article"],
                "location": f["location"],
            })

    # Deterministic ordering: slugs alphabetical, flat findings by
    # (slug, check, location) for diff-friendly output.
    by_manifest_sorted = dict(sorted(by_manifest.items()))
    flat_findings.sort(key=lambda f: (f["slug"], f["check"], f["location"]))

    summary = {
        "total_findings": sum(severity_counts.values()),
        "by_severity": {
            "error": severity_counts.get("error", 0),
            "warn":  severity_counts.get("warn", 0),
            "info":  severity_counts.get("info", 0),
        },
        "by_article": dict(sorted(article_counts.items())),
        "by_check":   dict(sorted(check_counts.items())),
        "manifests_clean":         manifests_clean,
        "manifests_with_findings": manifests_with_findings,
    }

    return {
        _TIMESTAMP_FIELD:        _NOW.isoformat(),
        "scanner_version":       _SCANNER_VERSION,
        "constitution_version":  _CONSTITUTION_VERSION,
        "manifest_count":        len(by_manifest_sorted),
        "checks_per_manifest":   _count_registered_checks(),
        "summary":               summary,
        "by_manifest":           by_manifest_sorted,
        "findings":              flat_findings,
    }


def _serialize(payload: dict[str, Any]) -> str:
    """Deterministic JSON for diff-friendly checked-in output."""
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def _strip_timestamp(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with the volatile timestamp removed for diffing."""
    clone = dict(payload)
    clone.pop(_TIMESTAMP_FIELD, None)
    return clone


def _print_one(payload: dict[str, Any], slug: str) -> int:
    block = payload["by_manifest"].get(slug)
    if block is None:
        sys.stderr.write(f"X  Unknown slug: {slug}\n")
        sys.stderr.write(
            "   Known slugs: "
            + ", ".join(sorted(payload["by_manifest"].keys())[:10])
            + ", ...\n"
        )
        return 66
    sys.stdout.write(json.dumps(block, indent=2, ensure_ascii=False) + "\n")
    return 0


def _check_drift(payload: dict[str, Any]) -> int:
    if not _OUTPUT.is_file():
        sys.stderr.write(
            f"X  {_OUTPUT.relative_to(_REPO_ROOT)} missing. "
            "Run `python scripts/build-audit-log.py`.\n"
        )
        return 1
    try:
        on_disk = json.loads(_OUTPUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sys.stderr.write(
            f"X  {_OUTPUT.relative_to(_REPO_ROOT)} is not valid JSON.\n"
        )
        return 1
    if _strip_timestamp(on_disk) != _strip_timestamp(payload):
        sys.stderr.write(
            "X  Audit log drift detected. Re-run "
            "`python scripts/build-audit-log.py`.\n"
        )
        return 1
    sys.stdout.write("OK No audit log drift.\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Aggregate every Constitution scanner finding into "
            "docs/audit-log.json. Built for xAI, X, Grok and the "
            "ecosystem community."
        )
    )
    p.add_argument(
        "--check", action="store_true",
        help="Exit 1 if on-disk audit log differs from a fresh build.",
    )
    p.add_argument(
        "--print", dest="print_slug", metavar="SLUG",
        help="Print one agent's audit block and exit.",
    )
    args = p.parse_args(argv)

    try:
        payload = build_payload()
    except Exception:
        sys.stderr.write(
            "ERROR: aggregator crashed before producing a payload:\n"
        )
        traceback.print_exc(file=sys.stderr)
        return 70

    if args.print_slug:
        return _print_one(payload, args.print_slug)

    if args.check:
        return _check_drift(payload)

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(_serialize(payload), encoding="utf-8")
    sys.stdout.write(
        f"OK Wrote {_OUTPUT.relative_to(_REPO_ROOT)} "
        f"({payload['manifest_count']} manifests, "
        f"{payload['summary']['total_findings']} findings, "
        f"{payload['summary']['manifests_clean']} clean)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
