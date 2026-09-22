---
name: sq-spawn
description: Spawns a new squadron agent with a name, type and provider. Use when the user asks to start, spawn, or create an agent.
---

# sq spawn

Run `sq spawn`, appending whatever the user typed after `$sq-spawn` as arguments.

Common flags: `--name NAME` (required), `--type sdk|openai`, `--provider PROVIDER`,
`--profile PROFILE`, `--cwd PATH`, `--model MODEL`, `--system-prompt TEXT`.

If the user typed nothing after `$sq-spawn`, run `sq spawn --help` and show the usage.
