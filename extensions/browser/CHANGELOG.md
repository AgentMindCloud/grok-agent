<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Changelog — Grok Agent OS browser extension

> Built for xAI, X, Grok and the ecosystem community. ❤️

All notable changes to this extension are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-05-09

### Added

- Initial release. MV3 extension scanning x.com / twitter.com for v2.15 manifests; right-click context menu; install overlay with 3 paths; popup with recent-installs history.
- `manifest.json` (Manifest V3) declaring host permissions for `https://x.com/*` and `https://twitter.com/*`, plus `storage`, `contextMenus`, `notifications`, and `clipboardWrite` permissions.
- `background.js` service worker brokering `GET_HISTORY` and `INSTALL_REQUEST` messages between the popup, options page, and content scripts, and persisting the rolling history in `chrome.storage.local`.
- `content/detect-yaml.js` content script that scans the live X / Twitter DOM for the v2.15 manifest header and surfaces a floating install button on each match.
- `content/install-flow.js` plus `content/install-flow.css` overlay presenting the three install paths: PowerShell stdin pipe, one-liner clipboard copy, and `grok-agent install <url>` redirect.
- `popup/popup.html`, `popup/popup.js`, `popup/popup.css` toolbar popup showing the last 10 install requests with a per-item "Re-open install flow" button, plus marketplace and settings shortcuts.
- `options/options.html` and `options/options.js` preferences page persisting `install_path` (default `$env:LOCALAPPDATA\grok-agent\agents`), `notifications` toggle, and preferred install method (PowerShell stdin / one-liner / manifest URL) in `chrome.storage.sync`.
- `icons/` SVG sources at 16, 32, 48, and 128 pixels with the Spectral v1 cinnabar-on-charcoal brand and a PowerShell ImageMagick procedure for generating the four PNG sizes Chrome MV3 requires.
- Apache-2.0 license headers on every file. Repository pointer to [`AgentMindCloud/grok-agent/extensions/browser`](https://github.com/AgentMindCloud/grok-agent/tree/main/extensions/browser).
