<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — Browser extension

> Built for xAI, X, Grok and the ecosystem community. ❤️

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/AgentMindCloud/grok-agent/blob/main/LICENSE)
[![Manifest](https://img.shields.io/badge/Chrome-MV3-orange.svg)](manifest.json)
[![Spec](https://img.shields.io/badge/grok--agent.yaml-v2.15-purple.svg)](https://github.com/AgentMindCloud/grok-agent/tree/main/spec/v2.15)

A Chrome MV3 extension that turns any `grok-agent.yaml` v2.15 manifest discovered on **x.com** or **twitter.com** into a one-click install on the user's Windows machine. The extension is the missing browser surface for the Grok Agent OS distribution layer — it converts a tweet, gist, or pinned reply containing a manifest into a guided three-path installer overlay, with zero round-trips to a server we control.

## Installation (developer mode)

The extension is not yet published to the Chrome Web Store. To load it from source today:

1. Clone the repo: `git clone https://github.com/AgentMindCloud/grok-agent.git`
2. `cd grok-agent\extensions\browser`
3. Generate the four PNG icon sizes from the SVG sources (Chrome MV3 rejects SVG icons). From PowerShell, with [ImageMagick](https://imagemagick.org/) installed:

   ```powershell
   cd icons
   magick icon-16.svg  -background none -resize 16x16   icon-16.png
   magick icon-32.svg  -background none -resize 32x32   icon-32.png
   magick icon-48.svg  -background none -resize 48x48   icon-48.png
   magick icon-128.svg -background none -resize 128x128 icon-128.png
   ```

   See [`icons/README.md`](icons/README.md) for the full procedure.

4. Open `chrome://extensions` in Google Chrome.
5. Toggle **Developer mode** on (top right).
6. Click **Load unpacked** and select the `extensions/browser` folder.
7. Pin the extension to the toolbar so the popup is one click away.

## How it works

Three cooperating pieces, all local to the browser:

1. **`content/detect-yaml.js`** — content script injected into `x.com` and `twitter.com`. It scans the live DOM for code blocks, `<pre>` tags, and pasted text containing the v2.15 manifest header (`version: 2.15` plus a `kind:` line from the canonical enum). On a match, it surfaces a small floating button anchored to the matched block.
2. **`content/install-flow.js` / `install-flow.css`** — the overlay that opens when the floating button is clicked. The overlay presents three install paths chosen by the user in the options page:
   - **PowerShell stdin pipe** — paste the manifest into a running `grok-agent install -` shell.
   - **One-liner clipboard** — copies a single PowerShell command that pipes the manifest through `grok-agent install`.
   - **Manifest URL** — opens `grok-agent install <url>` against the source URL when the manifest came from a hosted file.
3. **`popup/`** and **`options/`** — the toolbar popup shows the rolling history of the last 10 install requests (timestamp + a 60-character snippet of the manifest + a "Re-open install flow" button), and the options page persists the user's preferred install method and default install path (`$env:LOCALAPPDATA\grok-agent\agents` by default) in `chrome.storage.sync`.

The `background.js` service worker brokers all messages between the popup, the options page, and the content scripts, and persists the install-request history in `chrome.storage.local`.

## Roadmap

- **v0.2** — signed install protocol: every manifest carries a detached Ed25519 signature that the extension verifies against the publisher's public key before the overlay opens.
- **v0.3** — Firefox port (Manifest V3) and Microsoft Edge package, both built from the same source tree.
- **v0.4** — in-overlay manifest validation: run the canonical Pydantic v2.15 schema (compiled to a tiny WASM bundle) before the install overlay opens.
- **v0.5** — multi-language UI: English, Vietnamese, Spanish, Mandarin Simplified strings driven by `chrome.i18n`.

## Privacy

The extension does **not** send any data to a server we control. The only outbound network requests are the user explicitly clicking through to GitHub from the popup footer or to the marketplace from the popup primary button. Install-request history lives only on the user's machine in `chrome.storage.local`. Preferences live only on the user's signed-in Chrome profile in `chrome.storage.sync` (Google's roaming layer — opt out by signing out of Chrome sync).

## License

Apache-2.0. See [LICENSE](https://github.com/AgentMindCloud/grok-agent/blob/main/LICENSE).

## Contributing

This extension lives inside the main `AgentMindCloud/grok-agent` repo at [`extensions/browser/`](https://github.com/AgentMindCloud/grok-agent/tree/main/extensions/browser). Open issues and PRs against the main repo. See the root [`CONTRIBUTING.md`](https://github.com/AgentMindCloud/grok-agent/blob/main/CONTRIBUTING.md) for the full contribution guide.

Built for xAI, X, Grok and the ecosystem community. ❤️
