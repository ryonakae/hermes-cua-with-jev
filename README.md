# Hermes CUA with Jev

Delegate bounded browser and native-app action selection to Jev while reusing Cua Driver.

Hermes supplies the goal, allowed controls, input values, and completion conditions. The plugin builds candidates from UI observations, asks Jev to choose a candidate, and executes it through the public Cua Driver MCP interface.

> [!WARNING]
> Work-in-progress checkpoint, not a release. Safety review has not passed. Do not enable this plugin for normal use or use it with credentials, payment data, verification codes, or sensitive applications.

## Current scope

- A single `cua_jev` tool exposes discovery, inspection, bounded runs, and single-step operation.
- Browser semantic controls and native accessibility controls support click and text input.
- TypeSafe SDK runs in a plugin-local worker environment; the plugin does not import Hermes's internal computer-use handler.
- Runtime receipts are profile-scoped. The desktop lock coordinates instances of this plugin, not other GUI controllers.

## Known safety gaps

The preliminary review found gaps in sensitive-input filtering, target revalidation, unknown-action handling, uncertainty cleanup after known rejection, and child-process cleanup on forced termination. These remain unresolved in this checkpoint.

The current implementation can send the goal, candidate input text, and selected UI labels/values to TypeSafe. Do not treat the usage instructions as an enforced secret-filtering guarantee.

See [review findings](docs/review-2026-10-12.md) and the [unfinished implementation plan](docs/plans/2026-10-12-hermes-cua-with-jev.md).

## Verification so far

- Local test run: **21 passed**, including real Hermes loader discovery, toolset filtering, and profile A→B→A routing with mocked worker execution and fake credentials.
- Isolated native and browser fixtures completed a button action and verified the resulting `Status=Done` state. The measured runner times were 5.720 seconds and 4.091 seconds, respectively.
- These are smoke tests, not a conventional-versus-Jev benchmark. No speedup or main-model token reduction has been established.
- Loader integration tests currently depend on the author's local Hermes checkout and runtime paths; they are not a portable CI setup.

## Install

Installation and activation guidance is deferred until the safety fixes and re-review pass. The working environment used Python 3.11+, Cua Driver 0.30.4, and TypeSafe SDK 0.7.4. Keep `TYPESAFE_API_KEY` outside this repository; `.env`, local `config.yaml`, and `.venv/` are ignored.

The existing computer-use tools have not been disabled, and this checkpoint has not been activated in the running gateway.
