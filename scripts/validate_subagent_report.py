# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sub-agent self-report integrity validator (P169 Fix 5).

Compares a sub-agent's claimed file list against the actual `git diff` output
of the working tree (or any explicit git range) and reports discrepancies.

Why: when the main agent spawns sub-agents in parallel, the only honest
record of what each sub-agent changed is the git working tree itself. A
sub-agent that reports "no edits" while `git diff --stat` shows +174 lines
is hiding a problem. This validator makes that drift impossible to ignore.

Exit codes:
    0  - all-claimed-changed (and, in non-strict mode, possibly extras)
    1  - one or more claimed files were NOT actually changed
        (also: in --strict mode, any changed-but-not-claimed file)
    2  - environment error (not in a git repo, missing git)

PowerShell usage examples:

    python scripts/validate_subagent_report.py --claimed CLAUDE.md scripts/foo.py
    python scripts/validate_subagent_report.py --claimed CLAUDE.md --strict --json
    python scripts/validate_subagent_report.py --claimed CLAUDE.md --git-range HEAD~1..HEAD

This script is idempotent and read-only — it never edits files or git state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set


def get_actual_changed_files(repo_root: Path, git_range: str) -> Set[str]:
    """Return the set of repo-relative POSIX paths changed in `git_range`.

    When `git_range == "HEAD"` the working tree is queried (unstaged + staged
    changes against HEAD). For any other value (e.g. `HEAD~1..HEAD` or a
    branch range) it is passed through to `git diff --name-only` verbatim.

    Raises subprocess.CalledProcessError when git itself fails (e.g. the
    directory is not a git repo). The caller is expected to handle that.
    """
    if git_range == "HEAD":
        # Working tree: unstaged changes vs HEAD.
        unstaged = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout
        # Staged changes are already in `diff HEAD`, but untracked files
        # are not. Grab them separately so a sub-agent that creates a brand
        # new file is correctly counted as having changed it.
        untracked = subprocess.run(
            [
                "git", "-C", str(repo_root),
                "ls-files", "--others", "--exclude-standard",
            ],
            check=True, capture_output=True, text=True,
        ).stdout
        raw = unstaged + untracked
    else:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", git_range],
            check=True, capture_output=True, text=True,
        )
        raw = result.stdout
    return {line.strip() for line in raw.splitlines() if line.strip()}


def compare(claimed: Set[str], actual: Set[str]) -> Dict[str, List[str]]:
    """Diff the two sets and return the partition.

    Keys:
      matches              - claimed files that were actually changed
      claimed_not_changed  - claimed files that show no diff (BAD)
      changed_not_claimed  - real changes the sub-agent did not mention
    """
    return {
        "matches": sorted(claimed & actual),
        "claimed_not_changed": sorted(claimed - actual),
        "changed_not_claimed": sorted(actual - claimed),
    }


def format_human(report: Dict[str, List[str]], strict: bool) -> str:
    """Render the comparison as a human-readable block."""
    lines: List[str] = []
    lines.append("-> Sub-agent self-report integrity check")
    lines.append(f"   strict mode: {'ON' if strict else 'off'}")
    lines.append("")

    matches = report["matches"]
    lines.append(f"OK matches ({len(matches)}):")
    if matches:
        for p in matches:
            lines.append(f"     + {p}")
    else:
        lines.append("     (none)")
    lines.append("")

    cnc = report["claimed_not_changed"]
    if cnc:
        lines.append(f"ERROR claimed-but-not-changed ({len(cnc)}):")
        for p in cnc:
            lines.append(f"     ! {p}")
        lines.append("     -> sub-agent claimed these files but git shows no diff")
        lines.append("")
    else:
        lines.append("OK claimed-but-not-changed: 0")
        lines.append("")

    cnotc = report["changed_not_claimed"]
    if cnotc:
        label = "ERROR" if strict else "WARN"
        lines.append(f"{label} changed-but-not-claimed ({len(cnotc)}):")
        for p in cnotc:
            lines.append(f"     ? {p}")
        if strict:
            lines.append("     -> strict mode: these unannounced edits fail the check")
        else:
            lines.append("     -> non-strict: warnings only, exit code unaffected")
        lines.append("")
    else:
        lines.append("OK changed-but-not-claimed: 0")
        lines.append("")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_subagent_report",
        description=(
            "Compare a sub-agent's claimed modified-files list against the "
            "actual git diff. See CLAUDE.md §16 for the integrity rule."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "PowerShell examples:\n"
            "  python scripts/validate_subagent_report.py --claimed CLAUDE.md\n"
            "  python scripts/validate_subagent_report.py --claimed a.py b.py --strict\n"
            "  python scripts/validate_subagent_report.py --claimed a.py --git-range HEAD~1..HEAD\n"
        ),
    )
    parser.add_argument(
        "--claimed",
        nargs="+",
        required=True,
        metavar="PATH",
        help="Repo-relative paths the sub-agent claims to have modified.",
    )
    parser.add_argument(
        "--git-range",
        default="HEAD",
        help=(
            "Git range to compare against. Default 'HEAD' inspects the "
            "working tree (unstaged + staged + untracked). Accepts any "
            "valid 'git diff' range, e.g. 'HEAD~1..HEAD'."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail when the claimed and actual sets are not exactly equal. "
            "Without this flag, only claimed-not-changed triggers exit 1; "
            "changed-but-not-claimed prints a warning."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON summary in addition to human-readable text.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        metavar="PATH",
        help="Repo root (defaults to the current working directory).",
    )
    return parser


def _normalize(paths: List[str]) -> Set[str]:
    """Strip whitespace and convert any backslashes to forward slashes."""
    out: Set[str] = set()
    for p in paths:
        s = p.strip().replace("\\", "/")
        if s:
            out.add(s)
    return out


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root or Path.cwd()).expanduser().resolve()

    if not repo_root.is_dir():
        sys.stderr.write(f"X  Repo root not found: {repo_root}\n")
        return 2
    if not (repo_root / ".git").exists():
        sys.stderr.write(
            f"X  Not a git repository: {repo_root}\n"
            "   Run this script from inside the grok-agent checkout, or pass "
            "--repo-root explicitly.\n"
        )
        return 2

    try:
        actual = get_actual_changed_files(repo_root, args.git_range)
    except FileNotFoundError:
        sys.stderr.write(
            "X  'git' executable not found on PATH. Install Git for Windows "
            "and retry from PowerShell.\n"
        )
        return 2
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(
            f"X  git diff failed (exit {exc.returncode}) for range "
            f"'{args.git_range}'.\n"
        )
        if exc.stderr:
            sys.stderr.write(exc.stderr)
        return 2

    claimed = _normalize(list(args.claimed))
    report = compare(claimed, actual)

    sys.stdout.write(format_human(report, strict=args.strict))

    has_claimed_not_changed = bool(report["claimed_not_changed"])
    has_changed_not_claimed = bool(report["changed_not_claimed"])
    if has_claimed_not_changed:
        exit_code = 1
    elif args.strict and has_changed_not_claimed:
        exit_code = 1
    else:
        exit_code = 0

    if args.emit_json:
        payload = {
            "repo_root": str(repo_root),
            "git_range": args.git_range,
            "strict": args.strict,
            "claimed": sorted(claimed),
            "actual": sorted(actual),
            "matches": report["matches"],
            "claimed_not_changed": report["claimed_not_changed"],
            "changed_not_claimed": report["changed_not_claimed"],
            "exit_code": exit_code,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")

    if exit_code == 0:
        sys.stdout.write("OK sub-agent report verified.\n")
    else:
        sys.stdout.write("FAIL sub-agent report has discrepancies.\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
