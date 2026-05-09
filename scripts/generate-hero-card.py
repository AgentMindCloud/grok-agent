# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Generate per-agent hero card SVGs for the Grok Agent OS marketplace.

Built for xAI, X, Grok and the ecosystem community. ❤️

Walks ``templates/<bucket>/<slug>/grok-agent.yaml`` for every shipped
agent, reads display name + tagline + kind, and writes a 1280x640 SVG
hero card to ``marketplace/public/hero-cards/<slug>.svg``.

The card is deliberately self-contained:

- pure SVG, no external image, font, or CSS reference
- system-font stack so the same card renders on Windows, GitHub, X,
  Vercel preview, and any Open Graph crawler
- Spectral v1 palette only:
    charcoal   #0A0A0A
    cinnabar   #FF1E70
    parchment  #F4ECDA
    teal       #00E0D5  (secondary accent on the kind label)
- diagonal charcoal-to-cinnabar gradient background
- corner ribbon shows the trust score letter tier (A / B / C / D)
  read from ``docs/agent-trust-scores.json``
- footer: "built on Grok Agent OS" in parchment
- 1280x640 == standard Open Graph / Twitter card aspect ratio (2:1)

Usage (from repo root, Windows 11 + PowerShell):

    python scripts/generate-hero-card.py
    python scripts/generate-hero-card.py --check   # exit 1 on any
                                                   # missing or stale card
    python scripts/generate-hero-card.py --slug x-money-companion-dashboard
"""
from __future__ import annotations

import argparse
import json
import sys
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
_TEMPLATES_ROOT = _REPO_ROOT / "templates"
_TRUST_SCORES = _REPO_ROOT / "docs" / "agent-trust-scores.json"
_OUTPUT_DIR = _REPO_ROOT / "marketplace" / "public" / "hero-cards"

# Spectral v1 palette — keep in sync with marketplace/app/globals.css and
# the README brand notes.
_CHARCOAL = "#0A0A0A"
_CINNABAR = "#FF1E70"
_PARCHMENT = "#F4ECDA"
_TEAL = "#00E0D5"

# Buckets we ship in the marketplace today. Folders outside this list
# (e.g. ``templates/general/`` skeletons) are intentionally skipped so
# the hero card directory mirrors the marketplace catalogue.
_INCLUDED_BUCKETS = {"super-agents", "finance", "creator"}

# Human-readable kind labels. The manifest's `kind:` field is a slug;
# the hero card prefers the friendlier label so the upper-right corner
# reads naturally on a social card preview.
_KIND_LABELS: dict[str, str] = {
    "finance-dashboard":   "X MONEY TOOL",
    "finance-tool":        "X MONEY TOOL",
    "x-money-tool":        "X MONEY TOOL",
    "super-agent":         "SUPER AGENT",
    "creator-template":    "CREATOR TEMPLATE",
    "creator-tool":        "CREATOR TEMPLATE",
    "agent":               "GROK AGENT",
}

# Width per character at the chosen display-name font size (60px). We
# avoid measuring real glyphs (no font available at build time) and
# use a conservative monospace approximation so long slugs still fit.
_TITLE_CHAR_PX = 31
_TAGLINE_CHAR_PX = 14
_TAGLINE_MAX_CHARS = 120

# Ribbon (trust tier) palette — matches the trust badge route.
_TIER_COLORS: dict[str, tuple[str, str]] = {
    # (background, text)
    "A": (_CINNABAR, _PARCHMENT),
    "B": (_CINNABAR, _PARCHMENT),
    "C": (_PARCHMENT, _CHARCOAL),
    "D": (_CHARCOAL, _PARCHMENT),
}


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _slug_to_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    # Cut on a word boundary if possible so the ellipsis lands cleanly.
    cut = text[: limit - 1]
    last_space = cut.rfind(" ")
    if last_space >= int(limit * 0.6):
        cut = cut[:last_space]
    return cut.rstrip(",;:.- ") + "…"


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap into lines no longer than ``max_chars``."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _wrap_title(text: str) -> list[str]:
    """Title wraps to at most two lines; longer titles get an ellipsis."""
    lines = _wrap(text, max_chars=22)
    if len(lines) <= 2:
        return lines
    return [lines[0], _truncate(" ".join(lines[1:]), 22)]


def _kind_label(raw_kind: str) -> str:
    return _KIND_LABELS.get(raw_kind, raw_kind.replace("-", " ").upper())


def _load_trust_tiers() -> dict[str, str]:
    """Map ``slug -> tier letter`` from the committed trust scores file.

    Falls back to an empty dict if the file is missing — the hero card
    then renders without a corner ribbon. We never block generation on
    a missing trust score because trust scores are recomputed by a
    separate workflow.
    """
    if not _TRUST_SCORES.is_file():
        return {}
    try:
        data = json.loads(_TRUST_SCORES.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    for slug, entry in (data.get("agents") or {}).items():
        tier = entry.get("tier")
        if isinstance(tier, str) and tier in _TIER_COLORS:
            out[slug] = tier
    return out


def _ribbon_svg(tier: str) -> str:
    bg, fg = _TIER_COLORS[tier]
    # Diagonal corner ribbon at the top-right. Built from a polygon so
    # it stays crisp at any scale and keeps the SVG self-contained.
    return f"""
  <g transform="translate(1280 0)">
    <polygon points="-180,0 0,0 0,180" fill="{bg}"/>
    <text x="-50" y="56" text-anchor="middle"
          font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif"
          font-size="22" font-weight="700" fill="{fg}"
          transform="rotate(45 -50 56)">TRUST {tier}</text>
  </g>"""


def build_card_svg(
    *,
    slug: str,
    display_name: str,
    tagline: str,
    raw_kind: str,
    tier: str | None,
) -> str:
    """Return the SVG markup for one agent's hero card."""
    safe_name_lines = [_escape_xml(line) for line in _wrap_title(display_name)]
    safe_tagline = _escape_xml(_truncate(tagline, _TAGLINE_MAX_CHARS))
    safe_kind = _escape_xml(_kind_label(raw_kind))
    safe_slug = _escape_xml(slug)

    # Wrap the tagline at ~70 chars per line (3-line maximum) so it
    # never collides with the footer at y=580.
    tagline_lines = _wrap(safe_tagline, max_chars=70)[:3]

    title_y_start = 240 - max(0, (len(safe_name_lines) - 1) * 36)
    title_lines_svg = "\n".join(
        f'    <text x="80" y="{title_y_start + i * 76}" '
        f'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="68" font-weight="800" fill="{_PARCHMENT}">{line}</text>'
        for i, line in enumerate(safe_name_lines)
    )

    tagline_y_start = title_y_start + len(safe_name_lines) * 76 + 30
    tagline_lines_svg = "\n".join(
        f'    <text x="80" y="{tagline_y_start + i * 36}" '
        f'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="28" font-weight="400" fill="{_PARCHMENT}" opacity="0.92">{line}</text>'
        for i, line in enumerate(tagline_lines)
    )

    ribbon = _ribbon_svg(tier) if tier else ""

    # Background: charcoal-to-cinnabar diagonal gradient. The stop at
    # 65% keeps the title legible (still on the dark side).
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640"
     viewBox="0 0 1280 640" role="img"
     aria-label="Grok Agent OS hero card — {_escape_xml(display_name)}">
  <title>Grok Agent OS — {_escape_xml(display_name)}</title>
  <desc>{_escape_xml(display_name)}: {safe_tagline}. Built on Grok Agent OS.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{_CHARCOAL}"/>
      <stop offset="65%" stop-color="{_CHARCOAL}"/>
      <stop offset="100%" stop-color="{_CINNABAR}"/>
    </linearGradient>
    <linearGradient id="kindBar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{_TEAL}"/>
      <stop offset="100%" stop-color="{_CINNABAR}"/>
    </linearGradient>
  </defs>

  <!-- background -->
  <rect width="1280" height="640" fill="url(#bg)"/>

  <!-- subtle scanline overlay (Spectral v1 retro CRT cue) -->
  <g opacity="0.06" fill="{_PARCHMENT}">
    <rect x="0" y="40"  width="1280" height="1"/>
    <rect x="0" y="120" width="1280" height="1"/>
    <rect x="0" y="200" width="1280" height="1"/>
    <rect x="0" y="280" width="1280" height="1"/>
    <rect x="0" y="360" width="1280" height="1"/>
    <rect x="0" y="440" width="1280" height="1"/>
    <rect x="0" y="520" width="1280" height="1"/>
  </g>

  <!-- accent bar above the kind label -->
  <rect x="80" y="80" width="120" height="6" fill="url(#kindBar)" rx="3"/>

  <!-- kind label (top-left) -->
  <text x="80" y="130"
        font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif"
        font-size="22" font-weight="700"
        fill="{_TEAL}" letter-spacing="2">{safe_kind}</text>

  <!-- display name (large) -->
{title_lines_svg}

  <!-- tagline -->
{tagline_lines_svg}

  <!-- footer separator -->
  <rect x="80" y="552" width="1120" height="1" fill="{_PARCHMENT}" opacity="0.25"/>

  <!-- footer left: built on Grok Agent OS -->
  <text x="80" y="600"
        font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif"
        font-size="22" font-weight="600" fill="{_PARCHMENT}">
    built on <tspan fill="{_CINNABAR}">Grok Agent OS</tspan>
  </text>

  <!-- footer right: slug pill -->
  <g>
    <rect x="900" y="572" width="300" height="40" rx="20" fill="{_CHARCOAL}"
          stroke="{_PARCHMENT}" stroke-opacity="0.35" stroke-width="1"/>
    <text x="1050" y="599" text-anchor="middle"
          font-family="JetBrains Mono, Consolas, Menlo, monospace"
          font-size="18" fill="{_PARCHMENT}">{safe_slug}</text>
  </g>
{ribbon}
</svg>
"""


def _iter_manifests() -> list[Path]:
    if not _TEMPLATES_ROOT.is_dir():
        sys.stderr.write(f"ERROR: templates/ not found under {_REPO_ROOT}\n")
        sys.exit(66)
    out: list[Path] = []
    for manifest in sorted(_TEMPLATES_ROOT.rglob("grok-agent.yaml")):
        rel_parts = manifest.relative_to(_TEMPLATES_ROOT).parts
        if not rel_parts:
            continue
        bucket = rel_parts[0]
        if bucket not in _INCLUDED_BUCKETS:
            continue
        out.append(manifest)
    return out


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def render_one(manifest_path: Path, tiers: dict[str, str]) -> tuple[str, str] | None:
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return None
    slug = manifest_path.parent.name
    metadata = manifest.get("metadata") or {}
    display_name = (
        metadata.get("display_name")
        or manifest.get("name")
        or _slug_to_title(slug)
    )
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = _slug_to_title(slug)
    tagline = (
        metadata.get("tagline")
        or manifest.get("description")
        or ""
    )
    if not isinstance(tagline, str):
        tagline = ""
    raw_kind = manifest.get("kind") or "agent"
    if not isinstance(raw_kind, str):
        raw_kind = "agent"
    tier = tiers.get(slug)

    svg = build_card_svg(
        slug=slug,
        display_name=display_name.strip(),
        tagline=tagline.strip(),
        raw_kind=raw_kind,
        tier=tier,
    )
    return slug, svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate 1280x640 hero card SVGs for every Grok Agent OS "
            "agent. Output: marketplace/public/hero-cards/<slug>.svg. "
            "Built for xAI, X, Grok and the ecosystem community."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any card is missing or differs from the freshly rendered SVG.",
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Render a single agent by slug (still writes to marketplace/public/hero-cards/).",
    )
    args = parser.parse_args(argv)

    tiers = _load_trust_tiers()
    manifests = _iter_manifests()
    if args.slug:
        manifests = [m for m in manifests if m.parent.name == args.slug]
        if not manifests:
            sys.stderr.write(f"X  Unknown slug: {args.slug}\n")
            return 66

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rendered: list[tuple[str, str]] = []
    for manifest in manifests:
        result = render_one(manifest, tiers)
        if result is not None:
            rendered.append(result)

    if args.check:
        drift = 0
        for slug, svg in rendered:
            target = _OUTPUT_DIR / f"{slug}.svg"
            if not target.is_file():
                sys.stderr.write(f"X  Missing hero card: {target.relative_to(_REPO_ROOT)}\n")
                drift += 1
                continue
            on_disk = target.read_text(encoding="utf-8")
            if on_disk != svg:
                sys.stderr.write(
                    f"X  Hero card drift: {target.relative_to(_REPO_ROOT)} "
                    "(re-run scripts/generate-hero-card.py)\n"
                )
                drift += 1
        if drift:
            return 1
        sys.stdout.write(
            f"OK No hero card drift ({len(rendered)} cards verified).\n"
        )
        return 0

    written = 0
    for slug, svg in rendered:
        target = _OUTPUT_DIR / f"{slug}.svg"
        target.write_text(svg, encoding="utf-8")
        written += 1

    with_ribbon = sum(1 for slug, _svg in rendered if slug in tiers)
    sys.stdout.write(
        f"OK Wrote {written} hero card(s) to "
        f"{_OUTPUT_DIR.relative_to(_REPO_ROOT)} "
        f"(ribbon shown for {with_ribbon} of {written}).\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
