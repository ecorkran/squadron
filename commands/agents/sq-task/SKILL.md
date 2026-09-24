---
name: sq-task
description: Sends a one-shot task to a named squadron agent. Use when the user wants to give an already-running agent a prompt to work on.
---

# sq task

Run `sq task`, appending whatever the user typed after `$sq-task` as arguments.

This sends a one-shot task to a named agent. Format: `sq task AGENT_NAME "prompt text"`

If the user typed nothing after `$sq-task`, run `sq task --help` and show the usage.

## Waiting on the command

The `sq` commands this skill runs can take several minutes, print their own progress, and
finish on their own. Waiting costs nothing; checking on them does, because every check is a
full model turn.

- Run each command **once**. Never start it again because it seems slow.
- If the command is still running when the tool returns and you are given a session ID, wait
  on that session with `write_stdin`, empty `chars`, and `yield_time_ms` set to `300000`.
  Repeat exactly that until the command exits.
- Between waits, do nothing else: no status checks, no reading files, no commentary.
