// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Built for xAI, X, Grok and the ecosystem community.
//
// Minimal extension entry point. Schema validation is delegated entirely
// to the Red Hat YAML extension (declared as an extensionDependency in
// package.json) via the contributes.yamlValidation block — that's the
// canonical, zero-JS pattern for shipping a YAML schema as a VS Code
// extension. No activation logic is required.
//
// This file exists so VS Code's `--selfcheck` smoke pass during
// `vsce package` finds an entry, and so future versions can hook in
// CodeLens for "grok install this" actions or a Constitution-lint
// status item without changing the manifest shape.

'use strict';

function activate(_context) {
  // Intentionally empty — yamlValidation contribution does all the work.
}

function deactivate() {}

module.exports = { activate, deactivate };

// `node ./extension.js --selfcheck` is invoked by `vsce` during
// `vscode:prepublish`. Exit cleanly when called that way.
if (require.main === module && process.argv.includes('--selfcheck')) {
  // eslint-disable-next-line no-console
  console.log('vscode-grok-agent extension entry point: OK');
  process.exit(0);
}
