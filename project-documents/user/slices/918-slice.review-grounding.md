---
docType: slice-design
slice: review-grounding
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: [917]
interfaces: []
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Slice Design: Review Grounding

## The problem in one paragraph

916 asked whether a review examined the right *scope*. 917 asked whether the persisted
artifact could be *trusted*. This slice asks whether the reviewer read the **document
actually under review** — and, when its output is lost anyway, whether the artifact
records why. Part 1 (#94) stops a re-review from grading text that was deleted two
revisions ago. Part 2 (#92) stops discarding the two facts that explain why a full,
substantive model response parsed to nothing. Part 3 (#65) stops `sq install-commands`
from deleting files it did not install. Parts 1 and 2 are one family — a review whose
output does not correspond to the file in front of it. Part 3 is unrelated and rides
along because it is small, contained, and loses user data.

## Scope corrections against the plan entry

Verified against `main` at `19bc4f80` while designing. The plan entry stands on all
three parts; these are refinements, not reversals.

1. **The plan entry says the deny-list goes in `resolve_in_jail` / `contained_in_jail`.
   Those are the enforcement point, but not where the decision enters.** Both helpers
   take `(cwd, path)` and nothing else, and every built-in tool executor is bound to a
   `cwd` and nothing else: `ToolFactory = Callable[[Path], ToolExecutor]`
   ([tools/models.py:37](src/squadron/tools/models.py#L37)). There is no channel for a
   second argument today. Adding one is the actual work of Part 1, and it is a change to
   the tool-binding contract rather than a two-line predicate edit. Effort for Part 1
   rises accordingly; see Risks.

2. **The per-review-type carrier already exists and is not config.** The plan entry
   directs the deny-list to resolve from `review.external_reviews_dir` (the key slice 383
   is adding). That is right about *where the reviews directory lives* but wrong about
   *what declares the exclusion*: `ReviewTemplate.diff_exclude_patterns`
   ([templates/__init__.py:40](src/squadron/review/templates/__init__.py#L40)) is an
   existing per-template list-of-strings field, declared today only by `code.yaml`
   ([code.yaml:76](src/squadron/data/templates/code.yaml#L76)), that already expresses
   "this review type excludes these paths." Part 1 adds a sibling field for the tool jail
   rather than a config key, which gets per-review-type scoping for free and puts the
   declaration next to the review type it describes. The configured reviews directory is
   still what the *default value* must resolve to — the two points are compatible and
   both are honored.

3. **Part 2's evidence has a channel; it is the message metadata, not a new return
   type.** `TurnResult` carries `finish_reason` and `reasoning_chars`
   ([agent.py:103-105](src/squadron/providers/openai/agent.py#L103-L105)) but is
   documented as "internal plumbing between `_stream_turn` and its callers — not
   translated into caller-facing Messages." Tool telemetry solved this same problem via
   final-`Message.metadata` (design D4), read back in `review_client`
   ([review_client.py:227-238](src/squadron/review/review_client.py#L227-L238)). Part 2
   follows that established path.

## Non-goals

- **Semantic verification of quoted text.** #94's second suggested check — a quoted
  phrase absent from the reviewed file as a hallucination signature — is the
  document-review analogue of 904's diff-membership check. Genuinely valuable, sized like
  its own slice, and unnecessary once the stale source is removed. Re-assess after this
  slice.
- **Injecting prior findings into a re-review.** Verified: no builder and no template
  references a prior review, so nothing is being removed here. 305's findings-addressed
  gate owns deliberate prior-findings injection. This slice closes the *discovery* path
  and leaves the *injection* path to 305.
- **Fixing #92's mechanism speculatively.** Part 2 lands instrumentation first. The fix
  follows the evidence; see Part 2.
- **#65's dependency findings.** Findings 2 and 3 (three declared-but-unimported runtime
  deps; `rich` imported but undeclared) are routed to the existing **907 Optional
  Dependency Split** entry, which already owns `pyproject.toml` restructuring.

## Parts, in execution order

1. **Jail exclusions for document reviews (#94)** — highest severity, verified mechanism,
   and it changes the tool-binding contract the other parts do not touch.
2. **Stop-reason evidence on every review (#92)** — instrumentation, then a fix chosen by
   what the instrumentation reports.
3. **Receipt-based command install (#65)** — independent; may land in any order.

Parts 1 and 2 both touch review-path files but not the same ones (`tools/` and
`providers/openai/` respectively). Part 3 touches neither.

---

## Part 1 — Jail exclusions for document reviews (#94)

### What goes wrong today

`sq review arch 380 -v`, minimax-m3, tools enabled, third consecutive run at
`reviewedSha: bd306bc8`. The saved review quoted three phrases removed from the document
in the two prior revisions and repeated the corresponding findings as unaddressed, while
the current file states each explicitly. The third run escalated to **FAIL on recycled
findings** — the review gate loop cannot converge if a re-review grades the revision it
already dispositioned.

The mechanism is fully determined. `archive_existing_review`
([persistence.py:439](src/squadron/review/persistence.py#L439)) writes every superseded
review to `<reviews>/archive/` under its original name. The jail root for a document
review is the repo root. So the archived predecessors of the document under review sit
inside the jail, named with the document's own prefix. Observed layout for the reported
case: one live `380-review.arch.pull-request-workflow.md` plus five archived
predecessors, every one name-prefixed with the document being graded. A model grepping
for the document's topic finds them and reads them as context.

### Decisions

**D1 — Exclude the whole reviews directory, not just `archive/` (PM, 20260913).**
Excluding only `archive/` fixes the observation and leaves the bug: the live review of
the document under review is the single most on-topic file in the tree for that reviewer,
and on run three it held findings the author had already dispositioned. The
recycled-findings failure reproduces from the live file alone.

The tension was weighed rather than dismissed. A re-review arguably *should* know what
the last round said. It is resolved by *discovered* vs. *injected*: 305 passes prior
findings deliberately — a known set, from a known revision, labeled as prior — whereas
#94 is the same information arriving unlabeled, from an arbitrary mix of revisions,
indistinguishable from the document under review. A model cannot tell "raised and since
fixed" from "wrong now," and on run three it chose FAIL.

**D2 — Per review type, declared on the template (PM, 20260913).** Code reviews read the
tree broadly by design — that is how a finding cites a real file — and their scope is a
diff, so archived reviews are not name-adjacent to what they examine. Document reviews
(arch, slice, tasks) examine one named document and never need to read reviews. A global
switch would either break code reviews or leave document reviews exposed.

The carrier is a new `ReviewTemplate` field, sibling to `diff_exclude_patterns`. Name it
for what it governs — the tool jail, not the diff — e.g. `tool_exclude_patterns`. Loader
handling mirrors `diff_exclude_patterns`
([templates/__init__.py:140-144](src/squadron/review/templates/__init__.py#L140-L144)):
optional, list-of-strings, `None` when absent. `arch.yaml`, `slice.yaml`, and
`tasks.yaml` declare it; `code.yaml` does not. The two judge templates
(`judge-slice-vs-arch`, `judge-tasks-vs-slice`) are document reviews and should declare
it too — confirm during implementation whether they run with tools at all, and skip them
if not.

**D3 — Silent to the model, WARNING to the operator.** Follow `contained_in_jail`'s
established D6 precedent ([_shared.py:43](src/squadron/tools/builtin/_shared.py#L43)): an
excluded path must be indistinguishable to the model from one that did not match. A model
told "you were denied" probes the boundary. The refusal logs at WARNING so it is
observable to an operator, matching the existing jail-escape log line.

**D4 — The default value resolves from configuration, not a literal.** The reviews
directory is not fixed: slice 383 (initiative 380, `squadron-pr`) is adding
`review.external_reviews_dir`. The exclusion default must resolve from the same location
the writer uses, or the two drift apart the first time someone reconfigures it. Since the
template field holds patterns rather than a resolved path, the resolution happens where
the patterns are bound to a `cwd` — see D5. If 383 has not landed when this is
implemented, resolve against the current default and leave a single named seam rather
than scattering the literal.

**D5 — Exclusions enter through tool binding, alongside `cwd`.** This is the contract
change. `materialize(names, cwd)`
([registry.py:41](src/squadron/tools/registry.py#L41)) resolves `cwd` exactly once and
hands it to `descriptor.factory(resolved)`; it has exactly one caller,
[agent.py:190](src/squadron/providers/openai/agent.py#L190). The agent is a generic
provider and **must not learn what a review type is** — it takes the exclusions as opaque
data, exactly as it takes `cwd`.

The shape to prefer: introduce a small value object — a jail specification carrying the
resolved root and the resolved exclusion paths — and thread it where `cwd` is threaded
today (`ToolFactory`, `materialize`, the agent's `cwd` parameter). `resolve_in_jail` and
`contained_in_jail` then answer two questions instead of one, returning `None` / `False`
on an excluded path by the *same* code path as a containment failure, so every existing
caller's handling is unchanged and no tool contract or error path changes.

Prefer this over the alternatives considered: a module-global exclusion set (untestable
in parallel, and wrong the moment two reviews run concurrently), and a per-tool argument
(the model supplies tool arguments, so an exclusion there is model-controllable).

**D6 — Exclusions are resolved paths, matched by containment.** Patterns come from the
template as strings; they are resolved against the jail root once, at bind time, in the
same place `cwd` is resolved. Matching is `is_relative_to` against a resolved candidate,
never string-prefix comparison — the identical reasoning `resolve_in_jail` already
documents (`/tmp/jail_evil` starts with `/tmp/jail` but is not inside it). A pattern that
resolves outside the jail is discarded at bind time with a WARNING, since it can never
match and silently keeping it invites a false sense of coverage.

### Where the change lands

- `src/squadron/tools/models.py` — the jail specification type; `ToolFactory` signature.
- `src/squadron/tools/registry.py` — `materialize` resolves root and exclusions together.
- `src/squadron/tools/builtin/_shared.py` — both predicates consult exclusions.
- `src/squadron/tools/builtin/{file_tools,search_tools,bash_tool}.py` — factories accept
  the new binding. **`bash_tool` needs explicit attention**: it runs a subprocess with the
  jail as its working directory and does not route file access through the two predicates,
  so a path exclusion does not constrain it. Determine during implementation whether
  document-review templates grant `bash` at all; if they do, either withhold it for those
  templates or state plainly in the design that the exclusion is best-effort against
  `bash`. Do not leave this implicit.
- `src/squadron/review/templates/__init__.py` — the new template field and its loader.
- `src/squadron/data/templates/{arch,slice,tasks}.yaml` — declare the exclusion.
- `src/squadron/review/review_client.py` — pass template exclusions to the agent.

### Success criteria

- An arch review of a document with archived predecessors cannot read, list, or grep any
  file under the reviews directory; a test asserts each of the three tools refuses.
- The refusal is invisible in tool output and produces exactly one WARNING per refusal.
- A code review's tool access is **unchanged** — a test pins that `code.yaml` declares no
  tool exclusion and that a code review can still read a file under the reviews directory.
- An exclusion pattern resolving outside the jail is dropped at bind time with a WARNING.
- Two reviews with different exclusions running concurrently do not affect each other
  (the anti-global-state criterion).
- The reported reproduction: three consecutive `sq review arch` runs on a document
  revised between each produce findings that track the current text, with no phrase quoted
  from an archived revision.

---

## Part 2 — Stop-reason evidence on every review (#92)

### What goes wrong today

`sq review slice 916 -v --model kimi3` (openrouter `moonshotai/kimi-k3`), 17 tool calls
at sha `1515cff`. Verdict UNKNOWN, zero findings — while `raw_output` held 3302 characters
of a complete, well-grounded review that tracked prior-round findings, evaluated revised
sections, checked the design against its parent architecture, and caught a real stale
cross-reference. Its closing lines: `Verdict: PASS, with two NOTE findings ... Let me
write positive PASS findings for the key criteria and the two NOTEs.` It then stopped.
The reasoning was complete; the formatted output was never emitted.

A second, differently-shaped occurrence was observed 20260913 and widens the part.
`sq review slice 917 -v --model kimi27` failed with
`Model returned an empty final turn (finish_reason='stop', reasoning_chars=3)` — but the
two lines above it were `list_files: path does not exist: project-documents/user/slices`
and the same for `.../architecture`. Both tool calls failed, the model had nothing to
review, and it stopped. The error blames the model for returning nothing when the actual
cause was the tool layer failing twice first. (That run's own cause was a jail root
predating `_resolve_review_cwd` — issue #86, fixed on `main` but not in any release. The
misattribution is the durable defect, not the stale binary.)

A third shape landed 20260913, on this very slice's own review
(`918-review.slice.review-grounding.md`, `moonshotai/kimi-k2.7-code`, sha `4b04eece`).
The model emitted a complete, well-formed review — `## Summary`, verdict `PASS`, four
findings each with `category:` and `location:` tags — with **zero newlines in 3076
characters**. `_SUMMARY_RE` requires `##\s+Summary\s*\n+`, so the verdict never parsed;
every `_FINDING_RE` terminator lookahead is `\n`-anchored, so finding #1 absorbed the
other three; and `_CATEGORY_RE`/`_LOCATION_RE` are `^…$` under `MULTILINE`, so all eight
tags were dropped. Restoring newlines takes finding matches from 1 to 4. Filed as
[#96](https://github.com/ecorkran/squadron/issues/96), with
[#97](https://github.com/ecorkran/squadron/issues/97) for the derived-verdict consequence.

917 made all three shapes **more visible without fixing any of them**. The always-on Run Digest
([persistence.py:184](src/squadron/review/persistence.py#L184)) shows a long response with
no located sections and zero surviving matches. What it does not show is *why* — and in
the kimi27 shape it does not show that tools failed at all, so a reader cannot tell "the
model produced nothing" from "the model was handed nothing".

The two facts that would discriminate the cause are captured and then dropped.
`finish_reason` and `reasoning_chars` live on `TurnResult`, but reach a caller only
through `_require_final_content` ([agent.py:67](src/squadron/providers/openai/agent.py#L67)),
which returns early unless the turn `is_empty()`. #92's turn is emphatically non-empty,
so the one case where the stop reason *is* the diagnosis is the one case that records
neither.

Also verified: **`max_tokens` is never set on any request** — no occurrence anywhere under
`providers/openai/`. The issue's "output budget consumed by reasoning" candidate is
therefore live and cheaply testable, and it is the same candidate #84 raised and left
open.

### Decisions

**D7 — Instrumentation lands first and unconditionally; the mechanism fix follows the
evidence.** This part has two steps and the second cannot be specified until the first
runs. That is deliberate, not underspecification: three candidate mechanisms remain
(turn-boundary bug, output-budget exhaustion, prompt adherence) and they call for three
different fixes. **Do not apply a speculative fix.** Land step 1, re-run the reproduction,
read the stop reason, then fix what it names. This is the project's standing rule on
debugging without evidence, and #92 is exactly the shape it exists for.

**D8 — Carry the evidence on final-`Message.metadata`, the tool-telemetry channel.**
Tool telemetry solved the identical problem — a fact known inside the agent, needed by
`review_client`, with no natural return path — by stamping the final Message's metadata
(design D4) and reading it back
([review_client.py:227-238](src/squadron/review/review_client.py#L227-L238)). Follow it
rather than widening `TurnResult`'s documented role as internal plumbing or adding a
second return channel. Two new keys: the stop reason and the reasoning character count.

**D9 — Count failed tool calls and carry them the same way.** The kimi27 shape is
diagnosable only if the artifact records that tools failed. `ToolResult.is_error` already
exists as a first-class field ([tools/models.py:23](src/squadron/tools/models.py#L23)) and
`_execute_tool_call` already branches on it to log at INFO
([agent.py:373](src/squadron/providers/openai/agent.py#L373)) — but it returns `str`, so
the error-ness is discarded at its return and never reaches the counter. `tool_calls_made`
([agent.py:457](src/squadron/providers/openai/agent.py#L457)) counts calls without regard
to outcome.

Add a failed-call counter beside it and stamp it with the other telemetry. Prefer widening
`_execute_tool_call`'s return over re-inspecting content strings downstream — matching on
an `"Error: "` prefix would be exactly the string-dispatch this project forbids. Note the
executor-raised path ([agent.py:367](src/squadron/providers/openai/agent.py#L367)) also
yields an error the model sees; count it too, so the number means "tool calls that failed"
rather than "tool calls whose executor returned `is_error`".

**D10 — Surface all three in the Run Digest, and only there.** `_run_digest_lines`
([persistence.py:175](src/squadron/review/persistence.py#L175)) is 917's home for
diagnostic facts, and its docstring already states that the frontmatter is for what the
verdict gate checks while diagnostic keys there invite coupling. Three new digest lines:
stop reason, reasoning characters, failed tool calls. Nothing gates on them; they are
evidence for a human or a future issue. Render an absent value with the digest's existing
`_NOT_COMPUTED` treatment rather than inventing a placeholder — `None` means the provider
offered no stop reason, which is different from a stop reason of `"stop"`. A failed-call
count of `0` is a real answer and must not render as not-computed.

The failed-call line earns its place next to the existing `Tool calls made` line: the pair
`Tool calls made: 2` / `Tool calls failed: 2` names the kimi27 shape at a glance.

**D10a — Report a newline-free response as its own digest fact.** #96's fix belongs to the
parser, not here, but the *condition* is a one-line check and it is the cheapest possible
discriminator: a multi-kilobyte response containing no line breaks is never a real review,
and it explains an UNKNOWN verdict and a collapsed finding list at a glance. Add a line
count (or a boolean for "response contains no line breaks") beside the response length.
This part does not fix #96; it makes the artifact say which of the three shapes occurred.
Note for whoever fixes #96: the same leniency must not reopen #91 — 917 Part F's fence
masking and section bounding both assume line structure, so they need review together.

**D11 — Add the corresponding `ReviewResult` fields as optional.** Three nullable
fields alongside `tool_calls_made` and the 917 digest fields. `None` means not reported,
exactly as the existing tri-state fields use it. Not serialized into frontmatter (D10).

**D12 — The SDK provider path is out of scope for step 1.** `finish_reason` is an
OpenAI/OpenRouter streaming concept. The SDK path has its own turn model, and reproducing
#92 there is a separate investigation. Stamp what the OpenAI path knows; leave the SDK
path stamping nothing, which reads as `None` and renders as not-computed. Do not fabricate
a value for it.

### Step 2, contingent

Once step 1 is in and the reproduction re-run:

- **`finish_reason == "length"`** → the model's output budget was consumed. `max_tokens`
  is unset on every request today, so sizing it against reasoning models is the fix, and
  it closes #84's open follow-up at the same time. Most likely outcome given the symptom.
- **A clean `stop` with a non-empty turn that parsed to nothing** → the model ended its
  turn believing more were available and the loop treated it as final. A turn-boundary
  bug in the agentic loop.
- **Neither** → prompt adherence: the model narrated its plan instead of emitting the
  format. Worth checking whether 917 Part F's fenced specimens changed adherence, since
  that part established these templates interact with output shape in non-obvious ways.

Record which branch the evidence selected in the DEVLOG before implementing it.

### Success criteria

- Every review artifact's Run Digest carries a stop reason, a reasoning-character count,
  and a failed-tool-call count, on success and on degradation alike.
- A review whose response parses to zero findings shows a non-empty response length
  **and** a stop reason in the same digest — the #92 signature, readable from the artifact
  with no `-vv` and no live terminal.
- A review in which every tool call failed shows `Tool calls made` and `Tool calls failed`
  equal and non-zero — the kimi27 shape, distinguishable from a model that simply produced
  nothing. A test drives a review whose tools all error and asserts both counts.
- A run with no failed tool calls reports `0`, not not-computed.
- A newline-free response is named as such in the digest, so the #96 shape is
  distinguishable from #92's never-emitted output and from the kimi27 all-tools-fail shape.
  A test parses a known newline-free response and asserts the digest says so.
- An SDK-path review renders the stop reason and reasoning count as not-computed rather
  than as fabricated values.
- The #92 reproduction is re-run, its stop reason recorded in the DEVLOG, and the
  contingent fix for that branch implemented and verified against the same command.

---

## Part 3 — Receipt-based command install (#65 finding 1)

### What goes wrong today

`install.py` walks every subdirectory of the bundled `commands/` and unlinks any `*.md`
in `~/.claude/commands/<subdir>/` not present in the bundle
([install.py:59](src/squadron/cli/commands/install.py#L59)). The bundle currently ships
`analysis/` and `sq/`. A user who keeps their own
`~/.claude/commands/analysis/*.md` loses them on the next `sq install-commands` — and
`sq setup` runs that command as step 2 of 17, so the loss happens during routine
onboarding, unprompted. `uninstall_commands` is asymmetric, removing only `sq/`.
Verified still present on `main`, 20260913.

### Decisions

**D13 — Track installed files in a receipt; remove only what squadron installed.** The
reporter's suggestion, and `sq skills` already does this — follow the existing mechanism
rather than inventing a second one. Read its receipt shape and location during
implementation and match it; a second, differently-shaped receipt for the same kind of
job is the thing to avoid.

**D14 — Make uninstall symmetric.** It removes every subdirectory the receipt records,
not just `sq/`.

**D15 — A file present but absent from the receipt is left alone, and stale receipt
entries are tolerated.** Pre-receipt installs exist in the wild: a user who installed
before this change has squadron's own files on disk with no receipt naming them. Deleting
unknown files is the bug being fixed, so the safe direction is to leave them and let the
next install overwrite squadron's own by name. Conversely, a receipt naming a file the
user already deleted is not an error.

### Success criteria

- A user file in a shared subdirectory (`~/.claude/commands/analysis/mine.md`) survives
  `sq install-commands`, and a regression test covers the non-`sq` subdir path that
  `tests/cli/test_install_commands.py` does not cover today.
- Squadron's own bundled files are still installed and refreshed on re-run.
- `sq uninstall-commands` removes every subdirectory squadron installed, and leaves user
  files.
- Running `sq install-commands` twice is idempotent and produces no deletions on the
  second run.
- An install over a pre-receipt installation (files present, no receipt) deletes nothing.

---

## Risks

- **Part 1 changes a shared contract.** `ToolFactory` and `materialize` are used by every
  tool-enabled path, not only reviews. The mitigating facts: `materialize` has exactly one
  caller, and the exclusion set is empty for every template except the three document
  ones, so a mistake shows up as "document reviews cannot read anything" rather than as
  silent over-permission. Pin the empty-exclusion case with a test so the default path is
  provably unchanged.
- **Part 1's `bash` gap is real.** A path deny-list does not constrain a subprocess.
  Called out in "Where the change lands" and must be resolved during implementation, not
  discovered in review.
- **Part 2's step 2 is genuinely unknown.** Sized as instrumentation plus one contingent
  fix; if the evidence points at prompt adherence, that may warrant its own follow-up
  rather than expanding this slice. Decide when the evidence is in.
- **Part 1 removes context a re-review currently sees.** By design (D1), and 305 owns the
  deliberate replacement. If a re-review after this slice proves unable to judge whether
  findings were addressed, that is a 305 gap to file, not a reason to reopen D1.

## Effort

3/5 overall. Part 1 is the bulk (contract change plus six touched modules); Part 2 step 1
is small and step 2 is unknown-but-bounded; Part 3 is small and self-contained.

## Verification walkthrough

Draft; refine at Phase 6 completion.

**Part 1 — the reported reproduction.** In the `squadron-pr` worktree, where the 380
document and its five archived reviews live:

```bash
ls project-documents/user/reviews/archive/ | grep 380     # confirm the predecessors exist
sq review arch 380 -v --model minimax-m3
```

Read the saved review. Confirm no finding quotes a phrase absent from the current
`380-arch.pull-request-workflow.md`, and that findings dispositioned in earlier rounds do
not reappear. Then confirm the exclusion actually fired rather than the model simply not
looking:

```bash
sq review arch 380 -vv --model minimax-m3 2>&1 | grep -i 'refus'
```

Expect one WARNING per refused access, and nothing in the model-visible transcript naming
a denial.

**Part 1 — code reviews unaffected.** `sq review code <slice> -vv` on a change touching a
file under `project-documents/user/reviews/`; confirm the reviewer reads it and no
refusal is logged.

**Part 2 — the digest carries the evidence.** Any review, then read the artifact:

```bash
sq review slice 916 --model <any>
sed -n '/### Run Digest/,/^$/p' project-documents/user/reviews/916-review.slice.*.md
```

Expect a stop reason, a reasoning-character count, and a failed-tool-call count present
on a clean PASS, not only on a degraded run, with the failed count reading `0`.

Then the kimi27 shape. This one has no clean CLI reproduction: the observed run's cause
was a jail root predating `_resolve_review_cwd`, and on `main` that function anchors the
jail at the git root regardless of `--cwd` — verified, `--cwd ./project-documents/user`
still resolves to the repo root. The all-tools-fail path is therefore covered by the test
named in the success criteria (a review whose executors all return `is_error`) rather than
by a command here. If a live instance does recur, the check is that the failure artifact's
digest shows `Tool calls made` and `Tool calls failed` equal and non-zero, so the artifact
names the tool layer rather than blaming the model.

Then the #92 reproduction itself:

```bash
sq review slice 916 -v --model kimi3
```

If it reproduces, the digest now names the stop reason; record it in the DEVLOG and
implement the branch it selects. If it does not reproduce, the instrumentation still
lands — say so plainly rather than claiming the underlying cause is fixed.

**Part 3 — user files survive.**

```bash
echo '# mine' > ~/.claude/commands/analysis/zz-scratch.md
sq install-commands
test -f ~/.claude/commands/analysis/zz-scratch.md && echo SURVIVED || echo DELETED
```

Expect `SURVIVED`. Then `sq install-commands` a second time and confirm no deletions, and
`sq uninstall-commands` and confirm squadron's files go and `zz-scratch.md` stays. Remove
the scratch file afterward.
