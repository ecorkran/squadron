Run a squadron pipeline via the prompt-only executor.

## Input parsing

The first word of `$ARGUMENTS` is the pipeline name. The remainder is the target argument passed to the pipeline.

If the pipeline name is missing, show the usage below and stop.

**Usage:**
```
/sq:run <pipeline> [target]    — run a pipeline (e.g., /sq:run slice 152)
```

---

## Step 0: Validate and Initialize

Run:
```bash
sq run <pipeline> <target> --prompt-only
```

This initializes the pipeline run and outputs the first step's instructions as JSON. Capture:
- The `run_id` (printed to stderr as `run_id=<value>`)
- The JSON step instructions (printed to stdout)

If the command fails (invalid pipeline, missing params), show the error and stop.

---

## Main Loop

Parse the JSON output. The structure is:

```json
{
  "run_id": "...",
  "step_name": "...",
  "step_type": "...",
  "step_index": 0,
  "total_steps": 6,
  "actions": [
    {
      "action_type": "cf-op|dispatch|review|checkpoint|commit|compact|devlog",
      "instruction": "Human-readable description",
      "command": "shell command to run (if applicable)",
      "model": "model alias (if applicable)",
      "model_switch": "/model alias (if applicable)",
      "template": "template name (if applicable)",
      "trigger": "checkpoint trigger (if applicable)",
      "resolved_instructions": "resolved compact instructions (if applicable)"
    }
  ]
}
```

For each action in the step's `actions` list, execute based on `action_type`:

### cf-op
Run the `command` field via Bash. Example: `cf set phase 4`, `cf build`.

### dispatch
This is in-session work — you perform the task described in `instruction`.
If `model_switch` is present (e.g., `/model opus`), note the recommended model. In Claude Code CLI sessions, you can issue the model switch command. In IDE sessions, this is informational only.

### review
Run the `command` field via Bash. Example: `sq review slice 152 --model glm5 --template slice -v`.
Capture the output. The review will produce a verdict (PASS, CONCERNS, FAIL) and persist the review file automatically.

### checkpoint
Evaluate based on the `trigger` field and the previous review's verdict:
- `on-concerns`: Pause if verdict is CONCERNS or FAIL
- `on-fail`: Pause if verdict is FAIL
- `always`: Always pause for user decision
- `never`: Skip (continue automatically)

If the checkpoint triggers, present the review findings to the user and ask for a decision:
- **Continue**: Proceed to the next step
- **Abort**: Stop the pipeline

If the checkpoint does not trigger, continue automatically.

### commit
Run the `command` field via Bash. Example: `git add -A && git commit -m 'phase-4: ...'`.

### compact
Run the `command` field, which is a `/compact [...]` invocation with resolved instructions.
The `resolved_instructions` field contains the full compaction instructions for reference.

### devlog
Execute the work described in `instruction` — write a DEVLOG entry capturing the pipeline run state.

---

## After Each Step

After completing all actions in a step, mark it done:

```bash
sq run --step-done <run-id>
```

If the step included a review action, include the verdict:

```bash
sq run --step-done <run-id> --verdict <PASS|CONCERNS|FAIL>
```

---

## Get Next Step

After marking a step done, request the next step:

```bash
sq run --prompt-only --next --resume <run-id>
```

Parse the JSON output:
- If it contains `step_name` and `actions`, loop back to the Main Loop.
- If it contains `"status": "completed"`, the pipeline is done — proceed to Completion.

---

## Error Handling

- If `sq run --prompt-only` fails on initialization: show the error and stop.
- If `sq run --step-done` fails: show the error but don't lose progress. The run state is preserved and can be resumed.
- If a checkpoint pauses execution: present findings to the user. On abort, the run can be resumed later with `sq run --prompt-only --next --resume <run-id>`.
- If a review verdict is FAIL with an `on-fail` checkpoint: stop and present findings. Do not silently continue.

---

## Completion

When the pipeline returns `"status": "completed"`, provide a brief summary:
- Steps completed and their verdicts
- Artifacts created (design files, task files, review files)
- Commits made during the pipeline
- Any unresolved concerns or deferred items

Run `sq run --status <run-id>` for a final state summary if needed.
