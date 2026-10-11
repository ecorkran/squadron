<!-- source: squadron project-documents/user/tasks/; each line below is preceded by a comment naming its file and line. Expected hits: none -->
<!-- 113-tasks.provider-variants.md line 96 -->
  - [x] In `spawn()`, when `--profile` is given, merge resolved profile fields into `request_data`
<!-- 120-tasks.model-alias-registry.md line 84 -->
  - [x] Add `get_all_aliases() -> dict[str, ModelAlias]` — merges built-in + user (user overrides)
<!-- 127-tasks.scoped-code-review-prompt-logging.md line 43 -->
  - [x] Run `git log --merges --oneline --grep='{N}-slice' main -1`
<!-- 127-tasks.scoped-code-review-prompt-logging.md line 54 -->
    - [x] Run `git merge-base main {branch}` to get divergence point
<!-- 149-tasks.pipeline-executor-and-loops.md line 109 -->
  - [x] `ActionContext.params` = merged pipeline params + action config (action config keys override)
<!-- 197-tasks.implementation-batch-pipeline-implement-plan.md line 55 -->
- [x] Tests (temp repo): ahead by N; not ahead; only merge commits ahead → 0; behind by N; each helper's non-zero exit and timeout raise with the asserted ERROR record
<!-- 197-tasks.implementation-batch-pipeline-implement-plan.md line 83 -->
  - [x] Not behind: no merge attempted
