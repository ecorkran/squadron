---
name: sq-task
description: Sends a one-shot task to a named squadron agent. Use when the user wants to give an already-running agent a prompt to work on.
---

# sq task

Run `sq task`, appending whatever the user typed after `$sq-task` as arguments.

This sends a one-shot task to a named agent. Format: `sq task AGENT_NAME "prompt text"`

If the user typed nothing after `$sq-task`, run `sq task --help` and show the usage.
