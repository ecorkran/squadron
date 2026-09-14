---
docType: review
layer: project
reviewType: tasks
slice: code-host-adapter-and-pr-target-resolution
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: ea0fca5861514c01144ae7aed6ca98a69d207377
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All success criteria trace to tasks; no gaps and no scope creep"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md:455-476"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-after-implementation pairing, and commit distribution are correct"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md"
  - id: F003
    severity: pass
    category: coverage
    summary: "I.3's \"verify both are already present\" claim checks out against the parent architecture"
    location: "architecture/380-arch.pull-request-workflow.md:56-57"
  - id: F004
    severity: note
    category: coverage
    summary: "No load/performance NFR exists in the parent, so no load test task is required"
    location: "architecture/380-slices.pull-request-workflow.md"
  - id: F005
    severity: note
    category: task-sizing
    summary: "F.5 is the densest single task in the breakdown; watch for the same splitting trigger applied to H.4/H.5"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:112-138"
  - id: F006
    severity: note
    category: coverage
    summary: "The fetch path is not parametrized over the enterprise hostname, which the design's GHE bullet lists"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:189-208"
  - id: F007
    severity: concern
    category: test-strategy
    summary: "CLI-level tests have no stated injection seam for the fake runner or the hosts fixture"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:281-294"
  - id: F008
    severity: concern
    category: documentation-consistency
    summary: "Two superseded design statements were never synced back into the design document"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md:475"
---

# Review: tasks — slice 381

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] All success criteria trace to tasks; no gaps and no scope creep

I cross-referenced each functional criterion against both task files. Six-form/enterprise parity → H.4 (CLI) and F.5 (unit); fork layout, non-GitHub mirror, and foreign-repository errors → D.3; fetch invariants, no-mutation argv, and the live unchanged-state check → G.1/G.3 plus I.1 steps 2 and 5; every-error type/log/exit coverage → H.5 (all nineteen classes, matching B.2's corrected count), F.5, G.3, and C.2; closed/merged and cross-repository resolution and fetch → F.5, G.3, and I.1; both doctor rows and the no-subprocess invariant → E.2/E.3. Technical criteria all land: ruff/pyright in every commit task, the import-graph walk in H.5, argv pinning in F.5/H.2/G.3, real-response fixtures in F.1, the 300-line rule in F.4 and the I.2 sweep, and the package re-export contract in B.1 (tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:223) verified by the I.2 sweep. Conversely, every task traces to a design anchor — including the cwd-helper extraction (A.5), which the design's fourth scope-corrections row and amended Excluded/Coordination sections now sanction, and the write operations (H.1), which the Excluded section explicitly includes.

### [PASS] Sequencing, test-after-implementation pairing, and commit distribution are correct

Parts run A→I in the design's stated Order 1–9, with the load-bearing seam (A) first and no circular dependencies (D.2 correctly takes `serves_host` as a callable so remotes never imports github_cli). Every implementation task is immediately followed by its test task: F.4→F.5, G.1/G.2→G.3, H.1→H.2, H.3→H.4/H.5, and likewise A→A.4, C.1→C.2, D.1/D.2→D.3, E.1/E.2→E.3 in the companion file. Commits are distributed at F.6, G.4, H.6 (plus A.6/B.4/C.3/D.4/E.4 in file 1) rather than batched, and H.6 correctly runs the full suite as the first point where the new command is registered. Both `sq-base` notifications precede their edits (A.5 before review.py, H.3 before app.py).

### [PASS] I.3's "verify both are already present" claim checks out against the parent architecture

Task I.3 (tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:402) instructs the implementer to verify, not re-add, the `serves_host` protocol addition and the `repo#n` grammar form in the parent arch doc. I confirmed both are present: the Design Goals protocol paragraph records "one local, read-only question added by slice 381: whether the implementation serves a given hostname" (lines 56-57), and `repo#n` appears in the Technical Considerations target-grammar paragraph (lines 186-189). The closeout instruction is accurate as written.

### [NOTE] No load/performance NFR exists in the parent, so no load test task is required

I searched the parent slice plan and the 381 design for performance, latency, throughput, load-test, or benchmark requirements and found none; the 30-second/300-second timeout constants in the tasks are functional failure-mode bounds, not performance NFRs. The absence of a `tests/load/` task is therefore correct, not a gap.

### [NOTE] F.5 is the densest single task in the breakdown; watch for the same splitting trigger applied to H.4/H.5

The part-1 review correctly split the CLI test task into H.4/H.5 for carrying too many deliverables, but F.5 (effort 4) retains a comparable load: exact-argv pinning for every read operation, env/`--hostname` assertions, the two-host parametrization with its hosts-file fixture, an eleven-case classification table, branch-resolution cases, discussion paging including the cap, and closed/merged state. All of it is one cohesive subject (test_github_cli.py) and table-driven structure is specified, so it is completable — but if it balloons during execution, the same half-done-test risk the part-1 disposition describes applies here first.

### [NOTE] The fetch path is not parametrized over the enterprise hostname, which the design's GHE bullet lists

The design's GitHub Enterprise section requires unit tests to parametrize "remote parsing, selection, resolution, identity, fetch refspecs" over `github.com` and `ghe.corp.example`. D.3 covers parsing and selection, F.5 covers resolution and identity, but G.3 has no enterprise leg. Since no git argv carries the host (the fetch names the remote, not the host, and refs.py is host-agnostic by construction), the missing leg is likely vacuous — but either add one line to G.3 saying the fetch path is host-independent and why, or strike "fetch refspecs" from the design's list, so the sweep in I.2 has something definite to check.

### [CONCERN] CLI-level tests have no stated injection seam for the fake runner or the hosts fixture

H.4 requires `sq pr show` tests through the `cli_runner` fixture with "identical scripted host responses" over two hosts, and H.4/H.5 require every error class to reach exit 1 through the CLI — all of which need the command to run against `FakeProcessRunner` rather than a real `gh`. The design (slices/381-slice.code-host-adapter-and-pr-target-resolution.md:152) says "The CLI constructs `SubprocessRunner()` and `GitHubCli(runner)`; tests construct `GitHubCli(FakeProcessRunner(...))`", and F.2 supplies `build_github_host(runner)` as "the one entry point the CLI uses" — but no task states how a CLI-level test routes the command onto the fake: patching `build_github_host`, a conftest fixture, or something else. The enterprise leg also needs the CLI's `read_gh_hosts()` to see the two-host fixture, presumably via `GH_CONFIG_DIR` as E.3 already does. Every other mechanical choice in these files is pinned down to `yaml.safe_load`; this is the one step a junior implementer must invent, and it is the mechanism the slice's headline criterion depends on. Add one bullet to H.4 naming the seam (e.g. monkeypatch `build_github_host` to return `GitHubCli(fake, hosts)` and set `GH_CONFIG_DIR` to the hosts-file fixture).

### [CONCERN] Two superseded design statements were never synced back into the design document

The design's seventh functional criterion still reads "`run_all_checks` still makes no subprocess call (existing test extended)" — but file 1's Corrections table verifies no such existing test exists, and E.3 (tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:454) now **writes** it. Likewise, the design's Testing section (slices/381-slice.code-host-adapter-and-pr-target-resolution.md:584) still lists `test_errors_observable.py` under `tests/codehost/`, while H.5 deliberately places that test in `tests/cli/test_pr_show.py` with a documented placement deviation. Both deviations are transparently documented in the task files, and the underlying work is fully covered, so this does not block execution. The inconsistency is procedural: the analogous cwd-helper correction was synced into the design (fourth scope-corrections row, amended Excluded bullet — verified present in my re-read), so a reader auditing tasks against design has no reason to expect these two lines to be stale. Apply the same treatment: amend the criterion's parenthetical and the Testing listing (or add a corrections row) so the design matches what the tasks actually build.
