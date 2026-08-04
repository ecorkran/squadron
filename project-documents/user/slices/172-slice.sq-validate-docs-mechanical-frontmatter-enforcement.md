---
docType: slice-design
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: []
interfaces: []
dateCreated: 20260803
dateUpdated: 20260803
status: not_started
---

# Slice 172 — `sq validate docs`: Mechanical Frontmatter Enforcement

## Problem

`file-naming-conventions.md` defines the canonical document metadata — five status values, fifteen `docType` values, `YYYYMMDD` dates, five universal required fields — in prose, and enforces none of it. A convention that is only written down is a suggestion, and agents do not read suggestions reliably.

This is not speculative. A scan of the 409 markdown documents under `project-documents/user/` on `main` at `5ed9d01` found **24 violating files**:

| Class | Count | Instances |
|---|---|---|
| Non-canonical `status` | 6 | `active`, `draft` ×2, `in-progress`, `not-started`, `superseded` |
| Missing `status` | 3 | three `tasks` documents |
| Non-canonical `docType` | 11 | `task-breakdown` ×10, `slice-tasks` ×1 |
| No frontmatter block | 2 | `archive/112-slice.…`, `reference/analyze-codebase-prompt.md` |
| **Frontmatter present but unparseable** | 5 | five review artifacts |

The last row is the one that matters most, and it was invisible before this design. Those five files *look* fine — they open with a well-formed-looking block carrying `docType`, `verdict`, `aiModel`, `status`. They fail `yaml.safe_load` because a finding's `location:` value contains a colon-space:

```
location: Slice design: Implementation Details
```

`read_frontmatter` returns `None` for a YAML error exactly as it does for a file with no block at all, so nothing distinguished the two until a scan asked the question directly. The downstream consequence is a hard failure at a distance: `metrology/identity.py:180` raises `MetrologyTargetError` and `review/resolution_evidence.py:132` raises `ResolutionError` on any such file, so `sq metrology capture` and `sq review resolve` simply cannot process those five reviews.

The producer is squadron itself. `review/persistence.py:222` renders that line as an unquoted f-string:

```python
lines.append(f"    location: {sf.location}")          # unquoted — the defect
lines.append(f'    summary: "{yaml_escape(sf.summary)}"')  # quoted — the adjacent field
```

`summary` is quoted; `location` is not. Both carry model-authored free text.

## Approach

Enforcement does not have to happen inside squadron. It has to happen somewhere a bad document cannot get past, and `git commit` already is that boundary: LLM-independent, crossed by every workflow including agent-driven ones, and blind to which tool wrote the file. That observation is what makes this a 1/5 slice rather than the 3/5 pipeline-hook mechanism (slice 171) it replaces.

Five pieces, in dependency order. Pieces 4 and 5 are separable — droppable without harming 1–3.

1. **`sq validate docs [paths...]`** — the primitive: a deterministic, path-scoped frontmatter validator.
2. **A tracked git pre-commit hook** over staged `.md` files. This is the enforcement; piece 1 alone is another suggestion.
3. **CI backstop plus a one-time cleanup** of the 24 known violations, since `--no-verify` exists.
4. **Structural hardening** — `update_frontmatter` / `render_frontmatter_block` reject an invalid `status`, closing squadron's own writing paths.
5. **Fix the review writer** — quote `location`, and repair the five corrupted artifacts.

---

## Design Decisions

### D1 — Scope is a configured document root, not "every `.md`"

A repo-wide sweep is wrong. A survey of every markdown file in this repo found frontmatter-free files that are *correct* that way: `README.md`, `CLAUDE.md`, `docs/QUICKSTART.md`, all ten `commands/sq/*.md` slash-command files, and `.claude/agents/*.md`. None are process documents and none should grow `docType:`.

A document is in scope when it is a `.md` file under the configured document root. New config key:

| Key | Type | Default | Description |
|---|---|---|---|
| `validate.docs_root` | `str` | `project-documents/user` | Root under which markdown files are validated as process documents. |

`str` is already supported by `config/manager.py:_coerce_value`; no config-type work is needed.

Paths given on the command line are **filtered** against the root, not trusted. This is what lets the pre-commit hook pass the whole staged file list without knowing anything about document conventions — `README.md` in the list is skipped, `project-documents/user/slices/172-slice.….md` is validated. With no paths given, the command walks the root.

`project-documents/ai-project-guide/` is a git submodule (`.gitmodules`), so its files are never staged in this repo and its 118 markdown files are never this repo's problem.

**Exemption:** a file whose first 2 KB contains the `context-forge:managed` marker is skipped, per `file-naming-conventions.md:43`. No file under the current root carries it; the check exists so that IDE-generated output landing inside the root later does not produce a violation nobody can fix.

### D2 — Two document classes, because squadron writes documents too

`review-resolution` and `gate-evidence` artifacts are written into `project-documents/user/reviews/` (`review/resolution_artifact.py:193`, `pipeline/actions/findings_addressed/evidence.py:184`) — inside the validated root. Their frontmatter carries `docType` and, for resolutions, `project` and `dateCreated`. Neither carries `status` or `dateUpdated`, and neither should: they are immutable machine records of a completed event, not documents with a lifecycle.

So the validator recognizes two classes, both defined in one place:

- **Process documents** — the fifteen `docType` values in the spec. Full universal-field validation.
- **Machine artifacts** — squadron-emitted `docType` values (`review-resolution`, `gate-evidence`, `devlog`). Recognized as valid `docType`s; exempt from the universal-field and status checks. Date fields are still validated *when present*.

Without this, the gate would fail on squadron's own correct output the first time a pipeline wrote a resolution artifact — which is precisely how a gate teaches people to use `--no-verify`.

### D3 — Eight check classes, each with exactly one mechanical fix

The property that makes a commit gate survive contact is that every failure has one obvious fix. Anything requiring judgment goes in `cf check`, not here.

| Code | Check | Fix |
|---|---|---|
| `FM001` | A frontmatter block is present | Add one |
| `FM002` | The block parses as YAML | Quote the offending value (error names line/column) |
| `FM003` | The block parses to a mapping | Replace the scalar/list with key-value pairs |
| `FM004` | Universal required fields present (process docs) | Add the named field |
| `FM005` | `status` ∈ `DocumentStatus` | Replace with one of the listed values |
| `FM006` | `docType` ∈ `DocType` ∪ machine artifact types | Replace with one of the listed values |
| `FM007` | `dateCreated` / `dateUpdated` match `\d{8}` and are real dates | Rewrite as `YYYYMMDD` |
| `FM008` | The file is readable as UTF-8 | Re-save as UTF-8, or move it out of the document root |

`FM001` and `FM002` are distinct codes for what `read_frontmatter` currently collapses into one `None`. That distinction is the whole reason the five corrupted reviews went unnoticed, so the validator must not reuse `read_frontmatter`'s return-`None`-on-error path for diagnosis: it re-splits the document and calls `yaml.safe_load` itself so it can report the `yaml.YAMLError` position.

Explicitly **not** checked: per-`docType` schemas, cross-document reference integrity, index/filename agreement, body structure. All are `cf check`'s territory, all can require judgment, and each one added here raises the odds the gate gets bypassed.

**No `--fix` mode.** `in-progress` → `in_progress` is mechanical, but `draft`, `active`, and `superseded` have no unambiguous target, and a commit hook that silently rewrites staged documents is a worse failure mode than one that stops. The error message names the fix; a human or an agent applies it.

`completed` is accepted as a `status` alias for `complete` per `file-naming-conventions.md:61`. It occurs zero times in the current corpus; the alias exists because the spec says it does, and lives in the same enum module.

### D4 — Canonical values live in code, with a mechanical drift guard

Project rules forbid scattering comparison values; the spec states them in prose in a submodule. Squadron therefore defines them once as `StrEnum`s — and a test asserts the enums still match the spec:

```python
def test_status_enum_matches_spec():
    """Fails when file-naming-conventions.md and DocumentStatus disagree."""
```

The test parses the "Valid Status Values" section and the `docType` list out of `project-documents/ai-project-guide/file-naming-conventions.md` and compares to the enums. It **fails** — never skips — when the submodule is absent, with a message naming `git submodule update --init`. A skip here would be a silent fallback, and drift is the exact risk that killed slice 171's frontmatter consumer.

This requires `submodules: true` on the CI checkout step. `ecorkran/ai-project-guide` is public (unauthenticated GitHub API returns 200), so no token is needed.

Squadron owns the machine-artifact types; they are not in the spec and the drift test does not expect them there. Offering them to Context Forge for inclusion is a later conversation, not a dependency.

### D5 — Output contract

One line per violation, sorted by path then line:

```
project-documents/user/slices/201-slice.supervisor-component.md:9: FM005 status: 'not-started' is not a valid status
    accepted: not_started | in_progress | complete | deferred | deprecated
```

- **Line number** is the actual line of the offending key inside the block, found by scanning the raw block for the key (the block's start offset is known). Where there is no offending line — `FM001`, `FM004` — the reported line is the opening fence (or line 1 when there is no block). Never a fabricated number.
- **Exit code** `0` clean, `1` violations found, `2` invocation error. The split is by *who is wrong*: exit 2 means the command was called incorrectly and no useful validation happened — the configured root does not exist, or a named path does not exist. Everything about a document's content, including a `.md` file under the root that cannot be decoded as UTF-8 (`FM008`), is a violation on exit 1. A `.md` file that is unreadable for permission or I/O reasons is exit 2, since that is an environment fault, not a document defect. No condition is allowed to raise an uncaught traceback out of the command; if one does, the hook sees a nonzero exit and refuses the commit, which is the safe direction.
- **Summary line** to stderr: `N documents checked, M violations in K files`. Emitted even when clean, so "the hook ran" is observable rather than inferred from silence.
- No `--json`, no severity levels. One kind of finding, one exit code.

### D6 — The hook ships in the repo and the install is part of the deliverable

`.git/hooks/` is per-clone and untracked, so the hook ships as `.githooks/pre-commit` plus a one-time `git config core.hooksPath .githooks`. A hook nobody installs is exactly the failure mode being escaped, so the install step goes in `CONTRIBUTING`/`README` and in `sq doctor`'s checks, not in a footnote.

The hook:

1. collects staged `.md` paths (`git diff --cached --name-only --diff-filter=ACM -- '*.md'`), exits 0 if none;
2. runs `uv run --quiet sq validate docs -- <paths>`;
3. propagates the exit code and, on failure, prints the `--no-verify` escape hatch explicitly.

If `sq` cannot be launched at all, the hook exits **non-zero** with a message. A hook that skips when its tool is missing enforces nothing while appearing to work.

Installing the hook into *other* projects (`sq validate install-hook`, or a step in `sq setup`) is deliberately out of scope — recorded under Future Work.

### D7 — CI backstop, and a one-time cleanup so it can run full-tree

`--no-verify` exists, so CI runs `uv run sq validate docs` as a step in the existing `test` job. For that to be meaningful it must run over the whole root, which requires the 24 existing violations fixed first. They are mechanical and enumerated above; the cleanup is part of this slice, in a commit of its own.

Cleanup decisions worth stating rather than discovering during implementation:

- `active`, `draft`, `superseded` → the closest canonical value per document, decided by reading the document, not by a lookup table.
- `task-breakdown` (10) and `slice-tasks` (1) → `tasks`. No squadron code reads either value; the sole `docType` reference in source is the constant set from D2.
- `archive/112-slice.local-daemon-agent-brief.md` and `reference/analyze-codebase-prompt.md` → add frontmatter. Archived documents are validated like any other; exempting `archive/` would be a special case bought for two files.
- The five unparseable reviews → quote the `location:` values. Content-preserving, and it restores metadata to `sq metrology capture` and `sq review resolve`.

Ordering matters: CI must not gate on the validator until the cleanup commit has landed, or `main` is red between two commits of the same slice.

### D8 — Structural hardening on squadron's own write paths

`update_frontmatter` and `render_frontmatter_block` (`documents/frontmatter.py`) raise `FrontmatterError` when a **top-level** `status` key is present and not a `DocumentStatus`. Present-and-invalid only — never required, since machine artifacts legitimately omit it.

Verified safe against current callers: `render_frontmatter_block`'s two consumers (`resolution_frontmatter`, `gate_evidence_frontmatter`) carry `status` only inside nested `findingStatuses` entries, where it is a `FindingStatus`, not a document status. `update_frontmatter`'s only caller (`executor.py:269`) writes `revision_number`. No current call site changes behavior.

This closes squadron's door, not the agents'. Agents write markdown with the Write tool and never touch this module — that is what piece 2 is for.

### D9 — Quote `location` in the review writer

`persistence.py:222` gets the same treatment its neighbor already has:

```python
lines.append(f'    location: "{yaml_escape(sf.location)}"')
```

Scoped deliberately narrow. The larger correct fix is to render that whole block through `render_frontmatter_block`, as `gate_evidence_frontmatter` and `resolution_frontmatter` already do — its docstring says "serialized by yaml, never by f-string," and `_render_review` predates that rule. But several test modules assert on the exact rendered text, so the migration is its own unit of work; it is recorded under Future Work with this rationale.

Of the hand-rendered fields, `summary` and `location` are the only ones carrying model-authored free text; the rest are enums, kebab-case names, model ids, paths, and integers. Quoting `location` closes the observed hole. The validator covers the residual risk that some other field surprises us — which is the point of having a gate rather than an audit.

---

## Components

```
src/squadron/documents/
  schema.py      (new) DocumentStatus, DocType, MACHINE_ARTIFACT_DOC_TYPES,
                       REQUIRED_UNIVERSAL_FIELDS, STATUS_ALIASES
  validate.py    (new) Violation, ViolationCode, validate_document, validate_paths
  frontmatter.py (edit) status validation in update_frontmatter /
                        render_frontmatter_block

src/squadron/cli/commands/
  validate.py    (new) validate_app typer sub-app; `docs` subcommand

src/squadron/cli/app.py       (edit) app.add_typer(validate_app, name="validate")
src/squadron/config/keys.py   (edit) validate.docs_root
src/squadron/review/persistence.py (edit) quote location
.githooks/pre-commit          (new)
.github/workflows/ci.yml      (edit) submodules: true; validate step
```

`schema.py` **defines** the machine-artifact docTypes; `review/` and `pipeline/` import them from it. The reverse — `documents/` sourcing the values from the modules that emit them — inverts the layering, and once `frontmatter.py` imports `schema.py` for the status check (D8) it is also a literal import cycle: `documents.frontmatter` → `documents.schema` → `review.resolution_artifact` → `documents.frontmatter`.

`validate.py` is pure — it takes paths and returns `list[Violation]`, performs no printing and no `sys.exit`. The CLI command formats and sets the exit code. That keeps the validator testable without a runner and lets a future MCP tool or `sq doctor` check call it directly.

## Data Flow

```
git commit
  └─ .githooks/pre-commit
       ├─ git diff --cached --name-only --diff-filter=ACM -- '*.md'
       └─ sq validate docs -- <staged paths>
            └─ cli/commands/validate.py
                 └─ documents/validate.validate_paths(paths, root)
                      ├─ filter: under root? .md? not context-forge:managed?
                      ├─ split + yaml.safe_load           → FM001 FM002 FM003
                      ├─ classify by docType              → FM006
                      ├─ process docs: required fields    → FM004
                      │                status ∈ enum      → FM005
                      └─ dates present → YYYYMMDD         → FM007
                 └─ format lines, summary to stderr, exit 0|1|2
```

CI runs the same command with no paths — `validate_paths` walks the root instead of filtering a list. One code path, two entry points.

## CLI Specification

```
sq validate docs [PATHS]...

  Validate process-document frontmatter against the canonical schema.

  With no PATHS, walks the configured document root. With PATHS, validates
  only those that fall under the root — others are silently skipped, so a
  caller may pass an unfiltered file list.

Options:
  --root PATH   Override validate.docs_root for this invocation.
  -q, --quiet   Suppress the summary line; violations still print.

Exit: 0 clean | 1 violations | 2 usage error
```

## Cross-Slice Dependencies and Interfaces

- **Depends on:** nothing new. `read_frontmatter` (slice 149-era `documents/frontmatter.py`) exists; the config manager exists.
- **Relationship to 171 (deferred):** 171 generalizes two hardcoded executor post-action checks and revives only when a consumer must run *inside* a pipeline and *block* it. This slice does not create one — a commit gate is deliberately outside the pipeline, and it catches documents 171 could not: those written when no pipeline was running.
- **Supersedes two placeholder modules in the parent architecture.** `140-arch.pipeline-foundation.md` reserved `documents/status.py` (DocumentStatus) and `documents/paths.py` (`USER_DOCS_ROOT`), both marked "171 — DEFERRED." This slice builds the canonical status enum in `documents/schema.py` alongside `DocType` and the machine-artifact set, and replaces `USER_DOCS_ROOT` with the `validate.docs_root` config key — a constant is the wrong shape for a value that must differ per project. The architecture is updated to name the real modules rather than leaving a revived 171 to discover a second `DocumentStatus`. If 171 is ever revived, it consumes `schema.py`; it does not define its own.
- **Offered to, not depended on:** Context Forge owns `file-naming-conventions.md` and ships `cf check`. If it later wants this check class, `validate_paths` is the callable to lift. Not a dependency in either direction.
- **`sq doctor`:** gains one check — is `core.hooksPath` set to `.githooks`? Additive, no interface change.

## Success Criteria

1. `sq validate docs` exists as a typer sub-app command wired into `app.py`.
2. `validate.docs_root` is a defined config key with default `project-documents/user`; `--root` overrides it per invocation.
3. Paths passed on the command line that fall outside the root are skipped, not flagged — verified by passing `README.md` and observing exit 0.
4. All eight check classes (`FM001`–`FM008`) are implemented, each with a unit test using a real-format fixture.
5. `FM001` (no block) and `FM002` (block present, YAML invalid) are reported as distinct codes; a fixture reproducing `location: Slice design: Implementation Details` yields `FM002` with the YAML error position.
6. `DocumentStatus`, `DocType`, and the machine-artifact docTypes are defined in exactly one module (`documents/schema.py`); the five existing literal sites — `review/persistence.py:187,195`, `review/resolution_artifact.py:25`, `pipeline/actions/findings_addressed/evidence.py:26`, `pipeline/actions/devlog.py:104` — import from it instead. Enforced by a test that greps `src/**/*.py` for the enum members, not by a checklist item.
7. A drift test parses `file-naming-conventions.md` and fails when its values disagree with the enums; it fails (not skips) when the submodule is absent, naming the fix.
8. Machine-artifact docTypes (`review-resolution`, `gate-evidence`, `devlog`) validate clean — an actual `render_gate_evidence` and `render_resolution` output passes the validator in a test.
9. Violation output carries `path:line`, code, offending key, actual value, and accepted values. Line numbers are real or the fence line; never invented.
10. Exit codes are 0 / 1 / 2 as specified, asserted by CLI tests covering at minimum: clean run, violation, nonexistent `--root`, nonexistent named path, and a non-UTF-8 `.md` under the root (which is exit 1 / `FM008`, not a traceback).
11. A summary line is written to stderr on every run, including clean runs.
12. `.githooks/pre-commit` is tracked, executable, validates only staged `.md` files, exits 0 when none are staged, propagates the validator's exit code, and exits non-zero (never 0) if `sq` cannot be launched.
13. Hook installation (`git config core.hooksPath .githooks`) is documented in the README/contributing docs, and `sq doctor` reports whether it is set.
14. All 24 existing violations under `project-documents/user/` are fixed, in a commit separate from the feature work.
15. `uv run sq validate docs` over the full root exits 0 on `main` after cleanup.
16. CI runs the validator in the `test` job, with `submodules: true` on checkout, added only after the cleanup commit.
17. `update_frontmatter` and `render_frontmatter_block` raise `FrontmatterError` when a top-level `status` is present and invalid; absent `status` is accepted.
18. No existing test's assertions change as a result of criterion 17 — the current call sites are unaffected by construction.
19. `persistence.py` quotes `location` via `yaml_escape`; a regression test writes a review whose finding location contains `: ` and asserts the resulting file's frontmatter round-trips through `read_frontmatter`.
20. The five corrupted review artifacts parse after repair, verified by `read_frontmatter` returning a mapping for each.

## Verification Walkthrough

**1. The validator catches what prose could not.**

```bash
printf -- '---\ndocType: notes\nproject: squadron\ndateCreated: 20260803\ndateUpdated: 20260803\nstatus: draft\n---\n\n# probe\n' \
  > project-documents/user/notes/zz-probe.md
uv run sq validate docs project-documents/user/notes/zz-probe.md
```

Expect exit 1 and a line naming the file, the line number of `status:`, `FM005`, `'draft'`, and the five accepted values. Leave the file in place — step 5 reuses it.

**2. It skips what is not a process document.**

```bash
uv run sq validate docs README.md CLAUDE.md docs/QUICKSTART.md
```

Expect exit 0 and `0 documents checked` — these are outside the root.

**3. It catches the corruption class that was invisible.**

```bash
uv run sq validate docs project-documents/user/reviews/157-review.tasks.precompact-hook-for-interactive-claude-code.md
```

Before the cleanup commit: exit 1, `FM002`, with the YAML error position (line 50 for this file). After: exit 0.

**4. Squadron's own machine artifacts pass.**

```bash
uv run pytest tests/documents/test_validate.py -k machine_artifact -q
```

The test renders real `gate-evidence` and `review-resolution` frontmatter and validates it. This is the check that a gate does not fire on correct output.

**5. The gate actually gates.**

```bash
git config core.hooksPath .githooks
git add project-documents/user/notes/zz-probe.md   # the step-1 file, status: draft
git commit -m "test: gate probe"
```

Expect the commit to be **refused**, with the `FM005` line and the `--no-verify` note. Then:

```bash
sed -i '' 's/^status: draft/status: not_started/' project-documents/user/notes/zz-probe.md
git add project-documents/user/notes/zz-probe.md
git commit -m "test: gate probe"   # succeeds
git reset --hard HEAD~1 && rm -f project-documents/user/notes/zz-probe.md
```

**6. The hook does not fire on non-documents.**

```bash
touch README.md && git add README.md && git commit -m "test: readme touch"
```

Expect success — staged `.md`, outside the root, skipped. Then `git reset --hard HEAD~1`.

**7. Squadron can no longer write a bad status.**

```bash
uv run python -c "
from pathlib import Path
from squadron.documents.frontmatter import update_frontmatter
p = Path('/tmp/probe.md'); p.write_text('---\ndocType: notes\n---\n\nbody\n')
update_frontmatter(p, {'status': 'draft'})
"
```

Expect `FrontmatterError` naming the accepted values.

**8. The review writer no longer produces unparseable frontmatter.**

```bash
uv run pytest tests/review/test_persistence.py -k location -q
```

**9. Full-tree clean, and CI would agree.**

```bash
uv run sq validate docs && echo "clean" && uv run ruff check && uv run pyright && uv run pytest -q
```

## Risks

- **Gate fatigue.** The one real risk. Mitigated by D3's narrowness (seven mechanical checks, no judgment calls), by D1's scoping (the gate is silent on non-documents), and by D2 (it never fires on squadron's own output). If it starts refusing commits for reasons a contributor cannot fix in fifteen seconds, the design has drifted.
- **Spec drift.** Handled by D4's drift test rather than by hoping.
- **Cleanup ordering.** CI turns red if the validator step lands before the cleanup commit. Sequenced explicitly in D7 and criterion 16.

## Future Work

- **`sq validate install-hook`** — install the hook into an arbitrary project, or fold it into `sq setup`. This slice ships the hook for squadron's own repo; every other project using this process has the same problem.
- **Render review frontmatter through `render_frontmatter_block`** — retire the hand-built f-string block in `_render_review` (`review/persistence.py:185-224`), the way gate evidence and resolution artifacts already do. Blocked only by test coupling to the exact rendered text; D9 patches the observed hole in the meantime.
- **Offer the check class to Context Forge** as a second consumer, since it owns the naming spec.

**Effort:** 1/5
