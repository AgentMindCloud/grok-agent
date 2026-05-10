# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Aggregate per-Super-Agent eval history into a single dashboard JSON.

Built for xAI, X, Grok and the ecosystem community. ❤️

This script is the BUILD-TIME aggregator behind the marketplace's eval
dashboard. The dashboard fetches one deterministic JSON document at build
time; this script produces it.

Pipeline:

1. Walk every `templates/super-agents/<slug>/grok-agent.yaml`.
2. Read the manifest's `evaluation.deepeval.metrics` (declared metric set)
   so the dashboard can render a row per metric whether or not history
   exists yet.
3. Look for per-run history under `eval/history/*.jsonl` adjacent to the
   manifest. Each line of each `.jsonl` is one run record with the shape:

       {"run_id": "<id>", "ts": "<ISO8601>", "metrics": {"<m>": <0..1>}}

   Records missing `run_id` get a stable synthesized id from the file +
   line number. Records missing `ts` are dropped from trend computations
   but kept in the runs list with `ts: null`.
4. Aggregate into `docs/eval-history.json` with summary counts, latest
   metrics per agent, and a 7-day delta per metric (latest score minus
   the most recent score whose timestamp is at least 7 days older than
   the latest run).

Modes:

    python scripts/build-eval-history.py
        Build + write `docs/eval-history.json`. Default mode. If a
        Super Agent has no history under `eval/history/`, an empty
        runs list is emitted (the dashboard handles this gracefully).

    python scripts/build-eval-history.py --seed
        Same as default, but for any Super Agent with no real history,
        emit 3 plausible STUB runs spread across the last 14 days. Each
        stub run is flagged `"stub": true` so the dashboard can render a
        "preview data" badge. Stub runs are deterministic for a given
        slug + metric set so re-runs produce identical output (no drift).

    python scripts/build-eval-history.py --check
        Re-build in memory and diff against the on-disk JSON. Exit 1 on
        drift. The `computed_at` field is excluded from the diff so a
        timestamp refresh alone never triggers a false positive.

Mirrors the patterns in `scripts/compute-trust-score.py` and
`scripts/build-audit-log.py`: pure stdlib + pyyaml, deterministic JSON
output (sorted slugs, sorted metric keys), Apache 2.0 header, ecosystem
positioning in the module docstring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
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
_SUPER_AGENTS_ROOT = _REPO_ROOT / "templates" / "super-agents"
_OUTPUT = _REPO_ROOT / "docs" / "eval-history.json"
_NOW = datetime.now(timezone.utc)

# Stub-run timestamps anchor here, NOT to wall-clock UTC midnight. The
# previous behaviour (`anchor = _NOW.replace(...)`) re-stamped the seed
# runs on every UTC midnight, so the on-disk JSON drifted by one day per
# day and `--check` failed every PR opened on a different calendar day
# from the last regen — even when the PR didn't touch any eval data.
# Pin to a fixed date so the seed output is byte-identical across runs;
# bump only when the dashboard's preview window legitimately needs to
# move forward.
_SEED_ANCHOR = datetime(2026, 5, 10, tzinfo=timezone.utc)

_SCHEMA_VERSION = "0.1"
_TIMESTAMP_FIELD = "computed_at"

# Bridge directories under templates/super-agents/ are not standalone agents.
_NON_AGENT_DIRS: set[str] = {"_bridges"}


def _slug_for(manifest_path: Path) -> str:
    return manifest_path.parent.name


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _declared_metrics(manifest: dict[str, Any]) -> list[str]:
    """Pull `evaluation.deepeval.metrics` out of the manifest as a list of
    strings. Missing or malformed sections degrade to an empty list — the
    dashboard renders an "(no metrics declared)" placeholder in that case.
    """
    evaluation = manifest.get("evaluation") or {}
    if not isinstance(evaluation, dict):
        return []
    deepeval = evaluation.get("deepeval") or {}
    if not isinstance(deepeval, dict):
        return []
    metrics = deepeval.get("metrics") or []
    if not isinstance(metrics, list):
        return []
    return [str(m) for m in metrics if isinstance(m, (str, int, float))]


def _load_history_runs(manifest_path: Path) -> list[dict[str, Any]]:
    """Read every `eval/history/*.jsonl` adjacent to the manifest.

    One record per non-empty line. Bad JSON lines are skipped silently —
    the aggregator must never blow up on a malformed log; a quarantine
    line in one history file should not poison the dashboard.
    """
    history_dir = manifest_path.parent / "eval" / "history"
    if not history_dir.is_dir():
        return []
    runs: list[dict[str, Any]] = []
    for jsonl in sorted(history_dir.glob("*.jsonl")):
        try:
            text = jsonl.read_text(encoding="utf-8")
        except OSError:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            metrics_raw = rec.get("metrics") or {}
            if not isinstance(metrics_raw, dict):
                metrics_raw = {}
            metrics_clean: dict[str, float] = {}
            for k, v in metrics_raw.items():
                try:
                    metrics_clean[str(k)] = float(v)
                except (TypeError, ValueError):
                    continue
            run_id = rec.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                run_id = f"{jsonl.stem}-{idx:04d}"
            ts = rec.get("ts")
            ts_clean = str(ts) if isinstance(ts, str) else None
            runs.append({
                "run_id": run_id,
                "ts": ts_clean,
                "metrics": dict(sorted(metrics_clean.items())),
                "stub": False,
            })
    return runs


def _seed_runs(slug: str, metrics: list[str]) -> list[dict[str, Any]]:
    """Generate 3 deterministic STUB runs across the last 14 days.

    Determinism: the per-metric score is derived from a SHA-256 of
    `slug | metric | run_index`, mapped into the [0.55, 0.95] band so the
    preview data looks plausible. The same slug + metrics will always
    produce the same stub output, so `--seed` is safe under `--check`.

    Timestamp determinism: stub `ts` values anchor to a fixed
    `_SEED_ANCHOR` constant, NOT to wall-clock UTC midnight. Anchoring to
    `datetime.now()` re-stamped the seed runs on every UTC midnight, so
    the on-disk JSON drifted daily and `--check` failed every PR opened
    on a different calendar day from the last regen. With a fixed
    anchor, `--seed` produces byte-identical output across days.
    """
    if not metrics:
        return []
    anchor = _SEED_ANCHOR.replace(hour=0, minute=0, second=0, microsecond=0)
    runs: list[dict[str, Any]] = []
    # Three runs at days -14, -7, -0 from the UTC-midnight anchor.
    for run_index, days_ago in enumerate([14, 7, 0]):
        ts = (anchor - timedelta(days=days_ago)).isoformat()
        scores: dict[str, float] = {}
        for metric in metrics:
            seed = f"{slug}|{metric}|{run_index}".encode("utf-8")
            digest = hashlib.sha256(seed).digest()
            # 16-bit slice => 0..65535 => normalize into [0.55, 0.95].
            raw = int.from_bytes(digest[:2], "big") / 65535.0
            scores[metric] = round(0.55 + raw * 0.40, 4)
        runs.append({
            "run_id": f"stub-{slug}-{run_index:02d}",
            "ts": ts,
            "metrics": dict(sorted(scores.items())),
            "stub": True,
        })
    return runs


def _latest_metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    """Latest = run with the largest parseable `ts`. Runs without `ts`
    are ignored for "latest" selection but appear in the runs list.
    """
    dated = [r for r in runs if r.get("ts")]
    if not dated:
        return {}
    dated_sorted = sorted(dated, key=lambda r: str(r["ts"]))
    return dict(dated_sorted[-1].get("metrics") or {})


def _trend_7d(runs: list[dict[str, Any]]) -> dict[str, float]:
    """Per-metric delta vs the most recent run at least 7 days older than
    latest. If no such baseline exists, the metric is omitted from the
    trend dict (rather than reporting a misleading 0.0).
    """
    dated = [r for r in runs if r.get("ts")]
    if len(dated) < 2:
        return {}
    parsed: list[tuple[datetime, dict[str, float]]] = []
    for r in dated:
        try:
            dt = datetime.fromisoformat(str(r["ts"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        parsed.append((dt, dict(r.get("metrics") or {})))
    if len(parsed) < 2:
        return {}
    parsed.sort(key=lambda pair: pair[0])
    latest_dt, latest_metrics = parsed[-1]
    cutoff = latest_dt - timedelta(days=7)
    baseline = None
    for dt, metrics in reversed(parsed[:-1]):
        if dt <= cutoff:
            baseline = metrics
            break
    if baseline is None:
        # Fall back to the oldest sample so the dashboard still gets a
        # signed delta for short-history agents.
        baseline = parsed[0][1]
    trend: dict[str, float] = {}
    for metric, latest_val in latest_metrics.items():
        if metric in baseline:
            try:
                trend[metric] = round(float(latest_val) - float(baseline[metric]), 4)
            except (TypeError, ValueError):
                continue
    return dict(sorted(trend.items()))


def _discover_super_agent_manifests() -> list[Path]:
    if not _SUPER_AGENTS_ROOT.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(_SUPER_AGENTS_ROOT.iterdir()):
        if not child.is_dir() or child.name in _NON_AGENT_DIRS:
            continue
        manifest = child / "grok-agent.yaml"
        if manifest.is_file():
            out.append(manifest)
    return out


def build_payload(seed: bool) -> dict[str, Any]:
    manifests = _discover_super_agent_manifests()
    agents: dict[str, dict[str, Any]] = {}

    total_runs = 0
    agents_with_history = 0
    agents_no_history = 0
    metric_set: set[str] = set()

    for manifest_path in manifests:
        slug = _slug_for(manifest_path)
        manifest = _load_manifest(manifest_path)
        kind = str(manifest.get("kind", "unknown"))
        declared = _declared_metrics(manifest)

        runs = _load_history_runs(manifest_path)
        had_real_history = bool(runs)
        if not had_real_history and seed:
            runs = _seed_runs(slug, declared)

        if had_real_history:
            agents_with_history += 1
        else:
            agents_no_history += 1
        total_runs += len(runs)
        for r in runs:
            metric_set.update((r.get("metrics") or {}).keys())
        metric_set.update(declared)

        # Sort runs deterministically by (ts, run_id) so checked-in JSON
        # diffs stay minimal across runs.
        runs.sort(key=lambda r: (str(r.get("ts") or ""), str(r.get("run_id") or "")))

        agents[slug] = {
            "category": "super-agent",
            "kind": kind,
            "metrics_declared": sorted(declared),
            "runs": runs,
            "latest_metrics": dict(sorted(_latest_metrics(runs).items())),
            "trend_7d": _trend_7d(runs),
        }

    return {
        _TIMESTAMP_FIELD: _NOW.isoformat(),
        "schema_version": _SCHEMA_VERSION,
        "agent_count": len(agents),
        "metric_count": len(metric_set),
        "summary": {
            "total_runs": total_runs,
            "agents_with_history": agents_with_history,
            "agents_no_history": agents_no_history,
        },
        "agents": dict(sorted(agents.items())),
    }


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def _strip_timestamp(payload: dict[str, Any]) -> dict[str, Any]:
    clone = dict(payload)
    clone.pop(_TIMESTAMP_FIELD, None)
    return clone


def _check_drift(payload: dict[str, Any]) -> int:
    if not _OUTPUT.is_file():
        sys.stderr.write(
            f"X  {_OUTPUT.relative_to(_REPO_ROOT)} missing. "
            "Run `python scripts/build-eval-history.py`.\n"
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
            "X  Eval history drift detected. Re-run "
            "`python scripts/build-eval-history.py`.\n"
        )
        return 1
    sys.stdout.write("OK No drift\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Aggregate Super Agent eval history into "
            "docs/eval-history.json. Built for xAI, X, Grok and the "
            "ecosystem community."
        )
    )
    p.add_argument(
        "--check", action="store_true",
        help="Exit 1 if on-disk JSON differs from a fresh build.",
    )
    p.add_argument(
        "--seed", action="store_true",
        help="Emit 3 deterministic stub runs per agent that lacks real history.",
    )
    args = p.parse_args(argv)

    # `--check` must reflect what is actually persisted on disk. The
    # checked-in JSON was generated with `--seed`, so default-mode `--check`
    # would chase a phantom drift. Auto-enable seeding under `--check` so
    # CI stays honest without a second flag.
    seed = args.seed or args.check
    payload = build_payload(seed=seed)

    if args.check:
        return _check_drift(payload)

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(_serialize(payload), encoding="utf-8")
    sys.stdout.write(
        f"OK Wrote {_OUTPUT.relative_to(_REPO_ROOT)} "
        f"(agents={payload['agent_count']} "
        f"runs={payload['summary']['total_runs']} "
        f"with_history={payload['summary']['agents_with_history']} "
        f"no_history={payload['summary']['agents_no_history']})\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
