---
docType: tasks
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
lld: user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md
dependencies:
  - context-forge#72
  - context-forge#73
projectState: >
  REOPENED 20260804. Parts 1-9 are implemented, code-reviewed, and committed on
  branch 172-slice.sq-validate-docs-mechanical-frontmatter-enforcement (033b3fb,
  4088a45); the branch is unmerged. Only Part 10 (T27-T32) remains, and it is
  BLOCKED on context-forge#73 (exposes `cf validate frontmatter`), which is
  itself blocked on context-forge#72 (status-spelling fix; cf slice 922 is
  designed and task-broken, implementation not started as of 20260806).
  Do not start Part 10 until `cf validate frontmatter` exists to call.
  Parts 1-3 are SUPERSEDED: they built a Python validator (documents/validate.py,
  cli/commands/validate.py) and a schema transcription that duplicate Context
  Forge's validateFrontmatter. Their items remain [x] because the work genuinely
  happened, but Part 10 deletes that code - do not extend, refactor, or rebuild
  it. Parts 4, 5, 5A, 6, 8 stand as shipped: the review-writer `location:` quoting
  fix, the frontmatter write-path hardening, the date-stamping fixes, the one-time
  cleanup, and the CI backstop are all unaffected by the reopening. Part 9's T22
  completion claims are withdrawn (the CHANGELOG bullet needs rewriting, since
  `sq validate docs` will not exist). The governing decision is D10: Context Forge
  maintains the schema, squadron uses it and owns only the gate. Slice 173
  (user-definable actions on supported events) supersedes the deferred 171 and may
  change T30's shape - see the design's Relationship note.
dateCreated: 20260803
dateUpdated: 20260806
status: in_progress
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
  tree (`review-resolution`, `gate-evidence`, `devlog`) have no lifecycle and
  so carry no `status`, but they do carry `dateCreated`, and they must
  validate clean. A gate that fires on its own tool's correct output is how
  people learn to use `--no-verify`.
- **The date rule, split by what a tool can know.** `dateCreated` belongs on
  every created file and is mechanically checkable, so it is required of both
  classes. `dateUpdated` belongs on every file edited after creation, but no
  tool reading one file can tell whether that happened — so the validator
  never requires it and only format-checks it. That half is a writer-side
  obligation, closed by Part 5A. The authored corpus already complies in full
  (413 documents, zero gaps); every gap is on the machine side.
- **`cf check` is the complement, not a competitor.** It owns per-`docType`
  schemas and cross-document consistency; this owns structure and universal
  fields. The only field `cf check --fix` writes is `status`, from the same
  five canonical values, so it cannot produce a document this gate rejects.
  Do not add a check that contradicts it — see D8a in the design.
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
  of this slice; Part 5A lands after Part 5, since T23 modifies the function
  T13 has just changed.
- **Task numbers are append-only.** Part 5A is numbered T23–T26 and sits
  between Parts 5 and 6. Renumbering T1–T22 would invalidate every reference
  in the design, the reviews, and the DEVLOG.
- **Out of scope, do not touch:** per-`docType` schema validation, filename or
  index checks, cross-document reference integrity, a `--fix` mode, installing
  the hook into other projects, migrating `_render_review` wholesale to
  `render_frontmatter_block` (test-coupled — recorded as Future Work), and the
  `ai-project-guide` submodule's contents.

---

## Part 1 — Canonical Values and the Drift Guard

> ⚠️ **PARTLY SUPERSEDED — DO NOT IMPLEMENT AS WRITTEN. Shipped; read for history only.**
>
> Part 10 (T29) reduces `schema.py` to the values squadron *writes* and retires the
> spec transcription it carried for validation; the drift test is repointed at cf
> rather than the guide. The tasks below are checked because the work happened —
> they are not a to-do list. **Anything below describing validation-side canonical
> values is scheduled for deletion; do not extend or rebuild it.** The write-side
> values (`MACHINE_ARTIFACT_DOC_TYPES` and the three definitions T1 unified) do
> survive. See D10.

- [x] **T1. Create `src/squadron/documents/schema.py`**
  - [x] Define `DocumentStatus(StrEnum)` with exactly the five spec values:
    `not_started`, `in_progress`, `complete`, `deferred`, `deprecated`.
  - [x] Define `STATUS_ALIASES: dict[str, DocumentStatus]` containing the one
    alias the spec blesses (`file-naming-conventions.md:61`). It is accepted on
    read; nothing in squadron emits it.
  - [x] Define `DocType(StrEnum)` with the fifteen values listed at
    `file-naming-conventions.md:30`.
  - [x] Define the machine-artifact docTypes **here**, in `schema.py`, and
    expose them as `MACHINE_ARTIFACT_DOC_TYPES: frozenset[str]`. These are the
    docTypes squadron itself writes that are not in the spec:
    `review-resolution`, `gate-evidence`, `devlog`.
  - [x] Flip the three existing definitions to import from `schema.py` rather
    than declaring their own: `RESOLUTION_DOC_TYPE`
    (`review/resolution_artifact.py:25`), `GATE_EVIDENCE_DOC_TYPE`
    (`pipeline/actions/findings_addressed/evidence.py:26`), and the literal
    `"docType: devlog"` rendered at `pipeline/actions/devlog.py:104`. Keep the
    existing names as aliases if that reads better at the call sites; the rule
    is one definition, not one spelling.
  - [x] **Direction matters.** `documents/` is the shared primitives package —
    it must not import from `review/` or `pipeline/`. Sourcing the values the
    other way would also be a real import cycle once T13 makes
    `frontmatter.py` import `schema.py`: `documents.frontmatter` →
    `documents.schema` → `review.resolution_artifact` →
    `documents.frontmatter`.
  - [x] Define `REQUIRED_UNIVERSAL_FIELDS: tuple[str, ...]` — the five fields
    at `file-naming-conventions.md:20-27`. Applies to process documents only.
  - [x] Define `MACHINE_ARTIFACT_REQUIRED_FIELDS: tuple[str, ...]` —
    `docType` and `dateCreated`. Machine artifacts have no lifecycle, so no
    `status`; they are never rewritten in place except the devlog, so
    `dateUpdated` is not required of them either.
  - [x] Neither tuple may require `dateUpdated`. A validator reading one file
    cannot know whether that file was ever edited after creation, so requiring
    the field would be a check the tool cannot justify. Context Forge's schema
    requires it and backfills it from `dateCreated`
    (`frontmatterSchema.ts:224`); requiring it here as well would make this
    hook *block* commits on documents `cf check --fix` considers valid. Add a
    comment stating this, so a later author does not "complete" the tuple.
  - [x] Add a module docstring stating that this module is the single
    definition of these values for all of squadron, and that
    `file-naming-conventions.md` is the upstream source.
  - [x] Success: `pyright` strict clean; the three modules above import their
    docType from `schema.py`; the only remaining status/docType literals in
    `src/` are the two in `review/persistence.py` (lines 187 and 195), which
    T11 removes.

- [x] **T2. Drift test against the spec** (test-with)
  - [x] Create `tests/documents/test_schema_drift.py`.
  - [x] Parse the status values out of the "Valid Status Values" section of
    `project-documents/ai-project-guide/file-naming-conventions.md` and assert
    the set equals `DocumentStatus`'s members. Parse leniently — match the
    backticked token at the start of each bullet; do not require exact
    whitespace or a fixed bullet count.
  - [x] Parse the `docType` list from the "Valid `docType` values:" line and
    assert the set equals `DocType`'s members.
  - [x] Assert the machine-artifact types are **not** present in the spec —
    they are squadron-owned, and a future upstream addition should surface as
    a failing test rather than a silent overlap.
  - [x] If the file is absent (submodule not initialized), the test must
    **fail** with a message naming `git submodule update --init`. It must not
    skip: a skipped drift test is a silent fallback, and drift is the exact
    risk that ended slice 171's frontmatter consumer.
  - [x] Success: all four assertions pass locally with the submodule present.

---

## Part 2 — The Validator

> ⚠️ **SUPERSEDED — DO NOT IMPLEMENT. Shipped, then scheduled for deletion. History only.**
>
> This part built `documents/validate.py`, which duplicates Context Forge's
> `validateFrontmatter`. Part 10 (T28) **deletes the entire module and its tests**.
> Items stay checked because the work was done — this is not a to-do list, and the
> code described below should not be extended, refactored, or reimplemented. If you
> need frontmatter validation, call `cf validate frontmatter` (context-forge#73).
> See D10.

- [x] **T3. Create `src/squadron/documents/validate.py` — types and codes**
  - [x] Define `ViolationCode(StrEnum)` with `FM001`–`FM008` per the design's
    D3 table. Each member carries only the code; the human message is built at
    report time.
  - [x] Define a frozen `Violation` dataclass: `path: Path`, `line: int`,
    `code: ViolationCode`, `key: str | None`, `actual: str | None`,
    `accepted: tuple[str, ...]`, `detail: str | None`.
  - [x] The module performs **no printing and no `sys.exit`**. It takes paths
    and returns `list[Violation]`. That keeps it testable without a CLI runner
    and callable later from `sq doctor` or an MCP tool.
  - [x] Success: `pyright` strict clean.

- [x] **T4. Implement single-document validation**
  - [x] `validate_document(path: Path) -> list[Violation]`.
  - [x] Read the file as UTF-8. On `UnicodeDecodeError`, return a single
    `FM008` and stop — do not let it propagate.
  - [x] Reuse `_split_document` from `documents/frontmatter.py` to locate the
    block (promote it to a public name if it is cleaner than importing an
    underscore-prefixed function; do not copy its logic).
  - [x] No block → `FM001` at line 1. Block present but `yaml.safe_load`
    raises → `FM002`, carrying the YAML error's line/column in `detail`,
    with the line translated into document coordinates (the block's start
    offset is known). Parses but is not a mapping → `FM003`.
  - [x] Classify by `docType`: unknown value → `FM006`. A machine-artifact
    docType skips the `FM004`/`FM005` checks.
  - [x] Process documents: each missing field in `REQUIRED_UNIVERSAL_FIELDS`
    → one `FM004`; a `status` outside `DocumentStatus` ∪ `STATUS_ALIASES`
    → `FM005`.
  - [x] Both classes: `dateCreated`/`dateUpdated`, **when present**, must
    match `\d{8}` and be a real calendar date → `FM007`.
  - [x] Line numbers: find the offending key by scanning the raw block, and
    report its real document line. Where there is no offending line
    (`FM001`, `FM004`) report the opening fence, or line 1 when there is no
    block. Never invent a number.
  - [x] Success: one document yields all applicable violations, not just the
    first — a caller fixing one problem should not have to re-run to discover
    the next.

- [x] **T5. Tests for single-document validation** (test-with)
  - [x] Create `tests/documents/test_validate.py` with one test per code,
    `FM001`–`FM008`, each using a realistic fixture rather than a minimal
    synthetic one.
  - [x] `FM002` fixture must reproduce the real defect:
    `location: Slice design: Implementation Details` inside a `findings:`
    list. Assert the code is `FM002` (not `FM001`) and that `detail` carries
    a line number pointing inside the block.
  - [x] Machine-artifact test: render whole documents via `render_gate_evidence`
    (`pipeline/actions/findings_addressed/evidence.py:122`) and
    `render_resolution` (`review/resolution_artifact.py:116`), write each to a
    file, and assert **zero** violations. Use the full-document renderers, not
    the `*_frontmatter` mapping builders — the validator reads files, so the
    test must exercise exactly what lands on disk, including the fence.
    This is the regression guard against the gate firing on squadron's own
    output.
  - [x] A valid process document of each of the three common docTypes
    (`slice-design`, `tasks`, `review`) yields zero violations.
  - [x] A document with two problems yields two violations.
  - [x] Success: full `tests/documents/` suite green.

- [x] **T6. Implement path selection and `validate_paths`**
  - [x] `validate_paths(paths: Sequence[Path] | None, *, root: Path) -> list[Violation]`.
  - [x] With `paths=None`, walk `root` for `*.md`. With paths given, keep only
    those that are `.md` **and** resolve under `root`; silently skip the rest.
  - [x] Skip any file whose first 2 KB contains the `context-forge:managed`
    marker (`file-naming-conventions.md:43`). Define the marker string once,
    in `schema.py`.
  - [x] Return violations sorted by path then line, so output is stable
    across runs and diffable.
  - [x] Raise a typed error (not `SystemExit`) when `root` does not exist or a
    named path does not exist; the CLI layer maps it to exit 2.
  - [x] Success: `validate_paths(None, root=Path("project-documents/user"))`
    runs over the real tree without raising.

- [x] **T7. Tests for path selection** (test-with)
  - [x] Passing `README.md`, `CLAUDE.md`, and `docs/QUICKSTART.md` yields zero
    violations — outside the root, not flagged.
  - [x] Passing a mixed list (one in-root violating document plus three
    out-of-root files) yields exactly the one violation.
  - [x] A file carrying the `context-forge:managed` marker inside the root is
    skipped.
  - [x] A non-`.md` file inside the root is skipped.
  - [x] Nonexistent root and nonexistent named path each raise the typed error.
  - [x] Success: all five pass.

---

## Part 3 — Config Key and CLI Surface

> ⚠️ **SUPERSEDED — DO NOT IMPLEMENT. Shipped, then scheduled for deletion. History only.**
>
> Part 10 (T28) **removes the `sq validate docs` command, `cli/commands/validate.py`,
> and the `validate.docs_root` config key** along with the validator behind them.
> The command will not exist — do not document it, reference it in new work, or
> restore it. Items stay checked because the work was done. See D10.

- [x] **T8. Add the `validate.docs_root` config key**
  - [x] In `src/squadron/config/keys.py`, add a `ConfigKey` named
    `validate.docs_root`, `type_=str`, default `project-documents/user`, with
    a description saying it is the root under which markdown is validated as
    process documents.
  - [x] `str` is already supported by `config/manager.py:_coerce_value` — no
    config-type work is needed. Do not widen the coercion function.
  - [x] Success: `sq config get validate.docs_root` prints the default;
    `sq config set validate.docs_root <path>` round-trips.

- [x] **T9. Create `src/squadron/cli/commands/validate.py`**
  - [x] Build a typer sub-app `validate_app` with a `docs` command taking
    variadic `PATHS`, `--root` (override), and `-q/--quiet`.
  - [x] Resolve the root: `--root` if given, else the config value. Do not
    hard-code the default here — read it from `CONFIG_KEYS`.
  - [x] Format each violation as two lines: `path:line: CODE key: message`,
    then an indented `accepted: a | b | c` when the check has an accepted set.
  - [x] Write the summary (`N documents checked, M violations in K files`) to
    **stderr**, on every run including clean ones, unless `--quiet`. Silence
    must never be the only evidence the validator ran.
  - [x] Exit codes: 0 clean, 1 violations, 2 invocation error (missing root,
    missing named path, permission/IO fault). Catch the typed error from T6
    and map it; no traceback may escape the command.
  - [x] Success: `pyright` strict clean.

- [x] **T10. Wire the sub-app and test the CLI** (test-with)
  - [x] In `src/squadron/cli/app.py`, add
    `app.add_typer(validate_app, name="validate")` alongside the existing
    `add_typer` calls (lines 48-54).
  - [x] Create `tests/cli/test_validate_docs.py` using the existing typer
    `CliRunner` pattern from the other CLI tests.
  - [x] Assert each exit code path: clean run (0), a violating document (1),
    nonexistent `--root` (2), nonexistent named path (2), and a non-UTF-8
    `.md` under the root (1 with `FM008`, **not** a traceback).
  - [x] Assert the summary line appears on stderr for a clean run and is
    suppressed by `--quiet` while violations still print.
  - [x] Assert output contains the accepted-values line for an `FM005`.
  - [x] Success: all assertions pass; `sq validate docs --help` renders.

---

## Part 4 — Fix the Review Writer

- [x] **T11. Quote `location` in `_render_review`**
  - [x] In `src/squadron/review/persistence.py:222`, render the location as
    `f'    location: "{yaml_escape(sf.location)}"'`, matching how `summary` is
    already rendered on line 220.
  - [x] Add a one-line comment naming why: `location` and `summary` are the
    only fields in this hand-built block carrying model-authored free text.
  - [x] While in this function, replace the two remaining canonical-value
    literals with imports from `schema.py`: `"docType: review"` (line 187)
    becomes `DocType.REVIEW` and `"status: complete"` (line 195) becomes
    `DocumentStatus.COMPLETE`, each interpolated into the rendered line. These
    are the last two sites; T1 handles the other three.
  - [x] Do **not** migrate the rest of the block to `render_frontmatter_block`
    in this slice. It is the correct fix, several test modules assert on the
    exact rendered text, and it is recorded as Future Work in the design.
  - [x] Success: existing review-persistence tests pass, or their expected
    strings are updated only where the location line itself is asserted.

- [x] **T12. Regression test for the corruption class** (test-with)
  - [x] In `tests/review/test_persistence.py`, write a review whose structured
    finding has a location containing a colon-space (use a realistic value,
    e.g. a document anchor of the form seen in the five corrupted artifacts).
  - [x] Assert `read_frontmatter` on the written file returns a **mapping**,
    and that the round-tripped location equals the original string.
  - [x] Add the mirror-image test: a location containing an embedded double
    quote survives `yaml_escape` and still round-trips.
  - [x] Add a single-definition test: assert that no module in `src/` outside
    `documents/schema.py` contains a canonical status or docType value as a
    string literal. Implement it as a source grep over `src/**/*.py` driven by
    the enum members, so a value added to `schema.py` later is covered without
    editing the test. This is the mechanical form of the design's success
    criterion 6 — a criterion only a grep in a close-out checklist can enforce
    is one that silently rots.
  - [x] Success: all three pass; the first fails if T11 is reverted, and the
    third fails if any of the five known literal sites is left behind.

---

## Part 5 — Structural Hardening of the Frontmatter Writers

- [x] **T13. Validate `status` in `documents/frontmatter.py`**
  - [x] In `update_frontmatter` (line 94) and `render_frontmatter_block`
    (line 76), raise `FrontmatterError` when a **top-level** `status` key is
    present and its value is not a `DocumentStatus` (aliases accepted).
  - [x] Present-and-invalid only. Never required — machine artifacts
    legitimately omit `status`, and requiring it would break
    `gate_evidence_frontmatter` immediately.
  - [x] The error message must name the offending value and the accepted set.
  - [x] Import from `schema.py`; do not restate the values.
  - [x] Success: no existing call site changes behavior. Verified by
    construction — `render_frontmatter_block`'s two consumers carry `status`
    only inside nested `findingStatuses` entries (a `FindingStatus`, not a
    document status), and `update_frontmatter`'s only caller
    (`executor.py:269`) writes `revision_number`.

- [x] **T14. Tests for the hardening** (test-with)
  - [x] `update_frontmatter` with `{"status": "draft"}` raises
    `FrontmatterError` naming the accepted values.
  - [x] `update_frontmatter` with a valid status succeeds and preserves the
    body byte-for-byte.
  - [x] `render_frontmatter_block` with a nested `findingStatuses` entry
    carrying a finding-level `status` does **not** raise.
  - [x] `render_frontmatter_block` with no `status` key does not raise.
  - [x] Success: the whole existing suite is still green, with no assertion
    changed anywhere.

---

## Part 5A — Date Stamping on Squadron's Write Paths

Numbers are appended rather than renumbered, so every existing reference to
T1–T22 stays valid. This part must land after Part 5 (T23 modifies the
function T13 just changed) and before Part 9.

- [x] **T23. `update_frontmatter` stamps `dateUpdated`**
  - [x] Change the signature in `src/squadron/documents/frontmatter.py` to
    `update_frontmatter(path, updates, *, today: str) -> None` and write
    `dateUpdated: today` alongside the caller's keys.
  - [x] Skip the stamp when `updates` already contains `dateUpdated` — the
    caller is asserting a specific date and must win.
  - [x] The date is a required keyword, not a clock call inside the function.
    An ambient `date.today()` here would make the function untestable and put
    hidden state in a primitives module.
  - [x] Update the sole caller, `pipeline/executor.py:269`, to pass
    `today=date.today().strftime("%Y%m%d")`. This is the only in-place
    document edit squadron performs, and it currently leaves `dateUpdated`
    stale on every slice and task document it stamps `revision_number` into.
  - [x] Success: `pyright` strict clean; the existing revision-stamp tests
    pass with the new keyword supplied.

- [x] **T24. Tests for the stamp** (test-with)
  - [x] `update_frontmatter` on a fixture whose `dateUpdated` is older than
    `today` advances the field and leaves `dateCreated` untouched.
  - [x] `update_frontmatter` with `dateUpdated` supplied in `updates` writes
    the caller's value, not `today`.
  - [x] `update_frontmatter` on a document with **no** `dateCreated` still
    writes `dateUpdated` — the stamp is not conditional on the other field.
  - [x] The body of the document is preserved byte-for-byte in all three.
  - [x] Success: all four assertions pass; the first fails if T23 is reverted.

- [x] **T25. Emit `dateCreated` from the artifact writers**
  - [x] `gate_evidence_frontmatter`
    (`pipeline/actions/findings_addressed/evidence.py:99`) emits
    `dateCreated`. It currently emits no date at all. Take the date as a
    parameter on the same principle as T23 — no clock call inside the
    renderer.
  - [x] The devlog stub (`pipeline/actions/devlog.py:102-111`) emits
    `dateCreated` and `dateUpdated`, and gains `project` and `layer` to match
    what the root `DEVLOG.md` already carries. The action already computes
    `today` at line 58; no new clock is needed.
  - [x] The devlog **append** path stamps `dateUpdated` on every entry, since
    `DEVLOG.md` is the one document squadron rewrites repeatedly. Route the
    write through `update_frontmatter` rather than splicing the frontmatter
    lines by hand — `_insert_entry` operates on a raw `list[str]` and must not
    grow frontmatter knowledge.
  - [x] Leave `review` (`review/persistence.py:196-197`) and
    `review-resolution` (`resolution_artifact.py:106`) alone. Neither is ever
    rewritten; the first already emits both dates and `metrology/identity.py:234`
    reads its `dateUpdated`, the second correctly emits `dateCreated` only.
  - [x] Success: no `review-resolution` or `gate-evidence` file exists in the
    corpus today, so there is nothing to migrate and no format to stay
    compatible with. Verify by rendering one of each.

- [x] **T26. The writers' own output validates clean** (test-with)
  - [x] Render a `gate-evidence` document via `render_gate_evidence`, a
    `review-resolution` via `render_resolution`, and a devlog stub; write each
    to a tmp path inside a fixture document root and assert `validate_paths`
    returns **zero** violations for all three.
  - [x] Append a devlog entry to a fixture whose frontmatter carries an older
    `dateUpdated` and assert the field advances to today.
  - [x] Success: all four pass. This is the test that would have caught the
    real-world defect this part fixes — `DEVLOG.md` currently claims
    `dateUpdated: 20260803` while carrying a `20260804` entry, because the
    convention was maintained by hand and hands forget.

---

## Part 6 — One-Time Cleanup (its own commit)

- [x] **T15. Repair the five unparseable review artifacts**
  - [x] Run `uv run sq validate docs` and use its output as the work list.
    Do not work from a list transcribed here — re-derive it, then compare.
  - [x] For each `FM002` review artifact, quote the offending `location:`
    value. Change nothing else in the file; these are historical records.
  - [x] Verify each with `read_frontmatter` returning a mapping.
  - [x] Success: zero `FM002` violations remain.

- [x] **T16. Fix the remaining violations**
  - [x] Non-canonical `status` values: decide each by **reading the document**,
    not by a lookup table. `in-progress` and `not-started` are mechanical;
    `active`, `draft`, and `superseded` are judgment calls.
  - [x] Missing `status`: add the value the document's content supports.
  - [x] `docType: task-breakdown` and `docType: slice-tasks` → `tasks`. No
    squadron code reads either value; confirm with a grep before editing.
  - [x] Files with no frontmatter block: add a complete universal block.
    Archived documents are validated like any other — do not add an
    `archive/` exemption to buy off two files.
  - [x] Commit the cleanup **separately** from the feature work, with a
    message saying it is the one-time cleanup for slice 172.
  - [x] Success: `uv run sq validate docs` exits 0 over the full root.

---

## Part 7 — The Commit Gate

- [x] **T17. Create `.githooks/pre-commit`**
  - [x] Collect staged markdown:
    `git diff --cached --name-only --diff-filter=ACM -- '*.md'`. Exit 0
    immediately when the list is empty.
  - [x] Run `uv run --quiet sq validate docs -- <paths>` and propagate its
    exit code.
  - [x] On failure, print the `--no-verify` escape hatch explicitly. A gate
    with a hidden override is a gate people fight instead of use.
  - [x] If `sq` cannot be launched at all, exit **non-zero** with a message
    naming the likely cause. A hook that skips when its tool is missing
    enforces nothing while appearing to work.
  - [x] Handle paths with spaces correctly (quote, or use `-z` and read
    NUL-delimited).
  - [x] `chmod +x` and confirm the executable bit is committed
    (`git ls-files -s` shows mode `100755`).
  - [x] Success: the walkthrough in the design's step 5 behaves as written.

- [x] **T18. `sq doctor` reports whether the hook is installed**
  - [x] Add `check_git_hooks(hooks_path: str | None) -> CheckResult` to
    `cli/commands/doctor_checks.py`, following the existing `CheckResult` /
    `CheckStatus` shape (lines 42-56). Keep it **pure** — the module's
    docstring promises no subprocesses.
  - [x] In `cli/commands/doctor.py`, obtain the value with
    `run_git(["config", "--get", "core.hooksPath"], cwd=...)` from
    `review/git_utils.py:19` and pass it in. Reuse `run_git`; do not call
    `subprocess` directly.
  - [x] Report OK when the value is `.githooks`, a warning naming the exact
    `git config core.hooksPath .githooks` command otherwise. Not being in a
    git repo is not an error.
  - [x] Success: `sq doctor` shows the check in both states.

- [x] **T19. Tests and documentation for the gate** (test-with)
  - [x] Unit-test `check_git_hooks` for all three inputs: `.githooks`, some
    other value, and `None`.
  - [x] Document the one-time `git config core.hooksPath .githooks` install in
    the README (or contributing docs, wherever contributor setup lives) next
    to the existing `uv sync` instructions. The install step is part of the
    deliverable — a hook nobody installs is the failure mode being escaped.
  - [x] Walk the design's verification steps 5 and 6 by hand and confirm the
    commit is refused for a bad document and allowed for a touched `README.md`.
  - [x] Success: both walkthrough steps behave as documented; correct the
    walkthrough in the slice design if reality differs.

---

## Part 8 — CI Backstop (must land after Part 6)

- [x] **T20. Add the validator to CI**
  - [x] In `.github/workflows/ci.yml`, add `with: submodules: true` to the
    `actions/checkout` step of the `test` job. The drift test from T2 reads
    `file-naming-conventions.md` from the submodule and fails without it.
    `ecorkran/ai-project-guide` is public, so no token is required.
  - [x] Add `- run: uv run sq validate docs` to the `test` job, after the
    existing `ruff`/`pyright` steps and before `pytest`.
  - [x] Do not merge this before T15/T16 have landed, or `main` goes red
    between two commits of the same slice.
  - [x] Success: CI is green on the branch with both steps present.

---

## Part 9 — Close Out

- [x] **T21. Full verification pass**

  > ⚠️ **Ran and passed 20260804, against the pre-reopening code. Do not re-run as
  > written.** Three steps below invoke `sq validate docs`, which Part 10 (T28)
  > deletes, and one cross-checks it against `cf check` per D8a, which D10
  > supersedes. When Part 10 lands, the equivalent pass runs `cf validate
  > frontmatter` and the `sq validate docs` steps drop out entirely.

  - [x] Run every step of the design's Verification Walkthrough in order and
    confirm each behaves as written. Update the walkthrough where reality
    differs — it becomes the slice's demo script.
  - [x] `uv run ruff format`, then `uv run ruff check`, `uv run pyright`,
    `uv run pytest`, and `uv run sq validate docs` — all clean.
  - [x] Confirm no status or docType string literal exists in `src/` outside
    `documents/schema.py` (grep for the values).
  - [x] Confirm `sq validate docs` and `cf check` disagree on nothing: run
    `cf check --fix` on a clean tree, then `sq validate docs`, and expect
    exit 0. A `--fix` run that produces a document this gate rejects is the
    failure mode D8a exists to prevent.
  - [x] Success: all six commands exit 0.

- [ ] **T22. Documentation and slice close-out**

  > Reopened 20260804. The CHANGELOG/DEVLOG entries were written and stay, but they
  > describe `sq validate docs`, which Part 10 retires — they need rewriting once the
  > gate calls `cf validate frontmatter`. The completion marks are withdrawn: the
  > slice is not done.

  - [x] CHANGELOG: a short user-facing bullet for `sq validate docs` and the
    commit gate. Technical detail belongs in DEVLOG, not here.
  - [x] DEVLOG: implementation entry per the Session State Summary guidance.
  - [ ] Rewrite the CHANGELOG bullet once the gate calls `cf validate frontmatter`,
    since `sq validate docs` will no longer exist.
  - [ ] Mark slice 172 complete in this task file's frontmatter, in the slice
    design's frontmatter, and in entry 29 of
    `user/architecture/140-slices.pipeline-foundation.md`.
  - [ ] Success: the slice plan entry is checked off and the design's status
    reads `complete`.

---

## Part 10 — Retire the Parallel Validator, Install the Gate Everywhere

Added 20260804 when the slice was reopened. See **D10** and **D11** in the design.
Parts 1–3 built a Python validator and schema transcription that duplicate Context
Forge's `validateFrontmatter`; this part retires them and makes the gate reach every
squadron project rather than only this repo.

**Blocked on [context-forge#73](https://github.com/ecorkran/context-forge/issues/73)**
(exposes `cf validate frontmatter`), which is itself blocked on
[#72](https://github.com/ecorkran/context-forge/issues/72) (status-spelling fix —
until it lands, `validateFrontmatter` accepts the hyphenated values cf itself writes).

- [ ] **T27.** Point the pre-commit hook at `cf validate frontmatter`.
  - [ ] Replace the `uv run sq validate docs` invocation in `.githooks/pre-commit`.
  - [ ] Keep the staged-file collection as-is, including `--diff-filter=ACMR`.
  - [ ] `cf` missing on PATH is a hard non-zero exit with an actionable message —
    never a silent skip (same rule as D6, which currently covers `uv`).
  - [ ] Success: a staged document with a bad status is refused; a clean one commits.

- [ ] **T28.** Retire the parallel validator.
  - [ ] Delete `src/squadron/documents/validate.py` and
    `src/squadron/cli/commands/validate.py`; unwire `validate_app` from `cli/app.py`.
  - [ ] Delete `tests/documents/test_validate.py` and `test_validate_paths.py`.
  - [ ] Remove the `validate.docs_root` config key.
  - [ ] Success: `sq validate` is gone; the full suite passes.

- [ ] **T29.** Reduce `schema.py` to write-side values only.
  - [ ] Keep what squadron *emits*: the machine-artifact docTypes, and the values
    the review/devlog/evidence writers reference.
  - [ ] Drop what existed only to validate against.
  - [ ] Repoint the drift test: assert squadron agrees with **cf**, not the guide,
    since cf is now the schema squadron validates against. Still fails, never skips.
  - [ ] Success: the five write-side importers still build valid frontmatter.

- [ ] **T30.** Install the hook from `sq setup`.
  - [ ] Add a step to `cli/commands/setup_steps.py` that writes the hook and sets
    `core.hooksPath` — reuse the existing `StepKind` / installer registry.
  - [ ] A normal `sq setup` run installs it without the user asking.
  - [ ] Success: a fresh clone that runs `sq setup` has a working gate.

- [ ] **T31.** Add a `cf`-availability check to `sq doctor`.
  - [ ] Pure check function alongside `check_git_hooks`, per the existing shape.
  - [ ] WARN with a fix hint when `cf` is absent, since the gate depends on it.
  - [ ] Success: `sq doctor` reports the gate as unusable when `cf` is missing.

- [ ] **T32.** Register squadron's machine-artifact docTypes with cf.
  - [ ] `review-resolution`, `gate-evidence`, `devlog` — require `docType` and
    `dateCreated`; no `status`; do **not** require `dateUpdated` (a validator
    reading one file cannot know whether it was edited after creation).
  - [ ] Lands in context-forge under #73, tracked here because this slice is the
    consumer that needs them validated rather than silently passing through.
  - [ ] Success: a malformed gate-evidence artifact is caught by the gate.
