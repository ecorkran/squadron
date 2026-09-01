---
docType: review
layer: project
reviewType: code
slice: dispatch-action-wiring-and-pipeline-yaml-surface
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/263-slice.dispatch-action-wiring-and-pipeline-yaml-surface.md
aiModel: claude-opus-5
status: complete
dateCreated: 20260901
dateUpdated: 20260901
reviewedSha: d48122b
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "SDK session path silently drops allowed_tools and returns success"
    location: "src/squadron/pipeline/actions/dispatch.py:176"
  - id: F002
    severity: concern
    category: correctness
    summary: "Unconditional cwd changes SDK one-shot agent behavior"
    location: "src/squadron/pipeline/actions/dispatch.py:415"
  - id: F003
    severity: note
    category: correctness
    summary: "test-p4.yaml tools may route to SDK under a model override"
    location: "src/squadron/data/pipelines/test-p4.yaml:13"
  - id: F004
    severity: note
    category: consistency
    summary: "Non-string entry check returns instead of accumulating"
    location: "src/squadron/pipeline/steps/utils.py:52"
---

# Code Review: Slice 263 — Dispatch Action Wiring and Pipeline YAML Surface

Reviewed at `d48122b`. All four findings were addressed in `0fd9d1a`; full suite green
(3148 passed, 2 skipped) after the fixes.

## Summary

The core wiring for the non-SDK agent path is sound. Validation accumulates unknown-tool errors,
malformed values fail loudly rather than silently dropping tools, and the integration test
asserts a real file reaches disk rather than asserting a mock was called. The diff matches the
design's five-file scope exactly, with `loader.py` untouched — the intended signal that the
existing extension point carried the validation.

Two findings were consequential, and both sat in code this slice wrote.

## F001 — SDK session path silently drops `allowed_tools` (concern)

`_dispatch_via_session` never references `allowed_tools`. A step declaring tools that routed to
the session ran tool-less, returned `success=True`, and logged nothing. Load-time validation
cannot catch this: the routing decision is made at runtime, so a pipeline that validates cleanly
still degrades to the exact no-op-with-prose failure this slice exists to prevent.

**Fixed** in `0fd9d1a`. The session path returns a failed `ActionResult` when tools are
declared, and `one_shot_dispatch` raises when the resolved profile's provider is the SDK.
Full wiring is out of scope — registry names (`read_file`) are not SDK vocabulary (`Read`), and
slice 265 owns that mapping — so the fix closes the silent-failure gap without expanding scope.

## F002 — Unconditional `cwd` changes SDK one-shot behavior (concern)

`providers/sdk/provider.py:58` forwards a non-None `cwd` into `ClaudeAgentOptions`, which
previously never received the key, and `alias_profile or ProfileName.SDK` means the one-shot
path can select an SDK profile. Design decision D2's "inert" justification only ever covered the
non-SDK agent.

**Fixed** in `0fd9d1a` by gating on the resolved provider inside `one_shot_dispatch`, where the
provider is known. Two false starts are worth recording, both caught by existing tests rather
than inspection: gating on `profile_name == ProfileName.SDK` wrongly catches the `None`-alias
fallback (which names the SDK profile but still routes through the one-shot agent), and gating
at the call site is too early, because the provider is not yet resolved there.

## F003 — `test-p4.yaml` tools may route to SDK (note)

The design step's `model: "{model}"` defaults to `kimi27` (openrouter), so the shipped path is
correct. Under a `--model` override selecting an SDK alias, the declared tools would previously
have been dropped silently. **Fixed** by F001's guard, which now turns that case into a loud
failure. The vocabulary mismatch itself remains slice 265's scope.

## F004 — Non-string check returns instead of accumulating (note)

`validate_allowed_tools` returned on the first non-string element, contradicting its own
docstring's batch-reporting promise and hiding any errors after it — inconsistent with the
unknown-name loop directly below, which accumulates. **Fixed**: bad elements now accumulate
alongside unknown names, covered by a new test.

## Verification status

The `allowed_tools` -> `AgentConfig` -> registry -> filesystem path is confirmed working against
a real non-SDK model: in a live `sq run test-p4 264 -v`, the model reported specific paths it had
probed and found missing, which requires actual `read_file` calls. See the slice design's
Verification Walkthrough §4 for the full observation, including two pre-existing issues that run
surfaced (the 909 post-condition cannot pass for an undesigned slice; CF prompt-template guide
paths do not match the tree). The contrast case (11.3) remains outstanding.
