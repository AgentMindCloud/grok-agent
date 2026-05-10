# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Compute per-PR Super Agent eval delta and post it as a sticky PR comment.

Built for xAI, X, Grok and the ecosystem community. ❤️

Triggered by ``.github/workflows/eval-delta.yml`` on any pull request that
touches ``templates/super-agents/*/eval/**`` or
``templates/super-agents/*/prompts/**``. The job calls this script after
checking the PR out with ``fetch-depth: 0``.

Algorithm:

1. Resolve ``BASE_SHA`` and ``HEAD_SHA`` from the environment (the
   workflow injects them from ``github.event.pull_request.base.sha`` and
   ``github.sha``).
2. Run ``git diff --name-only BASE_SHA..HEAD_SHA`` to find every
   super-agent whose eval suite or prompt set changed.
3. For each affected super-agent, run its eval suite **on the head**
   (already checked out), record per-metric scores, then ``git stash``
   any uncommitted state, ``git checkout BASE_SHA`` for the same agent's
   eval folder only, run the suite again, record per-metric scores, then
   restore the head with ``git checkout HEAD_SHA`` and ``git stash pop``.
4. Compute deltas (head minus base) per metric.
5. Format a markdown table:

       | Agent | Metric | Base | Head | Δ |

6. Write the table to ``$GITHUB_STEP_SUMMARY`` if available.
7. POST the table as a sticky PR comment via the GitHub REST API if
   ``GITHUB_TOKEN`` and ``GITHUB_REPOSITORY`` and ``PR_NUMBER`` are
   resolvable. Otherwise print to stdout.

Graceful-degradation contract (see CLAUDE.md §17):

- If ``promptfoo`` is not on ``PATH``, the table emits
  ``(skipped — missing dep: promptfoo)`` for that row and continues.
- If ``import deepeval`` raises ``ImportError``, the table emits
  ``(skipped — missing dep: deepeval)`` for that row and continues.
- Any single-agent failure is logged to stderr and skipped; the script
  never crashes the workflow.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUPER_AGENTS_ROOT = _REPO_ROOT / "templates" / "super-agents"
_STICKY_MARKER = "<!-- grok-agent-os:eval-delta -->"


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and return the CompletedProcess; never raise on check=False."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def _git(*args: str, check: bool = True) -> str:
    result = _run(["git", *args], cwd=_REPO_ROOT, check=check)
    return result.stdout.strip()


def _affected_super_agents(base_sha: str, head_sha: str) -> list[str]:
    """Return the slug list of super-agents whose eval/ or prompts/ changed."""
    try:
        diff = _git("diff", "--name-only", f"{base_sha}..{head_sha}", check=False)
    except FileNotFoundError:
        sys.stderr.write("WARN: git not available; cannot compute affected agents.\n")
        return []
    slugs: set[str] = set()
    for line in diff.splitlines():
        parts = line.strip().split("/")
        if (
            len(parts) >= 4
            and parts[0] == "templates"
            and parts[1] == "super-agents"
            and parts[3] in ("eval", "prompts")
        ):
            slugs.add(parts[2])
    return sorted(slugs)


def _has_promptfoo() -> bool:
    return shutil.which("promptfoo") is not None


def _has_deepeval() -> bool:
    try:
        __import__("deepeval")
        return True
    except ImportError:
        return False


def _run_promptfoo(agent_dir: Path) -> dict[str, float] | str:
    """Run promptfoo eval for the agent. Return per-metric dict OR an error string."""
    cfg = agent_dir / "eval" / "promptfoo.yaml"
    if not cfg.exists():
        return "no promptfoo.yaml present"
    if not _has_promptfoo():
        return "skipped — missing dep: promptfoo"
    try:
        result = _run(
            ["promptfoo", "eval", "-c", str(cfg), "--output", "json"],
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return f"promptfoo run failed: {exc}"
    if result.returncode != 0:
        return f"promptfoo exited {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "promptfoo output not valid JSON"
    # Promptfoo result schema: {"results": {"stats": {"passes": N, "failures": N, ...}}}
    stats = ((payload.get("results") or {}).get("stats")) or {}
    passes = int(stats.get("passes", 0))
    failures = int(stats.get("failures", 0))
    total = passes + failures
    return {
        "promptfoo_pass_rate": (passes / total) if total else 0.0,
        "promptfoo_total_cases": float(total),
    }


def _run_deepeval(agent_dir: Path) -> dict[str, float] | str:
    """Run the deepeval suite stub for the agent. Return per-metric dict OR error."""
    suite = agent_dir / "eval" / "deepeval_suite.py"
    if not suite.exists():
        return "no deepeval_suite.py present"
    if not _has_deepeval():
        return "skipped — missing dep: deepeval"
    try:
        result = _run(
            [sys.executable, str(suite), "--summary-json"],
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return f"deepeval run failed: {exc}"
    if result.returncode != 0:
        return f"deepeval exited {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "deepeval output not valid JSON"
    metrics: dict[str, float] = {}
    for key, value in (payload.get("metrics") or {}).items():
        try:
            metrics[f"deepeval_{key}"] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics or "deepeval emitted no metrics"


def _measure_agent(slug: str) -> dict[str, Any]:
    """Run promptfoo + deepeval for a single agent at the current checkout."""
    agent_dir = _SUPER_AGENTS_ROOT / slug
    return {
        "promptfoo": _run_promptfoo(agent_dir),
        "deepeval": _run_deepeval(agent_dir),
    }


def _at_revision(sha: str, slugs: list[str]) -> dict[str, dict[str, Any]]:
    """Check out the eval+prompts folders at `sha`, run measurements, restore head."""
    if not sha:
        return {}
    paths: list[str] = []
    for slug in slugs:
        paths.append(f"templates/super-agents/{slug}/eval")
        paths.append(f"templates/super-agents/{slug}/prompts")
    head_before = _git("rev-parse", "HEAD", check=False) or "HEAD"
    # Stash any local changes so the per-path checkout is safe.
    _git("stash", "push", "-u", "-m", "eval-delta-tmp", check=False)
    try:
        # Per-path checkout — safer than full `git checkout SHA`.
        _git("checkout", sha, "--", *paths, check=False)
        measured: dict[str, dict[str, Any]] = {slug: _measure_agent(slug) for slug in slugs}
    finally:
        # Restore head paths.
        _git("checkout", head_before, "--", *paths, check=False)
        # Pop the stash if we pushed one (stash pop is a no-op if empty).
        _git("stash", "pop", check=False)
    return measured


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return "ok"
    if isinstance(value, str):
        return value
    return str(value)


def _format_delta(base: Any, head: Any, metric: str) -> tuple[str, str, str]:
    """Return (base_str, head_str, delta_str) for one metric row."""
    if isinstance(base, str) or isinstance(head, str):
        # At least one side is an error / skip message.
        msg = base if isinstance(base, str) else head
        return ("n/a", "n/a", msg)
    base_v = float(base.get(metric, 0.0))
    head_v = float(head.get(metric, 0.0))
    delta = head_v - base_v
    sign = "+" if delta > 0 else ""
    return (f"{base_v:.3f}", f"{head_v:.3f}", f"{sign}{delta:.3f}")


def _build_table(
    base_results: dict[str, dict[str, Any]],
    head_results: dict[str, dict[str, Any]],
) -> str:
    rows: list[str] = []
    rows.append("| Agent | Metric | Base | Head | Δ |")
    rows.append("|---|---|---|---|---|")
    for slug in sorted(set(base_results) | set(head_results)):
        base_a = base_results.get(slug, {"promptfoo": "no base data", "deepeval": "no base data"})
        head_a = head_results.get(slug, {"promptfoo": "no head data", "deepeval": "no head data"})
        for tool in ("promptfoo", "deepeval"):
            base_payload = base_a.get(tool, "missing")
            head_payload = head_a.get(tool, "missing")
            if isinstance(base_payload, str) or isinstance(head_payload, str):
                msg = base_payload if isinstance(base_payload, str) else head_payload
                rows.append(f"| `{slug}` | `{tool}` | n/a | n/a | {msg} |")
                continue
            metrics = sorted(set(base_payload) | set(head_payload))
            for metric in metrics:
                base_s, head_s, delta_s = _format_delta(base_payload, head_payload, metric)
                rows.append(f"| `{slug}` | `{metric}` | {base_s} | {head_s} | {delta_s} |")
    return "\n".join(rows)


def _post_sticky_comment(body: str) -> bool:
    """POST a sticky comment to the PR via REST API. Return True on success."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    if not (token and repo and pr_number and pr_number.isdigit()):
        return False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "grok-agent-os-eval-delta",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    list_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    existing_id: int | None = None
    try:
        req = urllib.request.Request(list_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            comments = json.loads(resp.read().decode("utf-8"))
        for comment in comments:
            if _STICKY_MARKER in (comment.get("body") or ""):
                existing_id = int(comment["id"])
                break
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        sys.stderr.write(f"WARN: could not list PR comments: {exc}\n")
    payload = json.dumps({"body": body}).encode("utf-8")
    try:
        if existing_id is not None:
            patch_url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}"
            req = urllib.request.Request(patch_url, data=payload, headers=headers, method="PATCH")
        else:
            post_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            req = urllib.request.Request(post_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return True
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        sys.stderr.write(f"WARN: could not write PR comment: {exc}\n")
    return False


def main() -> int:
    base_sha = os.environ.get("BASE_SHA", "").strip()
    head_sha = os.environ.get("HEAD_SHA", "").strip() or _git("rev-parse", "HEAD", check=False)
    if not base_sha:
        print("INFO: BASE_SHA not set; nothing to compare. Exiting 0.")
        return 0

    slugs = _affected_super_agents(base_sha, head_sha)
    if not slugs:
        print("INFO: No super-agent eval/ or prompts/ changes detected.")
        return 0

    print(f"INFO: Affected super-agents: {', '.join(slugs)}")

    head_results = {slug: _measure_agent(slug) for slug in slugs}
    base_results = _at_revision(base_sha, slugs)

    table = _build_table(base_results, head_results)
    body = (
        f"{_STICKY_MARKER}\n"
        "## Super Agent Eval Delta\n\n"
        f"Base: `{base_sha[:7]}` → Head: `{head_sha[:7]}`\n\n"
        f"{table}\n\n"
        "_Built for xAI, X, Grok and the ecosystem community. ❤️_"
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        try:
            Path(summary_path).write_text(body, encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"WARN: could not write GITHUB_STEP_SUMMARY: {exc}\n")

    posted = _post_sticky_comment(body)
    if not posted:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
