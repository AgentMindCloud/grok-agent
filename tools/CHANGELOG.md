# Changelog

All notable changes to `x-platform-toolkit` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-04-21

### Added

- Initial repo scaffold with brand identity (grok-install family)
- 6 LIVE tools shipped (vanilla JS, single-file):
  - 04 Pre-Post Virality Scorer
  - 05 Pinned Post A/B Rotator
  - 07 Content Compound Calculator
  - 09 Engagement Quality Score
  - 12 Controversy Detector
  - 18 Emotional Tone Trend Tracker
- 14 SPEC'D tools with detailed implementation plans
- Shared UI kit (tokens, components, shell template)
- Shared X API v2 wrapper (`@x-platform-toolkit/x-api-client`)
- Shared xAI Grok API wrapper (`@x-platform-toolkit/grok-client`)
- Documentation: PHILOSOPHY, ARCHITECTURE, BRAND, ROADMAP
- Contributing guide, Code of Conduct, issue templates

### Notes

- Tool 12 (Controversy Detector) ships with empty default keyword lists. Users add their own niche-specific risk vocabulary via the in-UI "Edit keywords" control, which persists locally. The tool's value is the scoring framework and highlight UI, not a baked-in glossary — every niche has different risk vocabulary.

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
