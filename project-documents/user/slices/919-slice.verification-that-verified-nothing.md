---
docType: slice-design
slice: verification-that-verified-nothing
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: [917, 918]
interfaces: []
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Slice Design: Verification That Verified Nothing

## The problem in one paragraph

Three layers of this system report success having verified nothing. The parser, handed a
complete review with no line breaks, publishes a verdict it never found and one finding
where there were four ([#96](https://github.com/ecorkran/squadron/issues/96)). The
artifact then records that derived verdict in frontmatter with no mark distinguishing it
from one the model actually stated, so Context Forge's review gate clears the slice
([#97](https://github.com/ecorkran/squadron/issues/97)). And the commit gate whose job is
to reject bad frontmatter hands `cf` a list of paths, `cf` silently checks none of them,
and the gate reports `ok` ([#98](https://github.com/ecorkran/squadron/issues/98)). Where
916 asked whether the review examined the right scope, 917 whether the artifact can be
trusted, and 918 whether the reviewer read the right document, this asks whether a *pass*
means anything at all.

## Scope corrections against the plan entry

The plan entry was written from the issues. Reading the code and running the real
specimen corrected it in four places, all of which change the work.

**The plan's two candidate approaches are not equivalent, and the naive form of the
preferred one makes things worse.** The entry offered "relax each regex in place" versus
"normalize then parse" as comparable options. Measured against the real specimen, a
first-cut normalizer that inserts breaks before `##`/`###` and before each tag took the
parse from 1 finding to **0** — strictly worse than today. Three distinct traps, none
mentioned in #96, are documented in D1 below. Normalization is still the right shape, but
it is a precise transformation with named failure modes, not a two-line regex.

**`_extract_verdict` can return a *wrong* verdict, not merely UNKNOWN.** #96 reports the
verdict as lost. Worse is true. `_SUMMARY_RE` requires `(PASS|CONCERNS|FAIL)\b`, and in
the specimen the verdict is fused to the following word — `## SummaryPASSThe slice
design...`. There is no word boundary after `PASS`, so `\b` fails there and the
non-greedy `.*?` scans forward to the first *bounded* severity word, which is a `CONCERN`
belonging to a later finding. Inserting a break after `Summary` alone therefore yields
`verdict: CONCERNS` on a review whose stated verdict is `PASS`. A confidently wrong
verdict is a worse artifact than an UNKNOWN one, and any fix that stops at the newline
misses it.

**Markdown anchors in `location:` values are a second `#` source.** The specimen's
locations are of the form `project-documents/user/slices/918-slice.review-grounding.md#The-problem-in-one-paragraph`.
Any heading-insertion rule keyed on `#` treats that anchor as a heading, and because
`_locate_section` terminates a section at the next same-or-higher-level heading, a single
bogus level-1 heading inside a finding body truncates the findings section. Measured: a
corrected normalizer reached `total=4` finding matches but `in_section=1` for exactly this
reason. The rule must anchor on structural position, not on the character.

**`fallback_used` reaches the artifact body already; only frontmatter is missing.** The
entry says the flag "does not reach the surface the gates read," which is right, but the
gap is narrower than it sounds. `persistence.py:405` already renders the
"findings not parsed" section from `result.fallback_used`, and `:340` folds it into a
local `degraded`. What has no degradation parameter at all is
`_review_frontmatter_lines` ([persistence.py:242](src/squadron/review/persistence.py#L242)).
Part 2 is a frontmatter-emission change plus a policy decision, not new detection.

## Slice review disposition (20260913)

Slice review at sha `7b36737d` returned CONCERNS with three concerns and two notes; all
five were verified against the code and all five are accepted and addressed here.

- **F003 — Part 3's citations named a package that does not exist.** Correct. The gate
  files live in `src/squadron/events/builtin/`, not `events/actions/`; `pipeline/actions/`
  is a real but unrelated package, which is exactly what made the wrong path plausible.
  Three references corrected.
- **F004 — `_FENCE_OPENER` does not exist.** Correct: the symbol is `_FENCE_OPEN_RE`, at
  line 487. Fair characterization from the review, too — a slice premised on verification
  claims being trustworthy should not cite a symbol a grep will never find.
- **F005 — no hang handling on the subprocess path.** The substantive finding. Accepted and
  answered as **D14**: the part changes that call's contract, so the Failure-Mode
  Enumeration rule applies, and `await proc.communicate()` has no timeout today.
- **F006 — `parsers.py` line citations drifted 1-2 lines.** Correct; five citations came
  from grep offsets rather than definition lines. All five corrected and re-verified.
- **F007 — three-part bundling.** Note only, and the review's own reading is right: it
  matches 901, 909, 910, and 916-918 in this same plan. No change.

Nothing in the review contradicted a decision; the concerns were accuracy defects in the
document plus one genuinely missing failure mode.

## Non-goals

- **Fixing #92/#99.** 918 Part B landed the stop-reason instrumentation and the
  reproduction did not reproduce across two runs, so no branch of the mechanism is
  selected. 918's D7 holds: do not fix a mechanism speculatively. Both stay open.
- **Making the model emit newlines.** A prompt or template change that asks more firmly
  for line breaks is not a fix; the parser must handle valid semantic content regardless
  (`CLAUDE.md`, "Parsing & Pattern Matching"). Out of scope in both directions — this
  slice does not touch review templates.
- **Fixing context-forge#88.** The root cause of Part 3 lives in `cf`, and squadron
  cannot fix it. Part 3 is squadron's defense, which is warranted whether or not cf ever
  lands a fix.
- **Artifact naming for slice-less reviews ([#90](https://github.com/ecorkran/squadron/issues/90)).**
  Adjacent surface, but a naming design decision with collision and discoverability
  consequences; its silent-failure half is already closed by 916 Part C. Stays in Future
  Slices.
- **Semantic verdict verification.** Asking whether a stated verdict is *justified* by its
  findings is a different and much larger question than whether it was *stated*. Part 2
  records provenance only.

## Parts, in execution order

Sequence **1 → 2 → 3**, which inverts the plan entry's `C → A → B`.

The plan entry put the frontmatter gate first on the reasoning that it is self-contained
and needs no coordination. That is still true, and it remains independent — but Part 1 is
the highest-severity defect, it is the trigger that produced #97's derived verdict, and
settling its leniency story is what tells Part 2 how many distinct degradation shapes the
provenance flag must describe. Ordering the cheap independent item first buys nothing and
delays the decision the other two parts depend on. Part 3 can in fact land at any point;
it is last because it is the smallest and shares no file with the others.

| Part | Issue | Severity | Lands in |
|---|---|---|---|
| 1 — Newline-free responses parse | #96 | High | `review/parsers.py` |
| 2 — Verdict provenance in frontmatter | #97 | High | `review/persistence.py`, `review/models.py` |
| 3 — Frontmatter gate fails closed | #98 | Medium | `events/builtin/frontmatter_gate.py` |

## Part 1 — Newline-free responses parse (#96)

### What goes wrong today

Observed on `sq review slice 918 -v --model kimi27` (openrouter
`moonshotai/kimi-k2.7-code`), 20 tool calls at sha `4b04eece`. The persisted artifact is
`project-documents/user/reviews/918-review.slice.review-grounding.md`; its
`### Raw Response` section holds the specimen and is the fixture this part is verified
against.

The provider delivered **3076 characters with zero newlines**. Assembly is not at fault:
`review_client.py` joins parts with `"\n".join` (the #22 fix) and this was a single part.
Measured on that specimen today:

```
verdict:  UNKNOWN
findings: 1  (counts: total=1, in_fences=0, in_section=1, surviving=1)
finding:  [PASS] 'Scope fits the maintenance initiativecategory: scope-al…'
          location='unverified'  category=None  description=0 chars
```

The model's actual output was `## Summary` / `PASS` / four findings (three PASS, one
NOTE), each with its own `category:` and `location:`. The single surviving finding's
title is a 1300-character run-on containing all four findings' text, its body is empty,
and none of the eight tags were extracted.

Seven separate constructs in the parse pipeline depend on line structure. This is why
per-regex relaxation was rejected:

1. `_SUMMARY_RE` ([parsers.py:70](src/squadron/review/parsers.py#L70)) requires
   `##\s+Summary\s*\n+` before the verdict keyword.
2. `_FINDING_RE` ([parsers.py:81](src/squadron/review/parsers.py#L81)) terminates each
   finding on a lookahead whose every alternative is `\n`-anchored, so only `\Z` matches
   and finding #1 absorbs the rest.
3. `_CATEGORY_RE` / `_LOCATION_RE` ([parsers.py:106-107](src/squadron/review/parsers.py#L106-L107))
   are `^…$` under `re.MULTILINE`.
4. `_FILE_REF_RE` is `^->\s*(.+)$` under `re.MULTILINE`.
5. `_HEADING_RE` ([parsers.py:495](src/squadron/review/parsers.py#L495)) is
   `^(#{1,6})…$` under `re.MULTILINE`, which both `_locate_section` and the fence logic
   build on.
6. `_FENCE_OPEN_RE` ([parsers.py:487](src/squadron/review/parsers.py#L487)) is
   `^[ \t]*(fence)` under `re.MULTILINE`.
7. Inside `_extract_findings`, title and body are split by newline directly:
   `title = title_raw.strip().split("\n")[0]` and `body = "\n".join(lines[1:])`
   ([parsers.py:643-646](src/squadron/review/parsers.py#L643-L646)).

### Decisions

**D1 — Normalize line structure once, upstream, then run the existing parser unchanged
(Architect).** Relaxing seven constructs in place means seven chances to reopen #91 and
two parsing modes to maintain forever. A single normalization pass restores the one
property all seven assume, and every downstream construct then works for the reason it
already worked.

This is not free and the cost is stated plainly: **squadron rewrites model text before
parsing it.** Three consequences, all accepted. The normalizer must be conservative —
inserting a break where none belongs corrupts content, which is worse than failing to
parse. The `### Raw Response` section must continue to persist the **original**
response, not the normalized one, so the artifact remains evidence of what the provider
actually sent. And the run digest must disclose that normalization occurred (D4).

The offset contract is the reason normalization must happen *first* and nowhere else.
`_mask_fences` ([parsers.py:498](src/squadron/review/parsers.py#L498)) deliberately
preserves offsets — it blanks fence interiors to spaces so that `_locate_section`'s spans
index correctly into the masked string. Normalization *inserts* characters and therefore
shifts offsets. Interleaving the two would silently misalign every span. The pass runs
before `_mask_fences`, all downstream work uses the normalized string, and no existing
function's offset assumptions change.

**D2 — Three named traps the normalizer must avoid (Architect, measured 20260913).** Each
was found by running a candidate against the real specimen. Each must have its own test.

*Trap 1 — mid-run hash insertion.* A lookahead of the form `(?=#{2,6}\s*\S)` fires at the
**second** `#` of `###`, splitting it into a bogus empty level-1 heading plus a demoted
`##`. Measured effect: every finding demoted to the same level as `## Findings`, so
`_locate_section` closed the section before its first finding and returned a 1-character
span — the identical trap its own docstring documents for `### Findings`. Result: 1
finding became **0**. Insertion must anchor on the start of a complete hash run.

*Trap 2 — fused heading text.* `_HEADING_RE` captures `[^\n]*?$`, so with no break after
the heading word the entire remaining paragraph becomes the heading text
(`## SummaryPASSThe slice design is well-aligned with…`). A break before the run is
necessary but not sufficient; a break is also required after a recognized section heading
and after a finding heading's title.

*Trap 3 — `#` inside a `location:` anchor.* Locations of the form
`…918-slice.review-grounding.md#The-problem-in-one-paragraph` present a `#` that is not
a heading. Measured effect with traps 1 and 2 fixed: `total=4` finding matches but
`in_section=1`, because each anchor produced a level-1 heading that truncated the findings
section. The insertion rule must not treat a `#` that follows non-whitespace as
structural.

**D3 — Fix the verdict fusion explicitly; a newline is not enough (Architect, measured
20260913).** With a break inserted after `Summary`, `_SUMMARY_RE` on the specimen returns
**`CONCERNS`** — not the stated `PASS`, and not `UNKNOWN`. Mechanism: the pattern requires
`(PASS|CONCERNS|FAIL)\b`; the specimen reads `PASSThe`, which offers no boundary after
`PASS`, so the non-greedy `.*?` runs forward to the first bounded severity word, a
`CONCERN` inside a later finding.

This is the most dangerous single behavior in the issue and #96 does not mention it. A
wrong-but-confident verdict passes every gate and misrepresents the reviewer. The
normalizer must separate a fused verdict keyword from the word following it, and
`_extract_verdict` must not reach across a section boundary to find a keyword — a bounded
search within the summary section is the durable fix, and it is worth making independent
of the newline case since the same unbounded `.*?` scan can misfire on ordinary text.

A regression test asserting **`PASS`, not `CONCERNS`, not `UNKNOWN`** on the real
specimen is the acceptance condition for this part.

**D4 — Disclose normalization in the run digest (Architect).** 918 added
`- Response is newline-free: yes|no` ([persistence.py:206](src/squadron/review/persistence.py#L206))
and left a note at `:197` addressed to this slice. Extend that: the digest must say that
normalization ran and what it changed (a count of inserted breaks is sufficient and
cheap). Without this, a normalized parse is indistinguishable from a clean one, which is
the exact failure this slice exists to eliminate — fixing #96 by introducing a quieter
version of #97 would be self-defeating.

This also determines the Part 2 interaction: a normalized parse is a **degraded** parse,
and D6 decides whether it is degraded in the same sense as a derived verdict.

**D5 — Apply normalization only to a response detected as newline-free (Architect).**
Scoped narrowly on purpose: the trigger condition is exactly the bug's signature, the
detection is already computed (`"\n" not in raw_output`), and every response that parses
correctly today takes a byte-identical path. The cost is two behaviors to reason about,
accepted because the alternative is running a text-rewriting pass over every review
squadron has ever parsed correctly. A test must pin that a response containing newlines is
passed through untouched.

Whether a *sparsely*-broken response (line breaks present but not where the parser needs
them) should also normalize is deliberately left open — no specimen exists, and inventing
the trigger without one is how #91 happened. Revisit when one is observed.

### Where the change lands

- `review/parsers.py` — a new normalization function, called at the top of the parse
  entry point before `_mask_fences`; a bounded-search fix to `_extract_verdict`; the
  inserted-break count carried out to the result for D4.
- `review/models.py` — a field carrying the normalization fact, if D4's count is not
  derivable at render time (contrast 918's newline-free indicator, which is computed in
  `persistence.py` because `raw_output` is already in hand; an *inserted-break count* is
  not recoverable from `raw_output` alone, so this one likely needs a field).
- `review/persistence.py` — one or two digest lines.
- **Not** the review templates. See Non-goals.

The `### Raw Response` writer must be confirmed to persist the original text. If it
currently receives whatever the parser handled, it needs the unnormalized string
explicitly.

### Success criteria

1. The real specimen from `918-review.slice.review-grounding.md` parses to **verdict
   `PASS`** and **4 findings**, with each finding's `category` and `location` extracted
   and its description non-empty.
2. That specimen is a committed test fixture, so the failure cannot silently return.
3. Each of D2's three traps has a dedicated test that fails on the naive normalizer:
   `###` not split mid-run; a fused heading word separated; a `#` inside a `location:`
   anchor not treated as a heading.
4. D3's fusion case asserts `PASS` explicitly — a test asserting merely "not UNKNOWN"
   passes on the `CONCERNS` bug and is unacceptable.
5. #91 does not reopen: the existing fence-masking tests pass unchanged, and a
   newline-free response that *quotes* the finding format inside a fence yields no
   findings from the quoted text.
6. A response containing newlines produces a byte-identical artifact to today. Verified by
   the existing `clean_pass_artifact.md` snapshot guard, which must not drift except for
   intended digest lines.
7. The digest states that normalization ran and how many breaks were inserted.
8. The artifact's `### Raw Response` holds the original newline-free text.

## Part 2 — Verdict provenance in frontmatter (#97)

### What goes wrong today

The #96 run wrote `verdict: PASS` into frontmatter and it was committed. Nothing parsed
it. `_extract_verdict` returned UNKNOWN; the collapsed single finding happened to carry
`pass` severity; `_verdict_from_findings` ([parsers.py:124](src/squadron/review/parsers.py#L124))
derived PASS by most-severe-wins over that one finding.

The recovery is correct and deliberate (#28) — its docstring says it exists "only to
recover a verdict the summary parse lost." The defect is that the recovery is invisible to
the surface the gates read. 917 added a COMMIT action validating `verdict:` against the
`Verdict` enum: it checks the value is *legal*, not that it was *found*, and `PASS` is a
legal member.

Verified 20260913, and this narrows the work considerably. `fallback_used` is already set
exactly when a verdict is derived after a failed summary parse
([parsers.py:802](src/squadron/review/parsers.py#L802),
[:829](src/squadron/review/parsers.py#L829)); already serialized into `to_dict()`
([models.py:201](src/squadron/review/models.py#L201)); and already consumed in the
artifact **body** ([persistence.py:405](src/squadron/review/persistence.py#L405) renders
the "findings not parsed" section from it, `:340` folds it into `degraded`). But
`_review_frontmatter_lines` ([persistence.py:242](src/squadron/review/persistence.py#L242))
accepts no degradation parameter and emits no such key. CF's review gate reads
frontmatter. So a JSON consumer can already distinguish a derived PASS with
`verdict == "PASS" && fallback_used == true`, while CF — the consumer that actually
clears the slice — cannot.

The bias is structural, which is why a derived PASS is strictly worse than a derived FAIL:
`_verdict_from_findings` returns PASS unless it sees FAIL or CONCERN, so *any* parse
failure that drops or mangles the severe findings while leaving a benign one yields a
clean pass. That is precisely the shape #96 produced. A derived FAIL stops the loop and
gets attention; a derived PASS clears every gate silently.

### Decisions

**D6 — Emit provenance as a frontmatter key (PM, 20260913).** `verdictSource` is written
into review frontmatter with the closed vocabulary `stated | derived`.

The rationale is that the defect is an automated gate being fooled, so the fix has to
reach the surface that gate reads. Frontmatter is greppable and lets each consumer choose
its own policy: CF can treat `derived` as not-clearing, and Amoeba can decline to
auto-continue on it, without squadron dictating either. The consumer evidence on #97 (from
the Amoeba orchestrator, 20260913) asked for exactly this.

The rejected alternative — `ReviewResult` and digest only — was cheaper and needed no
cross-repo coordination, but it leaves #97's actual defect in place: no external gate can
read it, and it helps only a human who opens the file. That converts the bug into a
documentation improvement.

**Shipping it is not blocked on cf (verified 20260913).** Measured directly: a review
artifact carrying `verdictSource: derived` passes `cf validate frontmatter` with zero
findings, so cf tolerates the unknown key rather than rejecting it. Squadron can therefore
emit the key immediately, and cf adopting it is a follow-on that makes the key *useful*
rather than a precondition that makes it *safe*.

The coordination that remains is real but different in kind: until cf's review gate reads
the key, a derived PASS still clears that gate. Squadron's half closes the information gap;
CF's half closes the policy gap. File the cf issue when Part 2 lands so the key exists to
point at, and do not hold Part 2 for it.

**D7 — Carry the two-value vocabulary, not a reason string (Architect).**
`fallback_used` does not distinguish *why* the parse failed — #96's newline-free shape
and an ordinary reshaped summary both set it. A reason string would therefore need a
vocabulary, and every consumer would have to switch on it, which is string-dispatch on a
field whose values are not yet known. Emit `stated | derived` as a
closed two-value vocabulary defined once as an enum, per `CLAUDE.md`'s rule against
scattering comparison values. The *reason* stays in the digest, which is where a human
triages.

Given D4, a normalized parse that then parses a real `## Summary` verdict is `stated` —
the model did state it — with the digest disclosing normalization separately. This keeps
the two facts orthogonal: `verdictSource` answers "did the model say this?", the digest
answers "how much work did squadron do to read it?".

**D8 — The nothing-parsed branch needs nothing (verified).** `fallback_used` stays
`False` where nothing parsed at all ([parsers.py:816](src/squadron/review/parsers.py#L816),
deliberately commented). That path leaves `verdict: UNKNOWN`, which is self-announcing and
already fails closed at 917's gate and at 901's UNKNOWN-as-FAIL trigger. Emit
`verdictSource: stated` there only if it is unambiguous; otherwise omit the key, following
the established `_review_frontmatter_lines` convention that an absent optional key means
"does not apply." Decide during implementation and document which.

**D9 — 917's verdict gate is where policy is enforced, if any is (Architect).** Squadron
should record provenance and not unilaterally decide that a derived verdict fails —
consumers differ, and CF's threshold is configurable. If a squadron-side policy is wanted,
917's existing COMMIT action is the single place for it, and it should be opt-in
configuration rather than a behavior change that starts failing commits on artifacts that
pass today.

### Success criteria

1. A review whose verdict was derived emits a frontmatter key marking it as derived
   (subject to D6); one whose verdict was parsed marks it as stated.
2. The two-value vocabulary is defined once as an enum and referenced everywhere.
3. Existing artifacts remain valid — the key is additive, and its absence is meaningful
   rather than an error, consistent with `reviewedSha` and the tool-telemetry pair.
4. A test pins the #96-shaped case end to end: a mangled parse yielding a benign finding
   produces a derived marking, not a clean one.
5. The nothing-parsed branch's behavior is explicitly tested, whichever D8 chooses.
6. The `to_dict()` JSON contract and the frontmatter agree — no surface says `stated`
   while another says `derived`.
7. A cf issue is filed once the key ships, asking CF's review gate to read it. Not a
   precondition — cf tolerates the unknown key today (D6, verified) — but #97 is not
   fully closed until a consumer acts on the value.

## Part 3 — Frontmatter gate fails closed (#98)

### What goes wrong today

`frontmatter_gate.py:44` invokes `cf validate frontmatter` with the explicit staged paths
and reads **only the exit code** ([frontmatter_gate.py:61](src/squadron/events/builtin/frontmatter_gate.py#L61)).
`cf validate frontmatter` validates "only the in-root .md files among them (others are
silently skipped)", and in-root resolves against the registered project Identity path —
the default checkout. Explicit paths under a sibling git worktree are dropped silently
with exit 0.

Reproduced from two checkouts with the same throwaway file: default checkout
`filesChecked: 1`; sibling worktree `filesChecked: 0`, exit 0. Confirmed on a real tracked
document in the worktree too. So in any non-default worktree the gate hands cf every
staged path, cf checks none, exits 0, and the gate reports `squadron.frontmatter-gate: ok`
— byte-identical to a gate that checked everything and passed.

A gate whose entire purpose is to fail closed on bad frontmatter currently fails **open**,
in an environment squadron itself encourages: the project uses cf worktree contexts and
`git worktree` for parallel slice work, and initiative 380 is running in one now.

The signal exists and is ignored. Verified on the installed cf: `-j, --json` is supported
and emits `{"filesChecked": 1, "totalFindings": 0, "errors": 0, "warnings": 0, "findings": []}`.

### Decisions

**D10 — Read `filesChecked` and treat zero-against-nonempty-input as failure
(Architect).** Pass `--json`, parse the count, and fail when the staged-path list is
non-empty and `filesChecked == 0`. The message must name the likely cause, because the
operator cannot infer it from cf's silence — something to the effect of: *cf validated 0
of N staged files; in a git worktree this usually means cf resolved in-root against a
different checkout, so the gate cannot confirm frontmatter and is failing closed.*

This is the same fail-closed reasoning 917 applied to the verdict gate for unreadable
frontmatter, and 172's D6 posture that the gate's own docstring already states: *a gate
that cannot determine validity must not pass.* It holds whether or not cf#88 is fixed.

**D11 — An unreadable or absent `filesChecked` is itself indeterminate (Architect).**
Adding `--json` makes the gate depend on cf's output shape. A cf build that omits the key,
or emits unparseable JSON, must take the same fail-closed path rather than falling back to
exit-code-only behavior — a silent fallback here would reintroduce exactly the bug being
fixed, and `CLAUDE.md` forbids silent fallback values. The distinct message should say the
count could not be read, so the operator can tell a cf-version problem from a worktree
problem.

**D12 — A zero-length staged-path list is a legitimate pass (Architect).** A commit with
no staged markdown gives cf nothing to check, and `filesChecked: 0` is the correct answer.
The failure condition is zero-checked against a non-empty input list, never zero-checked
alone. This must be tested, or the fix turns every code-only commit into a gate failure.

**D13 — Expect currently-passing commits in worktrees to start failing (Architect).**
That is the point: those passes were vacuous. But it is a behavior change for anyone
committing markdown from a worktree, and it will look like a new bug to whoever hits it.
The message from D10 is what makes it self-explanatory, and it should name the workaround
(commit markdown from the default checkout, or register the worktree with cf) rather than
only the diagnosis. Worth a CHANGELOG line, since it changes when commits fail.

**D14 — Bound the `cf` subprocess with a timeout (Architect, added after slice review
20260913).** Raised as a CONCERN by the slice review, and correct: this part changes how
`frontmatter_gate.py` invokes and interprets the subprocess, so `rules/review-code.md`'s
Failure-Mode Enumeration rule requires the hang case be answered explicitly, not left
implicit. Verified on disk — `await proc.communicate()`
([frontmatter_gate.py:52](src/squadron/events/builtin/frontmatter_gate.py#L52)) has no
timeout, so a `cf` process that hangs blocks the commit indefinitely with no WARNING and
no observable signal. Adding `--json` widens the exposure slightly (more work between
spawn and exit), but the gap predates this slice.

The pattern is established in-repo and must be reused rather than reinvented —
`bash_tool.py:62` is the reference implementation: `asyncio.wait_for(proc.communicate(),
timeout=...)`, `start_new_session=True` on the spawn so the timeout path can kill the whole
process group, `_kill_process_group` to signal and reap it, and a WARNING naming the
timeout and the command. Reaping matters: a killed-but-unreaped `cf` leaves a zombie behind
every hung commit.

A hang is **indeterminate, so it fails closed** — the same posture as D11's unreadable
count and 172's D6, and for the same reason: the gate could not confirm validity. Its
message must be distinguishable from both the worktree cause (D10) and the unreadable-count
cause (D11), since the operator's next action differs in each case.

The timeout value belongs in `tools/limits.py` alongside `BASH_TIMEOUT_S` (120.0) and
`GREP_TIMEOUT_S` (5.0) rather than as a literal at the call site, per `CLAUDE.md`'s rule
against hard-coded magic defaults, and should be read at call time so a lowered limit
applies to the next invocation. `cf validate frontmatter` on a handful of staged files is
fast, so a bound far below `BASH_TIMEOUT_S` is appropriate; the exact number is an
implementation call. Note [#76](https://github.com/ecorkran/squadron/issues/76) proposes
making these constants configurable — this adds one to the same set, it does not depend on
that issue.

### Success criteria

1. In a sibling worktree, a staged markdown file makes the gate **fail** with a message
   naming the worktree cause — where today it reports `ok`.
2. In the default checkout, behavior is unchanged: valid frontmatter passes, invalid fails
   with cf's own findings.
3. A commit staging no markdown passes (D12).
4. Absent or unparseable `filesChecked` fails closed with its own distinct message (D11).
5. A hung `cf` is killed at the timeout, reaped, logged at WARNING, and fails the gate with
   a message distinct from D10's and D11's (D14). Tested with a stub that sleeps past the
   limit, asserting both the observable WARNING and that no process is left behind.
6. `squadron.review-verdict-gate` is untouched — verified independent, it reads and parses
   each staged path itself ([review_verdict_gate.py:97](src/squadron/events/builtin/review_verdict_gate.py#L97))
   and never shells out to cf.
7. Tests cover the failure modes as observable signals (WARNING log or gate error), per
   the Failure-Mode Enumeration rule in `rules/review-code.md`.

## Cross-slice dependencies and interfaces

- **917** — Part 1 must not reopen #91's fence masking (`_mask_fences`, `_locate_section`);
  Part 2 extends the verdict gate 917 added and may become where policy is enforced (D9).
- **918** — Part 1 builds on the newline-free digest indicator and the note left at
  [persistence.py:197](src/squadron/review/persistence.py#L197); the #92 non-reproduction
  is what scopes that issue out of this slice.
- **Context Forge** — Part 2 emits `verdictSource` for CF's review gate to read. Verified
  non-blocking: cf accepts the unknown key today, so squadron ships independently and CF
  adopts on its own schedule. The gap stays open until it does (see Risks).
- **Amoeba** — consumes `verdict` for routing and auto-continues on PASS; the provenance
  key is what lets it stop doing so on a derived one. Consumer, not a dependency.
- **305** — its findings-addressed gate reads findings; a parse that recovers 4 findings
  instead of 1 changes what it sees. Improvement, not a contract change.

## Risks

- **Part 1 rewrites model text before parsing it.** The mitigation is the narrow D5
  trigger (newline-free only), the conservative insertion rules of D2, D4's disclosure,
  and preserving the original in `### Raw Response`. The residual risk is a specimen whose
  content happens to look structural — the three measured traps are the known cases, and
  the fixture test is the guard.
- **Part 1 touches the parser every review passes through.** `_extract_verdict` and
  `_extract_findings` are on the path for every review type. The `clean_pass_artifact.md`
  byte-identical snapshot guard is the primary defense, plus D5 keeping the normal path
  untouched by construction.
- **Part 2's frontmatter key is a cross-repo contract.** Shipping it before cf accepts the
  key risks cf rejecting squadron's own artifacts — which would, with some irony, be
  caught by Part 3's newly fail-closed gate. Coordination is a success criterion, not an
  afterthought.
- **Part 3 will start failing commits that pass today.** By design (D13). The message
  quality is what separates "the gate works" from "the gate is broken."
- **Part 2 half-fixes #97 until context-forge reads the key.** Squadron emitting
  `verdictSource` makes a derived verdict visible; it does not stop CF's gate from clearing
  on it. That is the correct split of responsibility (D9 — squadron records, consumers
  decide), but the issue should not be closed as fixed on squadron's half alone.

## Effort

3/5 overall. Part 1 is the bulk — the normalizer is small in lines but exacting, and the
three measured traps plus the verdict-fusion fix each need their own test. Part 2 is small
in squadron (one frontmatter key, one enum, the read-back tests) and, with cf tolerance
verified, carries no blocking coordination. Part 3 is small and self-contained.

## Verification walkthrough

Draft. To be refined at Phase 6 completion from what was actually run, with corrections
stated rather than the draft quietly amended.

### Part 1 — the real specimen parses (#96)

**Run at Phase 6 completion, 20260914.** All commands below were executed against the
finished Part 1 implementation; output shown is what actually printed, not a draft
prediction.

The fixture is the `### Raw Response` section of
`project-documents/user/reviews/918-review.slice.review-grounding.md` — 3076 characters,
zero newlines (byte-identical to the committed
`tests/review/fixtures/918-newline-free-response.txt`, T1.1).

**Correction to the draft:** the draft's baseline command called `_extract_verdict` and
`_extract_findings` directly, bypassing `parse_review_output`'s normalization gate
entirely. Those two functions are intentionally *not* changed to normalize on their own —
normalization is applied once, in `parse_review_output`, before they ever see the text
(D1, D5) — so calling them directly still reproduces the pre-fix numbers even after Part 1
is complete. That is correct behavior, not a bug: it is what "normalization applied once,
upstream" means. The **before** and **after** measurements below use two different calls
for that reason; an external verifier re-running only the first would wrongly conclude
Part 1 did nothing.

Establish the pre-fix baseline (still true today, and expected to remain true — this
demonstrates the functions are unchanged, not regressed):

```bash
uv run python - << 'PY'
import re, pathlib
from squadron.review import parsers as P
t = pathlib.Path("project-documents/user/reviews/918-review.slice.review-grounding.md").read_text()
raw = t[re.search(r'^### Raw Response\s*$', t, re.M).end():].strip()
print("chars:", len(raw), "newlines:", raw.count("\n"))
print("verdict:", P._extract_verdict(raw))
f, counts, located = P._extract_findings(raw)
print("findings:", len(f), counts)
PY
```

Actual output (20260914, matches the 20260913 design measurement exactly):

```
chars: 3076 newlines: 0
verdict: Verdict.UNKNOWN
findings: 1 FindingScanCounts(total=1, in_fences=0, in_section=1, surviving=1)
```

Now the fixed state, through the real entry point (`parse_review_output`, which is where
normalization actually runs):

```bash
uv run python - << 'PY'
import re, pathlib
from squadron.review.parsers import parse_review_output
t = pathlib.Path("project-documents/user/reviews/918-review.slice.review-grounding.md").read_text()
raw = t[re.search(r'^### Raw Response\s*$', t, re.M).end():].strip()
result = parse_review_output(raw, "slice", {})
print("verdict:", result.verdict)
print("findings:", len(result.findings))
for f in result.findings:
    print(" category:", bool(f.category), "location_verified:", f.location != "unverified", "description:", bool(f.description))
PY
```

Actual output (20260914):

```
verdict: Verdict.PASS
findings: 4
 category: True location_verified: True description: True
 category: True location_verified: True description: True
 category: True location_verified: True description: True
 category: True location_verified: True description: True
```

Then confirm the guard against a wrong verdict, which is the subtlest part of this fix —
inserting only a newline after `Summary` yields `CONCERNS` if the bounded-search fix (D3)
is not in place:

```bash
uv run pytest tests/review/ -k "newline_free or verdict_fusion" -v
```

Actual: 5 passed (20260914).

And confirm #91 did not reopen, and the clean path is byte-identical:

```bash
uv run pytest tests/review/ -k "fence or snapshot or clean_pass" -v
```

Actual: 18 passed (20260914). This count includes tests unrelated to this slice (e.g.
`test_specimen_is_inside_a_fence` across every template) that happen to match the `-k`
filter — all pre-existing, none touched by this slice.

**Caveat discovered during implementation:** verifying `summary_section_located is True`
as a stated-vs-derived signal (originally suggested in T1.7) does not work — `_locate_section`
has a pre-existing, unrelated bug (filed as
[squadron#101](https://github.com/ecorkran/squadron/issues/101)) that makes it return
`None` for the "summary" section whenever the document also contains findings elsewhere,
regardless of newline-freedom. `fallback_used is False` is the correct signal instead, and
is what T1.7's test actually asserts.

### Part 2 — a derived verdict is visible where the gate reads (#97)

Construct the #96 shape — a parse that fails the summary but yields one benign finding —
and read the artifact's frontmatter rather than its JSON:

```bash
grep -E '^(verdict|verdictSource):' <the artifact>
```

Expected: `verdict: PASS` accompanied by the derived marking. Then confirm the surfaces
agree, since the whole defect was one surface knowing what another did not:

```bash
uv run pytest tests/review/ -k "provenance or verdict_source" -v
```

A real review whose `## Summary` parsed must show the stated marking — a test that only
exercises the derived side would pass with the key hard-coded.

### Part 3 — the gate fails closed in a worktree (#98)

Reproduce the vacuous pass first, from a sibling worktree, then confirm the fix. The
throwaway file must carry frontmatter that is actually invalid, so that a gate which truly
validated would fail on content rather than on the count:

```bash
# from a sibling git worktree
git worktree list                      # confirm which checkout is default
cf validate frontmatter --json <staged path>   # expect filesChecked: 0, exit 0
```

Before the fix, committing that file reports `squadron.frontmatter-gate: ok`. After, it
must fail with a message naming the worktree cause. Then the three guard cases:

```bash
uv run pytest tests/events/builtin/test_frontmatter_gate.py -v
```

covering zero-checked-against-nonempty (fails), empty staged list (passes),
absent/unparseable `filesChecked` (fails with its own message), and a hung `cf` (killed,
reaped, WARNING logged, gate fails with a third distinct message).

### Gates

```bash
uv run ruff format --check . && uv run ruff check . && uv run pyright
uv run pytest
```

Zero pyright errors is a merge blocker. The full suite baseline before this slice is
3698 passed, 4 skipped in the default checkout.
