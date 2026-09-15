---
docType: slice-design
slice: pr-keyed-review-persistence
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [382, 916, 917]
interfaces: [384, 385, 386]
dateCreated: 20260915
dateUpdated: 20260915
status: in_progress
---

# Slice Design: PR-Keyed Review Persistence

## Overview

382 left `sq review pr` producing a real review that nothing keeps: the command runs, displays a
verdict, and reports that persistence is not available. This slice gives it a home.

The obvious version of that — "add a PR branch to the save path" — would make a fourth naming
shape beside the three that exist. Persistence is generic at the top (`_resolve_save_outcome`
takes a `SaveTargetT`) and hardwired to `SliceInfo` everywhere beneath, so the two callers that
are *not* about a slice already work around it: the arch review fabricates a `SliceInfo` from an
initiative index, and the pipeline action bypasses `save_review_result` entirely for a
lower-level call keyed by step name and index. Both are the same unmet need, solved twice,
differently.

So the slice's real work is a **save-target contract**: a small structural protocol that answers
the three questions persistence actually asks — what is the filename stem, what target-specific
frontmatter does this carry, and which reviews directory does it go in. A slice target, an arch
target, a step target, and a PR target all satisfy it. Three shapes become one, and the PR target
is then an ordinary fourth implementation rather than a special case.

The rest is what a PR review needs that a slice review does not: a filename with no numeric
index, a location for repositories that have no `project-documents/`, and provenance for which
rules the reviewer was actually given.

## Value

**User value.** PR reviews are kept, archived, digested, and resolved like every other review —
including in repositories squadron never planned, which is the enterprise case the initiative
exists to serve. Without this slice `sq review pr` is a terminal command whose output dies with
the scrollback.

**Developer value.** Persistence stops fabricating slice records for reviews that are not about
slices. The next non-slice review target — and 384 and 385 both consume one — implements a
protocol instead of inventing a fourth workaround.

## Technical Scope

### Included

- `src/squadron/review/save_target.py`: the `SaveTarget` protocol and the slice/arch/step
  implementations (D1).
- `src/squadron/review/persistence.py`: `save_review_result` and `format_review_markdown` take a
  target rather than a `SliceInfo`; frontmatter rendering splits into common and target-specific
  parts (D2).
- `src/squadron/cli/commands/review.py`: the arch review drops `_arch_slice_info`; slice and arch
  paths pass targets.
- `src/squadron/pipeline/actions/review.py`: the step-keyed branch migrates onto the contract,
  deleting its separate `format_review_markdown` + `save_review_file` path.
- `src/squadron/cli/commands/review_pr.py`: the PR target is built here (D3) and the real save
  replaces 382's `save=lambda _target: False` stub.
- `src/squadron/review/rules.py`: `resolve_rules_dir` reports which source it chose (D6).
- `src/squadron/config/keys.py`: `review.external_reviews_dir` (D5).
- `project-documents/ai-project-guide/file-naming-conventions.md`: the PR review filename form.

### Excluded

- Posting (384), PR creation (385), slash-command parity and documentation (386).
- Any change to what a *slice* review's artifact contains **through the migration itself**. Slice
  and arch artifacts are byte-identical across the migration, asserted against untouched fixtures;
  that is the migration's acceptance test (D2). The two additive keys this slice does introduce —
  `rulesSource` and `targetKind` — land afterwards as one deliberate, separately-reviewed change,
  never inside the migration's diff.
- Reading PR reviews back for resolution or metrology. Those consumers are shown not to match
  (D4); teaching them to *act* on PR reviews is not in scope and nothing needs it yet.
- Any context-forge schema change. Probed at design time and not required — see D7.

## Scope corrections against the plan entry

| Plan text | Finding at design | Disposition |
|---|---|---|
| "with any required context-forge schema change landed first as a named dependency" | Probed against the registered project root rather than assumed. cf's `review` schema requires only `docType`, `project`, `status`, `dateCreated`, `dateUpdated` — no `slice` — and unknown keys are never rejected (validation checks required-field presence and enumerated values only). A PR-shaped fixture with a non-numeric name, no `slice`, and a nested `pr:` mapping validated clean. | **No cf dependency.** The slice's largest named risk retires before implementation. Recorded as D7 with the probe method, because the probe is easy to run wrong. |
| "the `review.external_reviews_dir` config key with its default under squadron's per-user data directory keyed by host, owner, and repository" | Correct, but the plan does not say what happens when a repository *has* `project-documents/` and the operator also set the key. Precedence has to be stated or two reviews of one PR land in two places depending on cwd. | Explicit precedence chain in D5: `--reviews-dir` > project reviews dir when one exists > `review.external_reviews_dir` > built-in per-user default. The chosen location **and its source** are printed. |
| "the non-numeric PR filename prefix, with `{index}-review.*` consumers shown never to match" | True, and stronger than the plan states: `locate_review` and metrology's capture both build their glob from a caller-supplied *integer*, so a non-numeric prefix cannot match by construction, not merely by convention. But `PullRequestRecord.key` is `host/owner/repo#number` — containing `/` and `#`, which a filename cannot carry — while its own docstring claims it is "filesystem-safe". | The stem flattens the key (D3). 382 already flattens it for worktree directories in `codehost/worktree.py::_flatten_key`; this slice promotes that helper to the record itself rather than writing the second copy, and corrects the misleading docstring. |
| "the rules-source provenance field as one additive optional frontmatter key" | The value does not exist to be recorded. `resolve_rules_dir` returns a bare `Path | None` and discards which of its five branches produced it, so "project, user, or template" cannot be read off the result — `~/.config/squadron/rules` and a project `rules/` are both just a `Path`. | A signature change, not a field addition: `resolve_rules_dir` returns the path **and** its source. Named D6, and it is the one change in this slice that touches a function every review path calls. |
| "a target yields the filename stem, the target-specific frontmatter fields, and **the reviews directory**" (parent architecture, "Persistence takes a target, not a slice") | The third part does not belong on the target. The directory depends on the *invocation* — `--reviews-dir`, whether the repository has a `project-documents/` — not on what is being reviewed, so every implementation would carry a value it does not choose and cannot answer. `save_review_result` already takes `reviews_dir` as a parameter today for exactly this reason. | Protocol is `filename_stem`, `frontmatter_fields`, `source_document`; the directory is resolved by the caller and passed in (D1, D5). `source_document` is an addition the architecture does not name — it is target-specific frontmatter that happens to have its own parameter already. **A deliberate deviation from the parent's literal wording**, recorded here rather than left inside D1's prose; raised as F005 at slice review. |
| "the pipeline action's step-keyed save migrated onto the same contract" | The step path does not merely name files differently — it calls `format_review_markdown` and `save_review_file` directly, so it is the only save path that never runs `archive_existing_review`'s refuse-on-failed-archive guard and silently returns `None` on write failure. | Migrating it onto the contract closes that gap as a side effect. Called out in D2 because it is a behavior change on an existing path, not pure refactoring, and it needs its own test. |

Effort stays 3/5.

## Dependencies

### Prerequisites

- **382** — `sq review pr`, the `ResolvedPullRequest`/`PullRequestRecord` types, the two-root
  split (`convention_root`), and the `_resolve_save_outcome` call site this slice fills in.
- **916, 917** — both `status: complete` and present on `squadron-pr` (verified at design time).
  917 owns the artifact-integrity seams (run digest, degraded-parse rendering, provider-failure
  artifacts) that this slice's frontmatter split must not disturb.

### Interfaces Required

- `PullRequestRecord` for the target's identity. The review package imports the record type only,
  never the adapter — the architecture's one-way rule, preserved by building the PR target in the
  CLI layer (D3).
- `cf`'s `review` frontmatter schema, as a validation target rather than a code dependency (D7).

## Architecture

### Component Structure

```
src/squadron/review/save_target.py     SaveTarget protocol; SliceTarget, ArchTarget, StepTarget
src/squadron/review/persistence.py     save_review_result / format_review_markdown take a target
src/squadron/cli/commands/review_pr.py PrTarget construction (record → target) and the save call
src/squadron/review/rules.py           resolve_rules_dir reports its source
src/squadron/config/keys.py            review.external_reviews_dir
```

Dependency direction is unchanged. `save_target.py` sits in `review/` and imports nothing from
`codehost`; `PrTarget` is built in the CLI layer, which already imports both packages. This is
the architecture's stated arrangement ("the conversion from PR record to save target lives in the
CLI layer"), and it is what keeps the protocol structural rather than a union of known types.

### Data Flow: saving a PR review

```
ReviewResult + ResolvedPullRequest
             │
   PrTarget(record, rules_source)          ← built in the CLI layer (D3)
             │
   resolve_reviews_dir(target, cwd, --reviews-dir)   ← D5 precedence, source printed
             │
   save_review_result(result, review_type, target, reviews_dir=...)
             │
   ┌─────────┴──────────┐
   │                    │
 stem from target   frontmatter = common keys + target.frontmatter_fields()
   │                    │
   └─────────┬──────────┘
             │
   archive_existing_review  ← unchanged; refuses to overwrite what it cannot archive
             │
   <reviews-dir>/github.com-ecorkran-squadron-42-review.code.md
```

## Technical Decisions

### D1 — The save-target contract is a structural Protocol with three questions

```python
class SaveTarget(Protocol):
    def filename_stem(self, review_type: str) -> str: ...
    def frontmatter_fields(self) -> dict[str, object]: ...
    def source_document(self) -> str | None: ...
```

The reviews *directory* is deliberately **not** a method: it depends on the invocation
(`--reviews-dir`, the project's presence) rather than on the target, so it is resolved by the
caller and passed in, as `save_review_result` already accepts it today. Putting it on the target
would make every implementation carry a directory it does not choose.

#### Corrections made during implementation

**The protocol has four methods, not three.** `reviewed_sha()` was added. D3 requires a PR
review's sha to come from the record rather than `resolve_reviewed_sha(".")`, and the only way to
express that through one save path is to let the target answer it — slice, arch and step targets
resolve from git exactly as before, `PrTarget` returns the record's head sha. Stating the protocol
as three methods and then special-casing the sha at the call site would have reintroduced the
"solved twice, differently" shape this contract exists to remove.

**The protocol is declared twice, deliberately.** `save_target.py` imports `SliceInfo` and
`resolve_reviewed_sha` from `persistence.py`, so `persistence.py` cannot import the protocol type
back without closing a cycle. It therefore declares its own structural copy
(`SaveTargetProtocol`). Moving `SliceInfo` to break the cycle was rejected: it has five consumers
and this slice is explicitly not a `SliceInfo` refactor. Structural typing is what makes the
duplication safe — implementations satisfy both by shape — and
`tests/review/test_save_target.py` asserts the two declarations name the same members, so a method
added to one and not the other fails a test rather than drifting silently.

**`project_name` is a caller-supplied parameter, not a protocol method.** `project:` is a key
*every* review carries, so by D2's own split it is common rather than target-specific. It is
passed to `format_review_markdown` alongside `model` and `source_document`, which are already
resolved-by-caller for the same reason. A PR review in a repository squadron never planned has no
Context Forge project to ask, and writes `project: unknown` — the same degradation the pipeline
step path already produces, and the behaviour `ac01838c` established when it stopped the value
being hardcoded.

**The body heading is parameterised.** Every review's body opens `# Review: {type} — slice {N}`.
A PR has no slice index, and `slice 0` would be a fabricated identifier — the same objection D3
raises against deriving a filename from a PR title, and one `format_provider_failure_markdown`
already acts on ("No '— slice 0' for a run with no slice: a fabricated index reads as real").
`format_review_markdown` takes a `heading_label`: existing paths pass `slice {index}` and their
bytes are unchanged, `PrTarget` passes `PR #42`. This is a new artifact shape rather than a
migration change, and 384 renders it into a PR comment.

**`_arch_slice_info` survives, narrowed.** The save path no longer calls it, but
`save_provider_failure` still takes a `SliceInfo` and migrating that path is not in scope. The
fabrication remains for that one consumer, with its project-name resolution extracted to
`_cf_project_name()` so the two paths share it rather than growing a second copy.

A `Protocol` rather than a base class or a union: persistence already uses `Protocol` for its `cf`
client, the implementations live in three different packages, and a union would have to name
`PrTarget` inside `review/`, which is the import the architecture forbids.

Four implementations: `SliceTarget` (wraps the existing `SliceInfo`), `ArchTarget` (initiative
index and arch document — replacing `_arch_slice_info`'s fabrication), `StepTarget` (pipeline step
name and index), and `PrTarget` (D3).

`SliceInfo` itself stays. It carries design/task/arch file paths that template inputs and the
resolve path read for reasons unrelated to saving; `SliceTarget` wraps it rather than replacing
it, so this slice does not become a `SliceInfo` refactor.

### D2 — Frontmatter splits into common and target-specific, and the migration's test is byte-identity

`_review_frontmatter_lines` currently takes `slice_name` and emits `slice:` unconditionally. It
splits: the common keys (`docType`, `layer`, `reviewType`, `project`, `verdict`, `sourceDocument`,
`aiModel`, `status`, dates, and the existing optional keys) stay where they are, and the
target-specific keys come from `frontmatter_fields()`. `SliceTarget` returns `{"slice": ...}`;
`PrTarget` returns `{"pr": {...}}` and no slice key.

Rendering stays line-based rather than moving to `yaml.safe_dump`. The existing renderer emits
`findings:` as hand-built lines with deliberate quoting, and 917's artifact-integrity work depends
on that output; switching serializers would rewrite every existing artifact's formatting and put
this slice's diff through code it has no reason to touch. `PrTarget` emits its nested mapping as
indented lines the same way `criteria:` already does.

**The migration's acceptance test is byte-identity.** Slice reviews, arch reviews, and pipeline
step reviews must produce files identical to what they produce today, asserted against fixtures
captured *before* the change on all three paths. Any diff is a regression, not an improvement —
this slice is not the place to fix artifact formatting.

**Byte-identity is verified before either new frontmatter key is added.** This slice introduces
two additive keys that every target writes — `rulesSource` (D6) and `targetKind` (D4) — and both
necessarily change the bytes of slice, arch, and step artifacts. Adding them during the migration
would make byte-identity unverifiable: a check whose fixtures may be updated on intent cannot
distinguish an intended key from unintended drift, which is the only thing it exists to catch.

So the migration completes and proves itself against untouched fixtures *first*. The two keys
land afterwards, together, as a single deliberate change with one fixture update covering both —
reviewed as an intentional artifact change rather than absorbed into the migration's diff. The
fixtures are regenerated once, at that point, and the diff is confirmed to contain exactly the
two new keys and nothing else. Neither key's scope narrows: both are still written on every
review, as D4 and D6 specify.

**One deliberate behavior change.** The pipeline step path currently calls `format_review_markdown`
+ `save_review_file` directly, which returns `None` on failure and never runs the
refuse-on-failed-archive guard that `save_review_result` enforces. Migrating it onto the contract
routes it through that guard, so a step review can now refuse to overwrite an unarchivable file.
That is a fix, but it is a change to an existing path: it gets its own test, and the action's
existing "persistence failure never fails the action" boundary (its `try/except` around the save)
is preserved so the new refusal is logged and non-fatal exactly as a write failure is today.

**The migration's real blast radius is `mock.patch`, not the save logic.** Recorded because it is
counter-intuitive and the remaining tasks repeat the pattern. `mock.patch` validates its target
attribute at *setup* time and raises `AttributeError` when the name is absent, so removing
`format_review_markdown` and `save_review_file` from the pipeline action's module namespace broke
**44 tests across four files** — `test_review_action.py`, `test_review_action_integration.py`,
`test_judge_cycle.py`, `test_review_empty_scope.py` — including many with nothing to do with
persistence (model resolution, tool threading, rules wiring). Every one died before its body ran.

Two consequences worth carrying into Task 7, which deletes 382's stub the same way:

- A large, alarming failure count after this kind of change is usually *one* missing name, not one
  problem per test. Read the first traceback before concluding anything about scope.
- The reverse case is the dangerous one. A patch whose target still exists but is no longer called
  fails *silently* — it intercepts nothing, the real function runs, and a test asserting "no file
  was written" still passes. Thirteen sites here stubbed `save_review_file` with
  `return_value=None`, which was its failure signal; they were repointed at `save_review_result`
  and given a `Path`, since that function raises rather than returning `None` and a `None` stub
  would have been quietly dishonest.

### D3 — The PR target, its filename, and the key that is not filesystem-safe

`PrTarget(record: PullRequestRecord, rules_source: RulesSource)`, constructed in
`review_pr.py`.

**Filename stem:** `{flattened-key}-review.{review_type}`, e.g.
`github.com-ecorkran-squadron-42-review.code.md`. No slice name segment — a PR has no slice name,
and inventing one from the PR title would be a fabricated identifier that changes when someone
edits the title.

`PullRequestRecord.key` is `f"{host}/{owner}/{repository}#{number}"` — it contains `/` and `#`
and cannot be a filename, despite a docstring claiming it is "filesystem-safe" and pointing at
this slice. 382 already flattens it in `codehost/worktree.py::_flatten_key` for worktree
directory names. This slice promotes that helper to a `PullRequestRecord.path_key` property, so
the worktree name and the review filename derive from one definition rather than two copies that
can drift, and corrects the docstring to say which property is safe for paths.

**Frontmatter:** `sourceDocument` is the PR URL; a `pr:` mapping carries host, owner, repository,
number, and url; `reviewedSha` is `record.head_sha`. That last point is the one the architecture
is emphatic about and the one most easily got wrong: `save_review_result` currently stamps
`resolve_reviewed_sha(".")`, which on this path is the *operator's* HEAD — a different tree from
the one reviewed. The PR path must take the sha from the record. Mechanically this means
`reviewed_sha` comes from the target rather than being resolved inside `save_review_result`:
slice and arch targets resolve it from git as they do now, `PrTarget` returns the record's head
sha. A test asserts a PR review's `reviewedSha` differs from the operator's HEAD when the two
differ.

### D4 — Existing consumers are shown not to match, and the `*-review.*` consumers learn target kind

Two glob families read the reviews directory.

**`{index}-review.*` consumers cannot match, by construction.** `resolution_evidence.locate_review`
builds `f"{index}-review.{type}.*.md"` from an `int`, and `metrology/capture` builds
`f"{index}-review.*"` after an explicit `target.isdigit()` check. A stem beginning
`github.com-...` cannot match either. This needs a regression test, not code: a PR review of PR 42
sitting beside a slice review of slice 42, asserting `sq review resolve 42` and metrology capture
for index 42 both select the slice review.

**`*-review.*` consumers do match and must classify.** `metrology/discovery.discover_judge_results`
and the archive/digest paths enumerate every review file. Discovery already filters on
`reviewType` resolving to a registered judge template, so a PR code review is dropped by existing
logic — but by a filter that happens to exclude it rather than one that knows what it is. Per the
plan, these consumers read the target kind explicitly: a `targetKind` frontmatter key
(`slice` | `arch` | `step` | `pr`) written by every target through the contract, with absence
meaning `slice` so existing artifacts keep parsing. Classification reads frontmatter, never the
filename — the same rule `capture._read_review_type` already follows, and the reason it is
reliable where filename parsing is not.

Like `rulesSource`, this key is written **after** the migration's byte-identity verification, and
the two land together as one deliberate artifact change (D2, D6). Absence-means-`slice` is what
keeps every artifact written before that point readable, so the ordering costs nothing.

Archiving, digest, and 917's integrity rendering are target-agnostic already: they operate on
`ReviewResult` and on paths, never on slice identity. They get a PR-artifact test, not changes.

### D5 — Where a PR review lands, in precedence order

```
1. --reviews-dir <path>                          (new flag, this invocation only)
2. <checkout>/project-documents/user/reviews/     when that directory exists
3. review.external_reviews_dir                    (config key, new)
4. ~/.config/squadron/reviews/<host>/<owner>/<repo>/   (built-in default)
```

A planned repository keeps its reviews with the project, which is what makes archiving, digest,
and `cf` discovery work unchanged. An unplanned repository never gets a directory invented inside
it — rule 2 requires the directory to *already* exist, so squadron does not create
`project-documents/` in someone else's repository as a side effect of reviewing a PR.

`review.external_reviews_dir` follows the existing `metrology.store_dir` shape (`type_=str`,
`default=None`). The built-in default is under `~/.config/squadron/`, the per-user directory
squadron already owns — deliberately *not* `data_dir()`, which resolves to the installed
package's read-only `squadron/data/`; 382's D3 recorded that same correction for worktrees and
the same reasoning applies here.

The chosen directory **and which rule chose it** are printed with the result. This is the
architecture's "explicit degradation": an operator who does not know where their review went has
been failed regardless of whether the file was written.

`--reviews-dir` is distinct from the existing `--output-path`, which is a JSON dump destination
and keeps that meaning. The help text for both says so, because the two are easy to confuse.

**Failure modes of the write path, enumerated.** This is a new I/O path, so the architecture's
"failure modes are enumerated and observable" principle applies to it directly rather than by
inheritance. Precedence selects a directory *once*; a failure of the selected directory is never
a fall-through to the next rule, which would silently write somewhere the operator did not ask
for — the precise silent fallback the project rules forbid.

| Mode | Behavior |
|---|---|
| Selected directory does not exist (rules 1, 3, 4) | Created, `parents=True`. `--reviews-dir /nonexistent` is created, not refused — matching `metrology`'s store dir, not `--rules-dir`'s silent degrade-to-`None`. |
| Directory cannot be created (permissions, read-only parent, path is a file) | `OSError` from the existing `mkdir` outside the try in `save_review_result` → `_save_and_report` reports it → `UNSAVED` → non-zero exit. The message names the path and the selecting rule. |
| Write fails (disk full, permissions, path became unwritable) | Same `UNSAVED` path. The review is already displayed, so the run is not lost. |
| Prior artifact cannot be archived | Existing refuse-to-overwrite guard, unchanged: the write is refused rather than destroying content. |

Rule 2 is the one exception to "created": it *requires* the project reviews directory to already
exist, because creating it is what would put `project-documents/` inside a repository that never
asked for one. When it does not exist, precedence continues to rule 3 — that is selection, not
a failure fall-through.

#### Where the resolver lives

`src/squadron/review/reviews_dir.py`, not the CLI layer — and it takes `host`, `owner` and
`repository` as **plain strings** rather than a `PullRequestRecord`. The record would be the
natural parameter, but `review/` must never import `codehost`, and the import-boundary test walks
every file in the package. The CLI caller already imports both, so it passes the three fields.

This also keeps the precedence rule beside `REVIEWS_DIR`, the constant it is built from, rather
than in `cli/commands/`. The alternative considered was importing it into `review_pr.py` from
`cli/commands/review.py`, which is where that module already reaches for four private helpers
under `pyright: ignore[reportPrivateUsage]`; a fifth would have deepened a pattern already
flagged four times.

`resolve_reviews_dir` returns the directory **and** a `ReviewsDirRule`, whose values are written
in operator terms (`--reviews-dir`, `review.external_reviews_dir`, `project reviews directory`,
`built-in default`) because they are printed with the result. A rule name that tells the operator
what to change is the difference between a location they can act on and one they can only read.

The resolver **creates nothing**. Creation stays in `save_review_result`, so an `OSError` is
reported through the existing unsaved-review path with the chosen directory named — and so a
caller asking only *where* a review would go does not mutate the filesystem to find out.

### D6 — Rules-source provenance requires `resolve_rules_dir` to report its source

The plan calls this "one additive optional frontmatter key", but the value does not exist:
`resolve_rules_dir` returns `Path | None` and discards which of its five branches produced it. A
project `rules/` directory and `~/.config/squadron/rules/` are both just a `Path` to the caller.

So the signature changes to return the path and its source together — a `RulesSource` StrEnum
beside the path. Every caller is updated in this slice; callers that do not care ignore the
second value.

**The enum has six members, not four.** The plan's "project, user, template" undercounts what the
resolver actually distinguishes, and `TEMPLATE` as written named no branch at all:

| Member | Branch |
|---|---|
| `FLAG` | `--rules-dir` |
| `CONFIG` | the `rules_dir` config key |
| `PROJECT` | `{cwd}/rules/` **or** `{cwd}/.claude/rules/` |
| `USER` | `~/.config/squadron/rules/` |
| `TEMPLATE` | `~/.config/squadron/templates/` (new branch, see below) |
| `NONE` | nothing found |

`FLAG` and `CONFIG` are separate members because collapsing either into `PROJECT` would make
`rulesSource` assert provenance the artifact does not have: `--rules-dir /tmp/scratch` is not a
project source, and an artifact claiming it was is a false record that nothing downstream can
correct. Both project-local layouts *do* collapse into `PROJECT` — the question the key answers is
whose rules these are, and either layout answers "the project's".

**`TEMPLATE` required adding a branch, and that is a deliberate scope addition.** At design time
`resolve_rules_dir` had no template branch, which is why the member appeared to name nothing. But
`~/.config/squadron/templates/` already exists as an established convention — it is defined in
code as `USER_TEMPLATES_DIR` (`review/templates/__init__.py`) and sits beside user-defined models
(`models.toml`) and pipelines (`pipelines/`). User review templates are the more likely home for
`review-code.md` than a project `rules/` directory, so a provenance key that cannot name them
records the wrong thing for the common case.

The branch is appended at the **tail** — after `~/.config/squadron/rules/`, before the `None`
return. Tail position is what keeps D6 behavior-preserving on the path value: the new branch is
reachable only where the resolver previously returned `None`, so every input that resolved to a
path before resolves to the same path now. Task 1.2's "do not change which path any branch
resolves" holds exactly, and the caller-path pinning test stays valid as written.

One implementation constraint, recorded because it is invisible and easy to reintroduce: the
branch derives its path from `Path.home()` at call time rather than reading the module-level
`USER_TEMPLATES_DIR` constant. The constant binds at import, so a test patching `Path.home()`
could never reach the branch — it would pass by *skipping* rather than by resolving, which is the
same "a skipped check proves nothing" failure D7 records for `cf validate`. The templates package
still owns the canonical location; only the directory name is read from it.

`rulesSource` is then written as an optional frontmatter key on every review, not only PR
reviews — the value is equally true for a slice review and costs nothing. Optional means existing
artifacts without it still parse, and its absence is never inferred as any particular source.

Writing the key is sequenced **after** the migration's byte-identity verification, together with
`targetKind` (D2, D4). The signature change lands first and alone as described below; the
frontmatter key follows once slice, arch, and step artifacts have been proven unchanged. The
scope is unaffected — every review still carries it.

This is the one change here that touches a function every review path calls, which is why it is
sequenced first in the implementation order: behavior-preserving, lands alone, with a test that
every existing caller's resolved *path* is unchanged.

### D7 — No context-forge schema change is needed, and here is how that was established

The plan names a possible cf schema dependency and says to discover it at design time. Probed,
not assumed:

- cf's `review` schema (`frontmatterSchema.js`) requires `docType`, `project`, `status`,
  `dateCreated`, `dateUpdated`. **`slice` is not required for `review`** — only for `slice-design`
  and `tasks`. Validation checks required-field presence and enumerated values; unknown keys such
  as `pr` and `rulesSource` pass through untouched.
- `inferDocTypeFromPath` requires a leading `\d+`, so a PR filename infers no docType — which
  skips *inference*, not validation, because `docType: review` is present in the frontmatter.
- Empirically: a PR-shaped fixture (non-numeric name, no `slice`, nested `pr:` mapping) placed in
  the reviews directory took the validated file count from 529 to 530 with **zero** findings
  against it.

**The probe is easy to run wrong, so the method matters.** `cf validate frontmatter` resolves its
project by *registered project*, not by working directory, and `-p/--project` is the only
override. Explicit-path invocations from this worktree return `filesChecked: 0` — cf silently
skips paths outside the registered root, which is exactly the "a skipped fixture proves nothing"
failure `tests/documents/test_schema_drift.py` warns about in its docstring. The valid probe is
the no-argument walk against the registered root, comparing counts before and after.

Consequence for this slice's own test: the PR-shape validation test must assert `filesChecked`
increased, never merely that findings were zero — a skipped file also reports zero.

The three pre-existing `test_schema_drift.py` failures in this worktree are that same
registered-root mismatch (context-forge issue #88), unrelated to this slice and not its to fix.

#### A note on test fakes, for Task 8

Landing the real save turned one existing test from a passing assertion into a
`_Result` object has no attribute 'timestamp'` error, and the fix was to **narrow the test, not
fatten the fake**. `tests/cli/test_review_pr.py` installs a two-line stub carrying only
`verdict = "PASS"`, because every case in that suite is unit-level: did this flag reach the review
call. Before 383 nothing on that path ever rendered markdown, so the stub was sufficient. Driving
a real `save_review_result` through it would require teaching the fake the whole `ReviewResult`
shape — timestamp, raw output, findings, scan counts — and would quietly convert a fast
flag-routing suite into a persistence suite.

The real save, its location, its filename, and its `reviewedSha` are asserted in
`tests/cli/test_review_pr_persistence.py`, whose fixtures exist for that. The general rule, which
Task 8 will meet again when two new keys start rendering on every path: when a change makes an
existing fake insufficient, check whether the test was ever *about* the thing the fake now has to
model. If it was not, the assertion moves rather than the fake growing.

### D8 — Not-persistable keeps its meaning

382's `_NOT_PERSISTABLE_REASON` ("PR review persistence is not yet available (383)") is deleted
along with the `save=lambda _target: False` stub. `NOT_PERSISTABLE` survives for the case it
actually describes: a review with no target to name an artifact under — a slice-less
`sq review code`. A PR review always has a target, so it never takes that path; it either saves
or reports a failed write as `UNSAVED`, and `_exit_on` exits non-zero on the latter as it does
for every other review.

## Integration Points

### Provides

- The `SaveTarget` protocol — 384 and 385 both consume persisted reviews, and any later non-slice
  review target implements it rather than inventing a fifth shape.
- The persisted PR review artifact, which 384 renders into a PR comment and whose `reviewedSha`
  384's staleness statement compares against.
- `resolve_rules_dir`'s source, and `rulesSource` on every review artifact.
- `review.external_reviews_dir`, `--reviews-dir`, and `PullRequestRecord.path_key`.

### Consumes from Other Slices

- 382's `sq review pr` path and its resolved record.
- 917's artifact rendering, unchanged and asserted unchanged.

## Success Criteria

### Functional

- A PR review in a planned repository saves under `project-documents/user/reviews/` with the
  PR-keyed name, and its `reviewedSha` equals the record's head sha — asserted with an operator
  HEAD deliberately different from the PR head, so the two cannot pass by coincidence.
- In a repository with no `project-documents/`, the review saves under the configured external
  directory, the location and the rule that chose it are printed, and **nothing is written inside
  the repository** — asserted by `git status --porcelain` being empty afterwards.
- The full precedence chain is table-tested: `--reviews-dir` beats an existing project directory,
  which beats the config key, which beats the built-in default.
- Each enumerated write-path failure mode (D5) is asserted: `--reviews-dir` at a non-existent
  path is created and written; an uncreatable directory and a failed write each report `UNSAVED`
  with a non-zero exit and a message naming the path; and neither falls through to the next
  precedence rule — asserted by the next-rule location being empty afterwards.
- `sq review resolve 42` and metrology capture for index 42 select the slice review, with a PR
  review of PR 42 present in the same directory.
- Arch reviews, slice reviews, and pipeline step-keyed reviews are **byte-identical** to
  pre-migration fixtures on all three paths, asserted with no new frontmatter key yet present.
- After `rulesSource` and `targetKind` land, the regenerated fixtures differ from the
  pre-migration ones by **exactly those two keys and nothing else**, asserted on all three paths.
  A third difference is unintended drift the migration check would otherwise have hidden.
- A pipeline step review whose target file cannot be archived is refused and logged, and the
  action still returns its review result rather than failing.
- Archiving, digest, and 917's integrity rendering run on a PR review artifact unchanged.
- `rulesSource` reads `project`, `user`, or `template` and matches the directory the loader
  actually used, asserted for each branch; an artifact written without the key still parses.
- A PR-shaped artifact validates under `cf validate frontmatter` with **`filesChecked` increased
  by one** and zero findings.

### Technical

- `ruff format`, `ruff check`, and `pyright` clean; zero pyright errors.
- No module under `review/` imports `squadron.codehost` — the existing import-graph test passes
  with `save_target.py` added.
- `SliceInfo` retains its current shape and consumers; this slice does not refactor it.
- The three `test_schema_drift.py` failures present before this slice are unchanged by it
  (context-forge #88).

### Verification Walkthrough

Run in a clone of `ecorkran/squadron` with `gh` authenticated, against an open PR.

1. Review a PR in this (planned) repository and confirm the artifact:
   ```
   sq review pr <number>
   ls project-documents/user/reviews/ | grep review.code
   ```
   The printed location names the project reviews directory. The new file's name begins with the
   flattened PR key, not a number.
2. Confirm the recorded sha is the PR's, not yours:
   ```
   git rev-parse HEAD
   grep -E '^reviewedSha:|^rulesSource:|^targetKind:' project-documents/user/reviews/<file>
   ```
   `reviewedSha` differs from your HEAD and matches the PR head shown by `gh pr view <number>`.
3. Confirm the slice consumers ignore it. With a slice review for the same number present:
   ```
   sq review resolve <number>
   ```
   It resolves the slice review and never offers the PR review.
4. Review a PR in an unplanned repository (no `project-documents/`):
   ```
   cd /path/to/unplanned-repo && sq review pr <number> && git status --porcelain
   ```
   The printed location is under `~/.config/squadron/reviews/<host>/<owner>/<repo>/`, the file is
   there, and `git status` prints nothing.
5. Override the location for one run:
   ```
   sq review pr <number> --reviews-dir /tmp/pr-reviews && ls /tmp/pr-reviews
   ```
   The printed source names the flag.
6. Validate the artifact's frontmatter. Note that `cf` resolves by registered project, not cwd:
   ```
   cf validate frontmatter --json | python3 -c "import sys,json; print(json.load(sys.stdin)['filesChecked'])"
   ```
   Run it before and after the review; the count increases by one and findings stay zero.

Steps 2, 4, and 6 for one run are recorded in the DEVLOG entry that closes this slice.

## Risk Assessment

- **Three callers migrate at once.** The arch, slice, and pipeline paths change shape in one
  slice, and a formatting regression would silently alter every artifact written afterwards.
  Mitigation: byte-identity fixtures captured before the change on all three paths and asserted
  once the migration lands, while no new frontmatter key yet exists — the migration is not "tests
  still pass" but "output is unchanged". The two additive keys land only after that assertion is
  green, so the check is never asked to tell an intended key from a regression.
- **`resolve_rules_dir` is called by every review path.** A signature change there reaches code
  this slice otherwise does not touch. Mitigation: sequenced first, landing alone, with a test
  pinning that every existing caller's resolved path is unchanged.
- **`reviewedSha` is the easiest thing to get wrong.** The existing code resolves it from the
  process working directory, which on the PR path is the wrong tree and still produces a
  plausible-looking sha. Mitigation: the target supplies it, and the test deliberately makes
  operator HEAD and PR head differ.

## Implementation Notes

### Order

1. `resolve_rules_dir` returns its source (D6), all callers updated, paths pinned unchanged. The
   signature only — the `rulesSource` frontmatter key comes later, at step 7.
2. `SaveTarget` protocol with `SliceTarget`, `ArchTarget`, `StepTarget`; byte-identity fixtures
   captured first, then persistence migrated onto the contract (D1, D2).
3. Arch review drops `_arch_slice_info`; pipeline step path migrates, with its archive-guard test.
   **Byte-identity is verified green on all three paths here, against untouched fixtures.** No
   new frontmatter key exists yet, so any diff at this point is unintended drift — which is the
   only condition this check can detect, and why it precedes step 7.
4. `PullRequestRecord.path_key`, with `worktree.py::_flatten_key` collapsed onto it (D3).
5. `review.external_reviews_dir`, `--reviews-dir`, and the precedence resolver (D5).
6. `PrTarget` and the real save in `review_pr.py`, replacing 382's stub (D3, D8).
7. `rulesSource` and `targetKind` added together on every target (D4, D6), with the fixtures
   regenerated once and the diff confirmed to contain exactly those two keys; then `targetKind`
   classification and the non-matching-glob regression tests (D4).
8. Conventions guide, cf validation test, live run, DEVLOG entry, CHANGELOG line.

### Testing

- `tests/review/test_save_target.py` — the four implementations' stems, frontmatter fields, and
  source documents.
- `tests/review/test_persistence_migration.py` — byte-identity against pre-migration fixtures for
  slice, arch, and step paths. The fixtures are captured in step 2 before any change.
- `tests/cli/test_review_pr_persistence.py` — the precedence table, the unplanned-repository
  no-write assertion, and the `reviewedSha`-is-the-PR's-not-yours test.
- `tests/review/test_review_consumers_ignore_pr.py` — resolve and metrology capture for index 42
  with a PR-42 review present.
- `tests/review/test_rules_source.py` — each `RulesSource` branch, and existing callers' paths
  unchanged. This covers the resolver's *return value* only.
- `tests/review/test_rules_source_artifact.py` — the end-to-end half: write an artifact, read
  `rulesSource` back from the written file, and assert it matches the branch the loader actually
  took. The resolver test and the write are separately correct in ways that still leave a
  hardcoded or never-threaded value undetected; only reading the field back off disk closes that.
- `tests/documents/` — the PR-shape cf validation test, asserting `filesChecked` increased.
- Live evidence is recorded, not asserted; no test needs `gh`, network, or auth.
