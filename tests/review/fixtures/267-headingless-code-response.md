### [CONCERN] Degraded terminal message assumes a saved markdown artifact

`_display_terminal` now tells the user that "The model's findings are in the saved review's `### Raw Response` section." This is true for the default terminal + markdown save flow, but misleading when `--no-save` is used (no saved file exists) or when the user later views only the JSON artifact (`ReviewResult.to_dict()` excludes `raw_output`). The previous message at least directed the user toward an action ("re-run with -vv"). Consider either gating the wording on `no_save`/output mode or making the message describe where the output is guaranteed to be (e.g., the in-memory `ReviewResult.raw_output`).

### [PASS] Tool-use guidance is composed once, at the agent constructor

`compose_system_prompt` centralizes the guidance block and is invoked inside `OpenAICompatibleAgent.__init__` after tool resolution. This satisfies design D1: callers cannot pass tools while forgetting the discipline block, and the block names only the tools the agent actually holds. The prose is intentionally tool-agnostic so it works for both review and dispatch templates.

### [PASS] SDK system prompt composes with instructions instead of discarding them

When `use_default_system_prompt=True`, the provider now sends `{"type": "preset", "preset": "claude_code", "append": instructions}` instead of sending the bare preset. This fixes #85: review templates keep the CLI's tool-use discipline while still applying their own instructions. The empty-instructions case correctly stays a bare preset, and the non-default case still sends the instructions verbatim.

### [PASS] Degraded artifacts embed the raw response at default verbosity

The `degraded` flag and the `result.system_prompt is None` guard ensure a failed/UNKNOWN parse always embeds the model's actual output in the markdown artifact exactly once, while a `-vv` appendix prevents duplication. The judge override case is correctly excluded, and the new `## Findings Not Parsed` body avoids the false "No specific findings" claim fixed in #72.

### [PASS] Tool-use telemetry is surfaced observably in review artifacts and logs

A review that is handed tools but makes no calls now logs a `WARNING`, and `_display_tool_telemetry` renders the three telemetry states distinctly on the terminal. The suppressed-reason state, the offered-but-unused state, and the no-tools state are no longer collapsed, matching the telemetry design in the markdown frontmatter.

### [PASS] Tests cover the new behavior and document the design rationale

The added tests verify the SDK preset-append matrix, the canonical→Claude tool name translation, the OpenAI guidance composition, the degraded artifact raw-response embedding, and the terminal telemetry styling. Comments in the tests explain why each guard exists, which helps future maintainers avoid reintroducing the regressions these changes fix.
