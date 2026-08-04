---
docType: tasks
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
lld: user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md
dependencies: []
projectState: >
  Slice 172 designed and design-reviewed (PASS, six notes resolved) on main at
  2ca8ecb. No implementation yet. Slice 171 (post-action hooks) is deferred —
  designed, not built — and 172 replaces it as the answer to invalid document
  frontmatter. The parent architecture 140-arch.pipeline-foundation.md was
  updated during review resolution to name documents/schema.py and
  documents/validate.py as the real modules. 24 known violations exist under
  project-documents/user/, five of them unparseable review artifacts produced
  by squadron itself.
dateCreated: 20260803
dateUpdated: 20260803
status: not_started
---

## Context Summary

- Working on the **sq-validate-docs-mechanical-frontmatter-enforcement** slice
  (172). Parent slice plan:
  `user/architecture/140-slices.pipeline-foundation.md`, entry 29.
- **The point of the slice:** `file-naming-conventions.md` defines canonical
  document metadata in prose and enforces none of it. This slice adds a
  deterministic validator and puts it on the `git commit` boundary, which is
  LLM-independent and crossed by every workflow.
- **Enforcement lives at the commit, not in the pipeline.** That is what makes
  this 1/5 rather than 171's 3/5. Do not add pipeline hooks, executor changes,
  or anything that runs during `sq run`.
- **Two document classes.** Process documents (the spec's fifteen `docType`
  values) get full validation. Machine artifacts squadron writes into the same
  tree (`review-resolution`, `gate-evidence`, `devlog`) legitimately carry no
  `status` and no `dateUpdated`, and must validate clean. A gate that fires on
  its own tool's correct output is how people learn to use `--no-verify`.
- **Scope is a configured root**, not every `.md`. `README.md`, `CLAUDE.md`,
  `docs/*`, `commands/sq/*.md`, and `.claude/agents/*.md` are correctly
  frontmatter-free and must never be flagged. Paths passed on the command line
  are *filtered* against the root, never trusted — that is what lets the hook
  hand over the whole staged file list.
- **The corruption class that motivated half the design:** five review
  artifacts under `user/reviews/` have frontmatter that looks correct and does
  not parse, because a finding's `location:` value contains a colon-space.
  `read_frontmatter` returns `None` for a YAML error exactly as for a file with
  no block (`documents/frontmatter.py:50-53`), so nothing distinguished the
  two. `metrology/identity.py:180` and `review/resolution_evidence.py:132`
  both raise on those files.
- **The producer is squadron:** `review/persistence.py:222` renders
  `location` as an unquoted f-string while line 220 quotes `summary` through
  `yaml_escape`. Both carry model-authored free text.
- **Ordering is load-bearing.** The writer fix (Part 4) lands before the
  cleanup (Part 6) so the cleanup is not invalidated by a fresh review; the
  cleanup lands before CI (Part 8) so `main` is never red between two commits
  of this slice.
- **Out of scope, do not touch:** per-`docType` schema validation, filename or
  index checks, cross-document reference integrity, a `--fix` mode, installing
  the hook into other projects, migrating `_render_review` wholesale to
  `render_frontmatter_block` (test-coupled — recorded as Future Work), and the
  `ai-project-guide` submodule's contents.

---

## Part 1 — Canonical Values and the Drift Guard

- [ ] **T1. Create `src/squadron/documents/schema.py`**
  - [ ] Define `DocumentStatus(StrEnum)` with exactly the five spec values:
    `not_started`, `in_progress`, `complete`, `deferred`, `deprecated`.
  - [ ] Define `STATUS_ALIASES: dict[str, DocumentStatus]` containing the one
    alias the spec blesses (`file-naming-conventions.md:61`). It is accepted on
    read; nothing in squadron emits it.
  - [ ] Define `DocType(StrEnum)` with the fifteen values listed at
    `file-naming-conventions.md:30`.
  - [ ] Define the machine-artifact docTypes **here**, in `schema.py`, and
    expose them as `MACHINE_ARTIFACT_DOC_TYPES: frozenset[str]`. These are the
    docTypes squadron itself writes that are not in the spec:
    `review-resolution`, `gate-evidence`, `devlog`.
  - [ ] Flip the three existing definitions to import from `schema.py` rather
    than declaring their own: `RESOLUTION_DOC_TYPE`
    (`review/resolution_artifact.py:25`), `GATE_EVIDENCE_DOC_TYPE`
    (`pipeline/actions/findings_addressed/evidence.py:26`), and the literal
    `"docType: devlog"` rendered at `pipeline/actions/devlog.py:104`. Keep the
    existing names as aliases if that reads better at the call sites; the rule
    is one definition, not one spelling.
  - [ ] **Direction matters.** `documents/` is the shared primitives package —
    it must not import from `review/` or `pipeline/`. Sourcing the values the
    other way would also be a real import cycle once T13 makes
    `frontmatter.py` import `schema.py`: `documents.frontmatter` →
    `documents.schema` → `review.resolution_artifact` →
    `documents.frontmatter`.
  - [ ] Define `REQUIRED_UNIVERSAL_FIELDS: tuple[str, ...]` — the five fields
    at `file-naming-conventions.md:20-27`. Applies to process documents only.
  - [ ] Add a module docstring stating that this module is the single
    definition of these values for all of squadron, and that
    `file-naming-conventions.md` is the upstream source.
  - [ ] Success: `pyright` strict clean; the three modules above import their
    docType from `schema.py`; the only remaining status/docType literals in
    `src/` are the two in `review/persistence.py` (lines 187 and 195), which
    T11 removes.

- [ ] **T2. Drift test against the spec** (test-with)
  - [ ] Create `tests/documents/test_schema_drift.py`.
  - [ ] Parse the status values out of the "Valid Status Values" section of
    `project-documents/ai-project-guide/file-naming-conventions.md` and assert
    the set equals `DocumentStatus`'s members. Parse leniently — match the
    backticked token at the start of each bullet; do not require exact
    whitespace or a fixed bullet count.
  - [ ] Parse the `docType` list from the "Valid `docType` values:" line and
    assert the set equals `DocType`'s members.
  - [ ] Assert the machine-artifact types are **not** present in the spec —
    they are squadron-owned, and a future upstream addition should surface as
    a failing test rather than a silent overlap.
  - [ ] If the file is absent (submodule not initialized), the test must
    **fail** with a message naming `git submodule update --init`. It must not
    skip: a skipped drift test is a silent fallback, and drift is the exact
    risk that ended slice 171's frontmatter consumer.
  - [ ] Success: all four assertions pass locally with the submodule present.

---

## Part 2 — The Validator

- [ ] **T3. Create `src/squadron/documents/validate.py` — types and codes**
  - [ ] Define `ViolationCode(StrEnum)` with `FM001`–`FM008` per the design's
    D3 table. Each member carries only the code; the human message is built at
    report time.
  - [ ] Define a frozen `Violation` dataclass: `path: Path`, `line: int`,
    `code: ViolationCode`, `key: str | None`, `actual: str | None`,
    `accepted: tuple[str, ...]`, `detail: str | None`.
  - [ ] The module performs **no printing and no `sys.exit`**. It takes paths
    and returns `list[Violation]`. That keeps it testable without a CLI runner
    and callable later from `sq doctor` or an MCP tool.
  - [ ] Success: `pyright` strict clean.

- [ ] **T4. Implement single-document validation**
  - [ ] `validate_document(path: Path) -> list[Violation]`.
  - [ ] Read the file as UTF-8. On `UnicodeDecodeError`, return a single
    `FM008` and stop — do not let it propagate.
  - [ ] Reuse `_split_document` from `documents/frontmatter.py` to locate the
    block (promote it to a public name if it is cleaner than importing an
    underscore-prefixed function; do not copy its logic).
  - [ ] No block → `FM001` at line 1. Block present but `yaml.safe_load`
    raises → `FM002`, carrying the YAML error's line/column in `detail`,
    with the line translated into document coordinates (the block's start
    offset is known). Parses but is not a mapping → `FM003`.
  - [ ] Classify by `docType`: unknown value → `FM006`. A machine-artifact
    docType skips the `FM004`/`FM005` checks.
  - [ ] Process documents: each missing field in `REQUIRED_UNIVERSAL_FIELDS`
    → one `FM004`; a `status` outside `DocumentStatus` ∪ `STATUS_ALIASES`
    → `FM005`.
  - [ ] Both classes: `dateCreated`/`dateUpdated`, **when present**, must
    match `\d{8}` and be a real calendar date → `FM007`.
  - [ ] Line numbers: find the offending key by scanning the raw block, and
    report its real document line. Where there is no offending line
    (`FM001`, `FM004`) report the opening fence, or line 1 when there is no
    block. Never invent a number.
  - [ ] Success: one document yields all applicable violations, not just the
    first — a caller fixing one problem should not have to re-run to discover
    the next.

- [ ] **T5. Tests for single-document validation** (test-with)
  - [ ] Create `tests/documents/test_validate.py` with one test per code,
    `FM001`–`FM008`, each using a realistic fixture rather than a minimal
    synthetic one.
  - [ ] `FM002` fixture must reproduce the real defect:
    `location: Slice design: Implementation Details` inside a `findings:`
    list. Assert the code is `FM002` (not `FM001`) and that `detail` carries
    a line number pointing inside the block.
  - [ ] Machine-artifact test: render whole documents via `render_gate_evidence`
    (`pipeline/actions/findings_addressed/evidence.py:122`) and
    `render_resolution` (`review/resolution_artifact.py:116`), write each to a
    file, and assert **zero** violations. Use the full-document renderers, not
    the `*_frontmatter` mapping builders — the validator reads files, so the
    test must exercise exactly what lands on disk, including the fence.
    This is the regression guard against the gate firing on squadron's own
    output.
  - [ ] A valid process document of each of the three common docTypes
    (`slice-design`, `tasks`, `review`) yields zero violations.
  - [ ] A document with two problems yields two violations.
  - [ ] Success: full `tests/documents/` suite green.

- [ ] **T6. Implement path selection and `validate_paths`**
  - [ ] `validate_paths(paths: Sequence[Path] | None, *, root: Path) -> list[Violation]`.
  - [ ] With `paths=None`, walk `root` for `*.md`. With paths given, keep only
    those that are `.md` **and** resolve under `root`; silently skip the rest.
  - [ ] Skip any file whose first 2 KB contains the `context-forge:managed`
    marker (`file-naming-conventions.md:43`). Define the marker string once,
    in `schema.py`.
  - [ ] Return violations sorted by path then line, so output is stable
    across runs and diffable.
  - [ ] Raise a typed error (not `SystemExit`) when `root` does not exist or a
    named path does not exist; the CLI layer maps it to exit 2.
  - [ ] Success: `validate_paths(None, root=Path("project-documents/user"))`
    runs over the real tree without raising.

- [ ] **T7. Tests for path selection** (test-with)
  - [ ] Passing `README.md`, `CLAUDE.md`, and `docs/QUICKSTART.md` yields zero
    violations — outside the root, not flagged.
  - [ ] Passing a mixed list (one in-root violating document plus three
    out-of-root files) yields exactly the one violation.
  - [ ] A file carrying the `context-forge:managed` marker inside the root is
    skipped.
  - [ ] A non-`.md` file inside the root is skipped.
  - [ ] Nonexistent root and nonexistent named path each raise the typed error.
  - [ ] Success: all five pass.

---

## Part 3 — Config Key and CLI Surface

- [ ] **T8. Add the `validate.docs_root` config key**
  - [ ] In `src/squadron/config/keys.py`, add a `ConfigKey` named
    `validate.docs_root`, `type_=str`, default `project-documents/user`, with
    a description saying it is the root under which markdown is validated as
    process documents.
  - [ ] `str` is already supported by `config/manager.py:_coerce_value` — no
    config-type work is needed. Do not widen the coercion function.
  - [ ] Success: `sq config get validate.docs_root` prints the default;
    `sq config set validate.docs_root <path>` round-trips.

- [ ] **T9. Create `src/squadron/cli/commands/validate.py`**
  - [ ] Build a typer sub-app `validate_app` with a `docs` command taking
    variadic `PATHS`, `--root` (override), and `-q/--quiet`.
  - [ ] Resolve the root: `--root` if given, else the config value. Do not
    hard-code the default here — read it from `CONFIG_KEYS`.
  - [ ] Format each violation as two lines: `path:line: CODE key: message`,
    then an indented `accepted: a | b | c` when the check has an accepted set.
  - [ ] Write the summary (`N documents checked, M violations in K files`) to
    **stderr**, on every run including clean ones, unless `--quiet`. Silence
    must never be the only evidence the validator ran.
  - [ ] Exit codes: 0 clean, 1 violations, 2 invocation error (missing root,
    missing named path, permission/IO fault). Catch the typed error from T6
    and map it; no traceback may escape the command.
  - [ ] Success: `pyright` strict clean.

- [ ] **T10. Wire the sub-app and test the CLI** (test-with)
  - [ ] In `src/squadron/cli/app.py`, add
    `app.add_typer(validate_app, name="validate")` alongside the existing
    `add_typer` calls (lines 48-54).
  - [ ] Create `tests/cli/test_validate_docs.py` using the existing typer
    `CliRunner` pattern from the other CLI tests.
  - [ ] Assert each exit code path: clean run (0), a violating document (1),
    nonexistent `--root` (2), nonexistent named path (2), and a non-UTF-8
    `.md` under the root (1 with `FM008`, **not** a traceback).
  - [ ] Assert the summary line appears on stderr for a clean run and is
    suppressed by `--quiet` while violations still print.
  - [ ] Assert output contains the accepted-values line for an `FM005`.
  - [ ] Success: all assertions pass; `sq validate docs --help` renders.

---

## Part 4 — Fix the Review Writer

- [ ] **T11. Quote `location` in `_render_review`**
  - [ ] In `src/squadron/review/persistence.py:222`, render the location as
    `f'    location: "{yaml_escape(sf.location)}"'`, matching how `summary` is
    already rendered on line 220.
  - [ ] Add a one-line comment naming why: `location` and `summary` are the
    only fields in this hand-built block carrying model-authored free text.
  - [ ] While in this function, replace the two remaining canonical-value
    literals with imports from `schema.py`: `"docType: review"` (line 187)
    becomes `DocType.REVIEW` and `"status: complete"` (line 195) becomes
    `DocumentStatus.COMPLETE`, each interpolated into the rendered line. These
    are the last two sites; T1 handles the other three.
  - [ ] Do **not** migrate the rest of the block to `render_frontmatter_block`
    in this slice. It is the correct fix, several test modules assert on the
    exact rendered text, and it is recorded as Future Work in the design.
  - [ ] Success: existing review-persistence tests pass, or their expected
    strings are updated only where the location line itself is asserted.

- [ ] **T12. Regression test for the corruption class** (test-with)
  - [ ] In `tests/review/test_persistence.py`, write a review whose structured
    finding has a location containing a colon-space (use a realistic value,
    e.g. a document anchor of the form seen in the five corrupted artifacts).
  - [ ] Assert `read_frontmatter` on the written file returns a **mapping**,
    and that the round-tripped location equals the original string.
  - [ ] Add the mirror-image test: a location containing an embedded double
    quote survives `yaml_escape` and still round-trips.
  - [ ] Add a single-definition test: assert that no module in `src/` outside
    `documents/schema.py` contains a canonical status or docType value as a
    string literal. Implement it as a source grep over `src/**/*.py` driven by
    the enum members, so a value added to `schema.py` later is covered without
    editing the test. This is the mechanical form of the design's success
    criterion 6 — a criterion only a grep in a close-out checklist can enforce
    is one that silently rots.
  - [ ] Success: all three pass; the first fails if T11 is reverted, and the
    third fails if any of the five known literal sites is left behind.

---

## Part 5 — Structural Hardening of the Frontmatter Writers

- [ ] **T13. Validate `status` in `documents/frontmatter.py`**
  - [ ] In `update_frontmatter` (line 94) and `render_frontmatter_block`
    (line 76), raise `FrontmatterError` when a **top-level** `status` key is
    present and its value is not a `DocumentStatus` (aliases accepted).
  - [ ] Present-and-invalid only. Never required — machine artifacts
    legitimately omit `status`, and requiring it would break
    `gate_evidence_frontmatter` immediately.
  - [ ] The error message must name the offending value and the accepted set.
  - [ ] Import from `schema.py`; do not restate the values.
  - [ ] Success: no existing call site changes behavior. Verified by
    construction — `render_frontmatter_block`'s two consumers carry `status`
    only inside nested `findingStatuses` entries (a `FindingStatus`, not a
    document status), and `update_frontmatter`'s only caller
    (`executor.py:269`) writes `revision_number`.

- [ ] **T14. Tests for the hardening** (test-with)
  - [ ] `update_frontmatter` with `{"status": "draft"}` raises
    `FrontmatterError` naming the accepted values.
  - [ ] `update_frontmatter` with a valid status succeeds and preserves the
    body byte-for-byte.
  - [ ] `render_frontmatter_block` with a nested `findingStatuses` entry
    carrying a finding-level `status` does **not** raise.
  - [ ] `render_frontmatter_block` with no `status` key does not raise.
  - [ ] Success: the whole existing suite is still green, with no assertion
    changed anywhere.

---

## Part 6 — One-Time Cleanup (its own commit)

- [ ] **T15. Repair the five unparseable review artifacts**
  - [ ] Run `uv run sq validate docs` and use its output as the work list.
    Do not work from a list transcribed here — re-derive it, then compare.
  - [ ] For each `FM002` review artifact, quote the offending `location:`
    value. Change nothing else in the file; these are historical records.
  - [ ] Verify each with `read_frontmatter` returning a mapping.
  - [ ] Success: zero `FM002` violations remain.

- [ ] **T16. Fix the remaining violations**
  - [ ] Non-canonical `status` values: decide each by **reading the document**,
    not by a lookup table. `in-progress` and `not-started` are mechanical;
    `active`, `draft`, and `superseded` are judgment calls.
  - [ ] Missing `status`: add the value the document's content supports.
  - [ ] `docType: task-breakdown` and `docType: slice-tasks` → `tasks`. No
    squadron code reads either value; confirm with a grep before editing.
  - [ ] Files with no frontmatter block: add a complete universal block.
    Archived documents are validated like any other — do not add an
    `archive/` exemption to buy off two files.
  - [ ] Commit the cleanup **separately** from the feature work, with a
    message saying it is the one-time cleanup for slice 172.
  - [ ] Success: `uv run sq validate docs` exits 0 over the full root.

---

## Part 7 — The Commit Gate

- [ ] **T17. Create `.githooks/pre-commit`**
  - [ ] Collect staged markdown:
    `git diff --cached --name-only --diff-filter=ACM -- '*.md'`. Exit 0
    immediately when the list is empty.
  - [ ] Run `uv run --quiet sq validate docs -- <paths>` and propagate its
    exit code.
  - [ ] On failure, print the `--no-verify` escape hatch explicitly. A gate
    with a hidden override is a gate people fight instead of use.
  - [ ] If `sq` cannot be launched at all, exit **non-zero** with a message
    naming the likely cause. A hook that skips when its tool is missing
    enforces nothing while appearing to work.
  - [ ] Handle paths with spaces correctly (quote, or use `-z` and read
    NUL-delimited).
  - [ ] `chmod +x` and confirm the executable bit is committed
    (`git ls-files -s` shows mode `100755`).
  - [ ] Success: the walkthrough in the design's step 5 behaves as written.

- [ ] **T18. `sq doctor` reports whether the hook is installed**
  - [ ] Add `check_git_hooks(hooks_path: str | None) -> CheckResult` to
    `cli/commands/doctor_checks.py`, following the existing `CheckResult` /
    `CheckStatus` shape (lines 42-56). Keep it **pure** — the module's
    docstring promises no subprocesses.
  - [ ] In `cli/commands/doctor.py`, obtain the value with
    `run_git(["config", "--get", "core.hooksPath"], cwd=...)` from
    `review/git_utils.py:19` and pass it in. Reuse `run_git`; do not call
    `subprocess` directly.
  - [ ] Report OK when the value is `.githooks`, a warning naming the exact
    `git config core.hooksPath .githooks` command otherwise. Not being in a
    git repo is not an error.
  - [ ] Success: `sq doctor` shows the check in both states.

- [ ] **T19. Tests and documentation for the gate** (test-with)
  - [ ] Unit-test `check_git_hooks` for all three inputs: `.githooks`, some
    other value, and `None`.
  - [ ] Document the one-time `git config core.hooksPath .githooks` install in
    the README (or contributing docs, wherever contributor setup lives) next
    to the existing `uv sync` instructions. The install step is part of the
    deliverable — a hook nobody installs is the failure mode being escaped.
  - [ ] Walk the design's verification steps 5 and 6 by hand and confirm the
    commit is refused for a bad document and allowed for a touched `README.md`.
  - [ ] Success: both walkthrough steps behave as documented; correct the
    walkthrough in the slice design if reality differs.

---

## Part 8 — CI Backstop (must land after Part 6)

- [ ] **T20. Add the validator to CI**
  - [ ] In `.github/workflows/ci.yml`, add `with: submodules: true` to the
    `actions/checkout` step of the `test` job. The drift test from T2 reads
    `file-naming-conventions.md` from the submodule and fails without it.
    `ecorkran/ai-project-guide` is public, so no token is required.
  - [ ] Add `- run: uv run sq validate docs` to the `test` job, after the
    existing `ruff`/`pyright` steps and before `pytest`.
  - [ ] Do not merge this before T15/T16 have landed, or `main` goes red
    between two commits of the same slice.
  - [ ] Success: CI is green on the branch with both steps present.

---

## Part 9 — Close Out

- [ ] **T21. Full verification pass**
  - [ ] Run every step of the design's Verification Walkthrough in order and
    confirm each behaves as written. Update the walkthrough where reality
    differs — it becomes the slice's demo script.
  - [ ] `uv run ruff format`, then `uv run ruff check`, `uv run pyright`,
    `uv run pytest`, and `uv run sq validate docs` — all clean.
  - [ ] Confirm no status or docType string literal exists in `src/` outside
    `documents/schema.py` (grep for the values).
  - [ ] Success: all five commands exit 0.

- [ ] **T22. Documentation and slice close-out**
  - [ ] CHANGELOG: a short user-facing bullet for `sq validate docs` and the
    commit gate. Technical detail belongs in DEVLOG, not here.
  - [ ] DEVLOG: implementation entry per the Session State Summary guidance.
  - [ ] Mark slice 172 complete in this task file's frontmatter, in the slice
    design's frontmatter, and in entry 29 of
    `user/architecture/140-slices.pipeline-foundation.md`.
  - [ ] Success: the slice plan entry is checked off and the design's status
    reads `complete`.
