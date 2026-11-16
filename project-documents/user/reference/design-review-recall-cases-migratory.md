---
docType: reference
project: migratory
dateCreated: 20261116
dateUpdated: 20261116
status: draft
---

# Design, architecture and task review recall: candidate cases from migratory (self-verified, 2026-11-16)

Read-only pass over `/Users/manta/source/repos/manta/migratory` using `git show`, `git diff`, `git log`, `git grep` at the reviewed commit. Nothing was checked out, no model was called, no `sq` command was run, no code was executed. 15 candidates examined (all of `batch-migratory.json`). The stop rule did not trigger: 7 of the first 8 produced a valid case.

Validity rule applied (same as `design-review-recall-cases.md` and `-3.md`): a flaw counts only if, in the reviewed text, the document contradicted itself, its parent, or code in the repo at that commit, left out something its own success criteria required, or held a task that could not be completed as written. It does not count if the correction follows a later decision, scope change, new gate or capability, filled-in unspecified detail, a style or size opinion, or facts that only existed after other slices were built. Borderline items are INVALID and tagged `borderline`.

Method: no later commit proves a flaw. The saved review and the response diff were leads only. Every valid flaw below was checked by me against the reviewed document text and, where marked `code`, against the repo at the named commit. A reviewer claim I could not verify is INVALID (unproven). Each valid flaw says whether the original review raised it; the original reviewer's model (`aiModel`) is the control for those.

Labels on evidence: every item is **read** (I read the reviewed text and the code or sibling document named). Nothing is **inferred**.

Flaw types: **doc** = needs only the reviewed document, its parent, or sibling documents and the file list of the repo; **code** = needs source, config or CLI code at the reviewed commit. Tag `minor` marks a name, path or command that is wrong but would be caught at first use. Tag `coverage` marks a task file that omits a branch its parent's success criterion names.

## Totals

- Candidates examined: 15
- Cases with at least one valid flaw: 13 (100-arch, 140-arch, 300-arch, 100-slice, 102-tasks, 109-slice, 113-slice, 141-slice, 146-slice, 149-slice, 152-slice, 304-slice, 313-tasks)
- Cases with no valid flaw: 2 (117-tasks, 300-slice)
- Valid flaws: 31 (15 need only documents, 16 need code at the reviewed commit)
- Minor-tagged among the valid: 15 (7 doc, 8 code); without them: 16 strong flaws (8 doc, 8 code)
- Original review raised: 10 of 31. Not raised by the original reviewer: 21 (verified by me; these are misses for the model named in each section).
- Source of the 10 raised: 100-arch 2, 140-arch 1, 300-arch 3, 102-tasks 1, 109-slice 1, 146-slice 1, 152-slice 1.
- Invalid or unproven: about 70 reviewer findings and candidate items (about 20 tagged borderline).
- Original reviewer models: claude-sonnet-4-6 (100-arch, 300-arch), z-ai/glm-5.1 (140-arch, 146, 149, 152), minimax/minimax-m2.7 (100-slice, 113, 117, 141, 300-slice), z-ai/glm-5 (102-tasks, 109, 304, 313-tasks).
- Seven reviews with verdict PASS (100-slice, 102-tasks, 109, 113, 141, 304, 313-tasks) cover a document with a valid flaw verified here. Two reviews affirm the opposite of a verified flaw in writing (113 F002, 146 F006), and 149 F006 does so for an item I kept INVALID (borderline): negative controls listed per case.

## Caveats

1. **Review commit is often later than the reviewed text.** In 100-arch, 300-arch and 102-tasks the review file was committed after the author had already edited the document, so the batch's `reviewedText` (the review commit) is not the text the reviewer saw. I used the last commit whose text still contains what the review quotes: 100-arch `40ad72f^`, 300-arch `ecd8f65^`, 102-tasks `6d86232^`. Details in each section.
2. **146, 149, 152: the committed design differs from the reviewed one.** Each review quotes text that the committed design no longer has (146 F002, 149 F001/F002, 152 F001 partly), so the author edited the design before committing it with the review. The reviewed text is not in git. I verified flaws only in the committed text and say where the reviewer plainly saw the same text.
3. **117-tasks and 313-tasks sit next to finished code.** Their task files were written before implementation, but at the reviewed commit the code already exists. For code claims in 313 I used the code before the implementing commit (`97c3bc4^`) as the baseline and the implementation diff only as supporting evidence.
4. **300-slice has no code at its reviewed commit** (the world-server code lived in a sibling worktree), so it could only be checked against documents.
5. **Shell note:** with zsh write `git show "${C}:path"`; `$C:path` is read as a modifier.

---

## 1. migratory-100-arch

- repo migratory; `project-documents/user/architecture/100-arch.behavior-engine.md`; kind arch
- reviewed-at: `40ad72f^` (= `09dd31b`). Review `reviews/100-review.arch.behavior-engine.md`, CONCERNS, **claude-sonnet-4-6**, 10 findings (2 FAIL, 6 CONCERN, 2 PASS). The review was committed in `44917ac`, after the response commit `e58b01a`, and the batch's reviewedText `44917ac` already holds the corrected document. The review's line numbers (81 and 122) and its quotes match `09dd31b`; the broken link was fixed one minute later in `40ad72f`. `09dd31b` itself changed the Scope paragraph (tick loop ownership); whether the reviewer saw that change is unknown, so I did not count the Scope text.
- response commit: `e58b01a` "docs: address arch review findings for 100-arch.behavior-engine" (read)
- flaws:
  - Related Work links `200-arch.world-server-foundation.md`. At `09dd31b` the repo holds `300-arch.worldserver-foundation.md` and no 200-arch file. **VALID** (minor): contradicts repo. Needs: doc (file list). Raised by the original review (F-1; the review also says the slice plan has the same link).
  - Envisioned State says the narrow interface is "tick the simulation forward, query agent state, register/remove agents", while the same section says the engine is stateless between ticks and all state lives in the arrays the caller passes. There is nothing in the engine to register into. **VALID**: self-contradiction. Needs: doc alone. Raised by the original review. The response removed the phrase and gave lifecycle to the world server (as 300-arch already did).
  - F "spatial query interface never defined", F "stateless engine, nobody owns the spatial index", F "aggregate shape vs individual neighbors", F "profile interaction rules have no representation", F "per-tick array allocation", F "GPU path vs per-profile branching". INVALID: each is an unspecified detail the response then filled in (a minimal contract, index ownership, an interaction matrix, `out=` buffers, index-based dispatch). None contradicts the text, a parent or code. The GPU item is not a contradiction either: the document says "no Python-level per-agent branching", and table lookups are not that.
  - F "swarm needs writes, but the environment is read-only". INVALID (borderline): the concept (`000-concept` line 30) says paths are "reinforced through use", but nothing says the engine writes; the environment layer could reinforce paths from agent traffic and leave the engine read-only. The response added an admission, not a fix to a contradiction.
  - "Current State: No engine exists". INVALID (borderline): code for the engine exists at this commit, but only because slices 100/101 were built after the document was written.
  - The two PASS findings (SoA layout, float32/float64 boundary). Not flaws; they hold.

## 2. migratory-140-arch

- `project-documents/user/architecture/140-arch.simulation-scaling.md`; arch
- reviewed-at: `fc7b39c^` (= the document before the response commit, so the exact text the reviewer saw: the review file was added by the response commit). Review `reviews/140-review.arch.simulation-scaling.md`, CONCERNS, **z-ai/glm-5.1**, 11 findings. The review file in the tree has an appended Responses section the reviewer did not write.
- response commit: `fc7b39c` "docs: add simulation scaling slice plan and arch review responses" (read)
- flaws:
  - Current State: "The wire protocol is currently uncompressed JSON over WebSocket ... 84 KB/tick (24 bytes x 3,500 agents)", and Tier 2: "Binary WebSocket replaces JSON". At `fc7b39c^` `src/migratory_server/protocol.py` builds every message with `struct.pack` and `positions.tobytes()` (lines 184-213, 280-369) and ships bytes; `project-documents/reference/terrain-wire-protocol-v2.md` documents the binary format. The 24 bytes (6 x f32) is the binary size. **VALID**: contradicts code. Needs: code. Raised by the original review (F006: "24 bytes cannot be JSON, either the byte count or the format is wrong"; the author answered that the format claim was stale). The reviewer did not know which half was wrong, but did raise the inconsistency.
  - Related Work says `100-arch.behavior-engine.md` "Defines the `SpatialQuery` protocol, `BulkForce` interface, CSR edge representation, and profile-driven force model". At `fc7b39c^` 100-arch contains none of `SpatialQuery` (it speaks of a "neighbor-query interface"), `CSR`, or a `BulkForce` interface (one passing mention of a "BulkForce pattern"). Those live in code and slice designs 100, 110 and 111. **VALID** (minor): contradicts a referenced document. Needs: doc alone. Not raised by the original review.
  - F001 "Tier 2 bundles a big-bang transition" (the principle says each tier is independently deployable). INVALID (borderline): a tier read as a milestone is not self-contradictory, and the response only clarified the prose.
  - F002 "tick return type decision deferred", F003 "no memory budget", F004 "no desync recovery", F010, F011. INVALID: a decision, an added analysis, added failure modes, or detail deferred to a slice design.
  - F005 "baseline numbers inconsistent" (57 TPS at N=3,500 beside a per-tick budget measured at N=2,492). INVALID (borderline): the document names the source of the breakdown (journal Entry 8, N=2492); the journal has no 3,500 point, but the wording is a conflation, not a contradiction. The journal's own table (106 TPS ceiling, about 59 live at N=2492, about 79 at N=2500) is internally uneven, which is the journal's flaw.
  - F007 "biome shading is scope creep". INVALID: the Scope excludes "viewer/client rendering optimization", and shading is not an optimization; a focus opinion.
  - F008 "single-vendor dependency, weak fallback". INVALID: opinion; the author rejected it as a deliberate research choice. Negative control.
  - F009 "same code, different backend understates the port". INVALID: the document describes a future Numba reference that does not exist yet at this commit (slice 118 is "anticipated"), so nothing in the repo contradicts it.
  - The Envisioned State sentence "tick() -> state arrays is preserved at every tier" against Tier 4 "the tick return type contract determines whether position data exits the GPU at all". INVALID (borderline): the contract is the document's open item.

## 3. migratory-300-arch

- `project-documents/user/architecture/300-arch.worldserver-foundation.md`; arch; its frontmatter `dependsOn` includes `100-arch.behavior-engine`, so 100-arch is its parent
- reviewed-at: `ecd8f65^`. Review `reviews/300-review.arch.worldserver-foundation.md`, CONCERNS, **claude-sonnet-4-6**, 8 findings. The review was committed in `717200a` after the response work (`ecd8f65`, `09dd31b`, `40ad72f`, `0ea672a`). The review quotes `tick.py` lines 83-92 as they were before `ecd8f65` and the unfixed links, so the reviewed text is the document before `ecd8f65` (the batch's `717200a` text has all findings addressed). A separate response file, `reviews/300-response.arch.worldserver-foundation.md`, was written by claude-opus-4-6.
- response commits: `ecd8f65`, `09dd31b`, `40ad72f`, `0ea672a` (read; the response file maps each finding to its commit)
- flaws:
  - 100-arch (the parent) Scope lists "the simulation tick loop" and says "the engine owns what happens between ticks"; 300-arch Overview says the world server owns "the tick loop" and its Tick as transaction loop calls the engine; 100-arch's own Envisioned State describes the engine as a callee of the world server. **VALID**: contradicts its parent. Needs: doc alone (both documents at the commit). Raised by the original review. The fix landed in 100-arch.
  - Frontmatter `dependsOn: [001-concept.migratory, ...]` and Related Work link `../project-guides/001-concept.migratory.md`. At `ecd8f65^` the repo holds only `000-concept.migratory.md`. **VALID** (minor): contradicts repo. Needs: doc (file list). Raised by the original review.
  - Tick loop and asyncio coexistence: "run the tick synchronously, then yield to the async event loop for I/O between ticks ... without the tick loop starving I/O", while Tick end says to sleep for the remainder "or log an overrun warning". `src/migratory_server/tick.py` at `ecd8f65^` calls `await asyncio.sleep(remaining)` only in the non-overrun branch; on overrun it logs and starts the next tick with no `await`, so a sustained overrun never yields. The document's overrun path contradicts its own constraint, and the code does exactly that. **VALID**: contradicts itself and code. Needs: code. Raised by the original review (the first FAIL).
  - "Handle entity lifecycle events ... queued during the tick" with no source or queue anywhere. INVALID (borderline): the response says no runtime event source exists yet; an unspecified future facility, not a contradiction.
  - "WebSocket library unspecified, absent from `pyproject.toml`". INVALID: a detail the response filled in; the dependency belongs to slice 305.
  - "Protocol extensibility asserted, no type byte". INVALID (borderline): opinion about a future need; the document says only "should not preclude".
  - "Persist state on shutdown has no slice". INVALID (borderline): the slice plan lists it as Future Work; the response scoped the sentence.
  - "Scaling section is too long". INVALID: style and size opinion.
  - The two PASS findings (tick as transaction, engine boundary). They hold.

## 4. migratory-100-slice

- `project-documents/user/slices/100-slice.agent-state-and-tick-function.md`; kind slice (design)
- reviewed-at: `1392106`. Review `reviews/100-review.slice.agent-state-and-tick-function.md`, **PASS**, **minimax/minimax-m2.7**, 10 PASS findings, no CONCERN. The design has not changed since `3bd5723` (the commit just before the review), so this is the reviewed text. No code exists at this commit (the implementation is `05626ea`).
- response commit: none (the review stood; the slice was completed in `05626ea`)
- flaws:
  - Force Protocol: "The tick loop prefers the bulk variant when available", and Success Criteria: "Placeholder forces exercise both the `Force` and `BulkForce` protocol paths". The only `tick` signature in the document is `forces: list[BulkForce]`; no sentence says how a per-agent `Force` reaches `tick()`, and a tick that prefers the bulk variant "when available" must accept both. **VALID** (minor): self-contradiction between prose and signature. Needs: doc alone. Not raised (the review passed the "Force protocol design"). The implementation at `05626ea` kept `forces: list[BulkForce]` and never added the per-agent dispatch.
  - Brute-force `SpatialQuery.query_radius` returns indices only, while the architecture's later "minimal contract" returns indices and squared distances. INVALID: that sentence was added to the architecture after this review.
  - BulkForce returns zeros for inactive agents "so integration adds force to velocity for all", beside Data Flow step 6 "inactive agents' state is untouched". INVALID (borderline): the parenthesis says nothing about positions, and the integration section applies only to active indices.
  - Per-agent `query_radius` loop beside "no Python-level per-agent loops in the hot path". INVALID (borderline): the success criterion restricts that rule to force accumulation and integration; a later slice (110) batched the query.
  - The reviewer's praise (PASS findings) for correct serialization boundary and determinism holds. No negative control found.

## 5. migratory-102-tasks

- `project-documents/user/tasks/102-tasks.herding-and-leadership.md`; tasks. Parent design: `slices/102-slice.herding-and-leadership.md` at the same commit.
- reviewed-at: `6d86232^` (= `593afcb`). Review `reviews/102-review.tasks.herding-and-leadership.md`, **PASS** (one CONCERN), **z-ai/glm-5**. The batch's `5d0772a` is the review commit; `6d86232` (before it) added the vectorization sub-items the review's single CONCERN asked for, so the reviewer saw the text before it.
- response commit: `6d86232` "docs: add vectorization verification to herding force tasks" (read; 4 inserted lines)
- flaws:
  - Task 2.1 adds two required fields to `BehavioralProfile`, and Task 2.2 updates test call sites only ("search for `BehavioralProfile(` across `tests/`"). At `6d86232^` the production call site `src/migratory_server/simulation.py:18` (`build_profiles`) also constructs `BehavioralProfile` with the six existing fields, fed from `ProfileConfig` in `src/migratory_server/config.py`. After Task 2.1 that call raises `TypeError`, every server test that builds profiles fails, and the "all existing tests still pass" check in 2.2 and 6.1 cannot be met. No task touches `migratory_server`. The parent slice design says the same ("all existing tests must be updated"). **VALID**: the tasks cannot be completed as written. Needs: code. Not raised. The implementing commit `55364da` changed `config.py` and `simulation.py` as well (and added defaults to `ProfileConfig`), which no task or design line mentions.
  - Slice design Technical Requirement 1: "both forces are vectorized within each agent's neighborhood". No task checks or enforces it (the tasks' sketches loop per agent with scalar NumPy calls). **VALID** (`coverage`, minor): the tasks omit verification a success criterion names. Needs: doc (design plus tasks). Raised by the original review (its only CONCERN); the response added the source-inspection checks.
  - Task 3.1's MomentumForce sketch (force along the current heading scaled by speed) gives positive speed feedback rather than "resisting turning". INVALID: the parent design chose that form explicitly (Option A).
  - The review's PASS findings on coverage, sequencing and commit checkpoints hold. No negative control found.

## 6. migratory-109-slice

- `project-documents/user/slices/109-slice.force-computation-vectorization.md`; slice (design)
- reviewed-at: `c43cd20` (the design was committed one minute earlier in `96fbbf2`; unchanged between). Review `reviews/109-review.slice.force-computation-vectorization.md`, **PASS**, **z-ai/glm-5**, 6 PASS and 1 NOTE.
- response commit: none; the slice was implemented in `b6a2eb7`..`c8df256` and closed in `f252659` (which only fills in results and changes the walkthrough grep)
- flaws:
  - Architecture, Vectorized Force Patterns, Cohesion sketch: `center_of_mass = np.sum(neighbor_pos, axis=1) / np.maximum(counts, 1)` then `cohesion = (center_of_mass - self_positions) * weights`. For an agent with zero neighbors the sum is the zero vector, so the force is `-self_position * weight`, not zero. The section "Handling Zero-Neighbor Agents" says the masked reduction "produces zero force for that agent, matching current behavior". **VALID**: self-contradiction. Needs: doc alone. Not raised (the review passed the design). The implementation had to add `forces[~has_neighbors] = 0.0` (`flocking.py` at `f252659`).
  - Verification Walkthrough step 4 runs `grep -n "for.*agent_idx\|for.*eval_indices\|for.*list_idx"` on the force modules and expects no matches, while the design's own Per-Agent Profile Weight pattern is `np.array([... for pi in state.profile_indices[eval_indices]])` in those modules. The regex `for.*eval_indices` matches that line, so the step cannot return empty if the design is followed. **VALID**: the step cannot be completed as written. Needs: doc alone. Not raised. At close the author rewrote the grep.
  - Technical Scope and Success Criteria call all five forces "neighbor-dependent" and include `MomentumForce`, which the document later says "does not use neighbors at all". **VALID** (minor): self-contradiction. Needs: doc alone. Raised by the original review (its only NOTE, "wording inconsistency").
  - Excluded section: "vectorizing the spatial query loop is 105's scope" and "When slice 105 introduces a batch query". The slice plan describes 105 as a hash grid "behind the existing query interface" and has no batch query. INVALID (borderline): 105 was not started and its design could take the work; `ce88ad2` repointed it to a new slice 110, a later decision.
  - "Python-level per-agent loops: none" against the weight-array list comprehension the design prescribes. INVALID (borderline): the document acknowledges and justifies that comprehension, and the closing note restates it as "weight-array one-liner".
  - Data Flow step 5 omits `active_indices` in the `integrate(...)` call. INVALID: illustrative pseudo-code.

## 7. migratory-113-slice

- `project-documents/user/slices/113-slice.adaptive-spatial-dispatch.md`; slice (design)
- reviewed-at: `a0b2418` (design and review added together; no earlier commit). Review `reviews/113-review.slice.adaptive-spatial-dispatch.md`, **PASS**, **minimax/minimax-m2.7**, 6 PASS findings.
- response commit: none; implementation and closeout in `8ed2760` (it changed the design only to record results and defer walkthrough steps)
- flaws:
  - The density signal is described three times as "the CSR's raw `counts` output ... pre-cap", "`filtered_counts` (post-`exclude_self`, pre-cap)", and `record_density(filtered_counts)` as step 8, after the force and integrate steps. In `src/migratory/engine/tick.py` at `a0b2418`, `filtered_counts` is reassigned by `apply_neighbor_cap` whenever any profile has `max_neighbors > 0`, so at step 8 it is the capped count. With the cap on (the `test.yaml` run the walkthrough names has `max_neighbors=1`), mean density is at most 1, below the default threshold of 10, so the dispatcher is pinned to grid, the opposite of the stated "the cap cannot perturb backend selection" (Non-Risks). **VALID**: contradicts code. Needs: code. Not raised; the review affirms the opposite (below). The implementation added `pre_cap_counts = filtered_counts` before the cap (`tick.py` at `8ed2760`).
  - Technical Decisions: "Make it configurable (`initial_backend: "brute"` by default) so an operator can choose grid-first", while `SpatialConfig` has three fields and `_build_spatial` passes `initial_backend="brute"`. INVALID (borderline): "exposed at construction" in Included reads as a constructor parameter only.
  - Development Approach step 5 asks for "bit-exact position equality" against brute force across a run that uses both backends, while the document says grid neighbor order may differ. INVALID (borderline): rests on float summation order, which I did not verify; the implemented test pinned brute and used `allclose`.
  - Walkthrough steps 2 and 5 rely on an env var (`MIGRATORY_SPATIAL_BACKEND`) and a `grid_selected` log count that no section introduces. INVALID: unspecified detail; the document hedges the env var as "an implementation detail".
  - Negative control: F002 of the review says the signal is "explicitly documented as reading pre-cap density, ensuring `apply_neighbor_cap` cannot perturb backend selection". The review accepted the document's claim without reading `tick.py`.

## 8. migratory-117-tasks

- `project-documents/user/tasks/117-tasks.kd-tree-spatial-backend.md`; tasks. Parent design `slices/117-slice.kd-tree-spatial-backend.md`.
- reviewed-at: `6818b8c^`. Review `reviews/117-review.tasks.kd-tree-spatial-backend.md`, CONCERNS, **minimax/minimax-m2.7**, 6 findings. The file at this commit already has T1-T10 checked and the implementation exists; the response commit only checked off T11-T21 and set `status: complete`.
- response commit: `6818b8c` (read; checkbox changes only)
- flaws (none valid):
  - F001 "uneven commit checkpoints; T14 has no commit listed, only T11 and T21 do". INVALID: process opinion, and partly false. T14 lists a commit (`feat: add "kdtree" as a valid spatial backend option`), as do T1, T3, T6, T8, T9, T10, T11 and T21. Negative control.
  - F002 "walkthrough names `test_all_backends_parity`, T11 names other tests". INVALID (borderline): the design says "New test name ... May also be added as a parametrisation of the existing brute-vs-grid parity test", so T11's extension satisfies it, though the walkthrough command would not find that name.
  - T5 note: `cKDTree.query_ball_point` is `<=` and the other backends are `<`; T6 case 2 asserts radius 0 returns self, which strict `<` would not. INVALID (borderline): T5 names the difference and defers to parity tests; the implementation kept `<=` and documented it.
  - T9 "`cKDTree.query` returns shape `(m, k)`": for `k=1` scipy squeezes the last axis. INVALID (unproven): library behavior, not in repo; the tick path passes `k+1 >= 2`.
  - Slice design walkthrough step 5 uses `migratory-server ... --ticks 100`; the CLI has no `--ticks` flag at this commit. INVALID for this case: the flaw sits in the parent design, not in the reviewed task file.
  - The remaining PASS findings (criteria coverage, no scope creep, sequencing, granularity) hold.

## 9. migratory-141-slice

- `project-documents/user/slices/141-slice.cross-platform-benchmark-harness.md`; slice (design)
- reviewed-at: `3c5e6c7` (design, review and the first implementation commit together; the design is unchanged from its creation in the same commit). Review `reviews/141-review.slice.cross-platform-benchmark-harness.md`, **PASS**, **minimax/minimax-m2.7**, 8 PASS findings.
- response commit: none; implementation finished in `9a58abf` with `bench/workloads/*.yaml`
- flaws:
  - Workload schema: `world_size: [200.0, 200.0, 200.0]`, `cluster_centers: [[60,60,60],[140,140,140]]`, "initializes one `AgentState` per workload". `src/migratory/__init__.py` at `3c5e6c7` has `DIMS = 2` and `AgentState` arrays are N x 2. The checked-in workloads ended up 2D (`[200.0, 200.0]`, `[60.0, 60.0]`). **VALID**: contradicts code. Needs: code. Not raised.
  - "A single registered backend: `numpy` (today's `engine.tick.tick` ...)" and "the NumPy backend (the only backend that exists today)", while Numba is a later one-row addition. At `3c5e6c7` `engine/_jit_config.py` sets `USE_JIT_KERNELS = True` and every force in `flocking.py` and `herding.py` dispatches to `forces_jit` kernels by default, so `tick()` as called by the harness runs the Numba kernels; the design never says the `numpy` runner must turn the flag off, and the implemented `numpy_backend.py` does not touch it. The report's "numpy" rows would be Numba timings and the parity "golden" hash would come from the JIT path. **VALID**: contradicts code. Needs: code. Not raised. (Moderate confidence: the design also says a Numba runner would delegate to `forces_jit` "via the engine's existing JIT-config flag", which shows awareness of the flag but not the consequence.)
  - Workload section: profile names resolve to "the existing `BehavioralProfile` constructors used in `config/default.yaml`. The harness does not invent new profiles". `config/default.yaml` has one profile, `default`; `flocker` and `leader` exist nowhere (the implementation's own comment calls `leader` "a derived profile"). **VALID** (minor): contradicts repo. Needs: code. Not raised.
  - "Force names resolve to module-level singleton instances in the relevant engine modules (e.g. `flocking.cohesion_force`)". No such instances exist; forces are classes (`CohesionForce`), and the implementation builds its own registry of instances. **VALID** (minor): contradicts code. Needs: code. Not raised.
  - Consumes from Other Slices: "`engine.spatial.KDTreeQuery`", while Interfaces Required says `migratory.spatial`; the class is `migratory.spatial.kd_tree.KDTreeQuery`. **VALID** (minor): self-contradiction plus code. Needs: code. Not raised.
  - The per-phase table names `csr_assembly` where 140-arch's table says `self_excl_cap (CSR assembly)`. INVALID: wording.
  - "1100 passed, 2 skipped" and the CLI examples. INVALID (unproven): not checkable without running.

## 10. migratory-146-slice

- `project-documents/user/slices/146-slice.production-engine-gpu-adoption.md`; slice (design)
- reviewed-at: `1f0521c` (design, tasks and review added together). Review `reviews/146-review.slice.production-engine-gpu-adoption.md`, CONCERNS, **z-ai/glm-5.1**, 8 findings. The committed design is not the text the reviewer saw (see caveat 2): F002 describes a production-to-bench dependency "acknowledged in Open Notes as a pragmatic tradeoff", while the committed Open Notes say `GpuAgentState` moves to `src/migratory/gpu/` as the first step.
- response commit: none separate (the design was edited before the commit); closed in `a6abc41`
- flaws:
  - Scope and A7: "falls back to CPU with a logged warning if neither [Metal nor CUDA] is detected", "A host with no Metal and no CUDA starts successfully with `backend: quadrants`". The `_select_arch()` listing returns `qd.cuda` for every Linux host and `qd.metal` for every Darwin host and falls back only for other platforms; Open Notes say a failing `qd.init()` propagates and the server exits. A Linux box without CUDA is the case A7 names, and it crashes. **VALID**: self-contradiction. Needs: doc alone. Raised by the original review (F001, quoting this text).
  - GpuAgentState Changes: "`export_positions()` and `export_velocities()` return f64 arrays (Quadrants upcasts on download). The `TickResult` therefore carries f64"; A3 requires the same dtype contract as the CPU path. At `1f0521c`, `quadrants_fused_state.py` declares `export_positions() -> NDArray[np.float32]` and returns `.astype(np.float32)`, and `TickResult.from_quadrants_fields` passes arrays through with no dtype change (its docstring says f32 stays f32). The design lists no change to the export methods. **VALID**: contradicts code. Needs: code. Not raised (the review's F006 PASS repeats the claim). Still f32 at `a6abc41`.
  - Files Changed and Task text name `src/migratory_server/entity_manager.py`; the module is `entities.py` and no `entity_manager.py` exists. **VALID** (minor): contradicts repo. Needs: code (file list). Not raised.
  - Walkthrough "Regression: `uv run pytest tests/server/ tests/bench/`" and the new `tests/server/test_gpu_driver.py`: the test tree is flat (`tests/test_server.py`, `tests/test_simulation.py`, ...; subfolders are `bench`, `forces`, `load`, `manual`, `spatial`), so `tests/server/` holds only the new file and the run does not cover the existing server tests that `SimulationManager` changes can break. **VALID** (minor): contradicts repo. Needs: code. Not raised. At close the author replaced the command with the flat test files.
  - Walkthrough step 2: `uv run python -m migratory_server config/default.yaml`. `__main__.py` accepts `--config`, `--replay`, `--world` and no positional argument. **VALID** (minor): the step fails as written. Needs: code. Not raised. The same text stayed in the closed walkthrough.
  - F003 "failure modes not enumerated", F005 "NFR not restated". INVALID: added analysis.
  - F004 "tests 5-8 call `setup()` under the document's own one-`qd.init()`-per-process warning". INVALID (borderline): the Open Notes state the isolation requirement; the Testing list leaves the mechanism open.
  - F002 production-to-bench dependency. INVALID for the committed text (the document moves the class first).
  - Negative control: F006 PASS accepts "export returns f64 arrays".

## 11. migratory-149-slice

- `project-documents/user/slices/149-slice.neighbor-scan-early-exit-and-cell-subdivision.md`; slice (design)
- reviewed-at: `dcbb53a` (design, tasks and reviews added together). Review `reviews/149-review.slice.neighbor-scan-early-exit-and-cell-subdivision.md`, CONCERNS, **z-ai/glm-5.1**, 6 findings. As in 146, the committed design already has the S-validation paragraph and the NFR restatement that F001 and F002 ask for, so the reviewed text is not in git.
- response commit: none separate; closeout `1f7ccd7`
- flaws:
  - Intervention 2: "With S=3 alone: candidates loaded drops to ~5000", beside the same section's "(2S+1) x (2S+1) = 7 x 7 scan" and "agents/cell about 555". Seven by seven cells of about 555 agents is about 27,000 candidates, not about 5,000; 5,000 is the S=1 occupancy of one cell. The "both interventions: ~555 candidates loaded" figure inherits the same error. **VALID** (minor): self-contradiction in the numbers that motivate the gate. Needs: doc alone. Not raised.
  - Verification Step 3 lists four runs (baseline, early exit only, subdivision only, both) as pairs of identical commands, and F006's PASS says "both interventions are toggleable independently". The design makes the early-exit `break` unconditional and gives no switch. INVALID (borderline): the walkthrough is labelled a draft "to be refined", and the baseline can come from the slice-145 build.
  - Walkthrough commands use `scripts/bench.py --subdivision-factor/--N/--parity-check`; the harness is `python -m migratory.bench --workload --backend`. INVALID (borderline): same draft label.
  - F001 "no failure modes for S", F002 "NFR not restated", F003 "148 not in dependencies". INVALID: filled-in detail, or already addressed in the committed text.
  - Negative control: F006 PASS "the verification walkthrough tests each combination separately" and "both interventions are toggleable independently" are not what the design says.
  - Checked and consistent: kernel line references (seam at 155-184, `for kk` at 291, `build_spatial_hash` at 411) match `quadrants_fused_kernels.py` at `dcbb53a`; the 1.67x figure follows from 100/60.

## 12. migratory-152-slice

- `project-documents/user/slices/152-slice.coherent-grid-for-k-nearest-neighbor-search.md`; slice (design)
- reviewed-at: `4b2edc8` (design and review v1 added together). Review `reviews/152-review.slice.coherent-grid-for-k-nearest-neighbor-search.md`, CONCERNS, **z-ai/glm-5.1**, 6 findings. The review file in the tree was also touched by later commits (`19a944f` onward are task and measurement commits for the same slice); the version used is the one added by `4b2edc8`.
- response commit: none separate (`19a944f` adds "updated slice 152 design, review, tasks")
- flaws:
  - Overview: "at the architecture's Tier 3 target (N=200k)" and "our current Tier 3 milestone of 200k". `140-arch` (Tier 3 "250k") and `140-slices` ("Tier 3 (250k, NVIDIA CUDA ...)") both say 250k; 200k appears only in this slice. **VALID**: contradicts its parent and the architecture. Needs: doc alone. Raised by the original review (F001).
  - Technical Scope item 7 and Technical Decisions: `k_first` "is removed entirely from the kernel", configs using it "raise a `ConfigurationError`", "no silent migration". Risk Mitigation: "ship the two new modes alongside the legacy `k_first` value (still parsed, with a deprecation warning) ... flip the default and remove `k_first` parsing in the final commit"; Default flip: change the default from `"k_first"` to `"k_nearest"` as the last commit. But Development Approach step 2 rewrites the inner loop to the two-mode form (`if radius_only ... else k_nearest`), which has no `k_first` branch, while the default and the accepted values still say `k_first` until step 4. Between those commits a default config would silently run `k_nearest`, the silent migration the design forbids. **VALID**: self-contradiction. Needs: doc alone. Not raised.
  - Walkthrough steps 2-5 use `python -m migratory.bench parity ...` and `python -m migratory.bench run ... --neighbor-mode ... --ticks`. `bench/cli.py` at `4b2edc8` has no subcommands and no `--neighbor-mode` or `--ticks` option (only `--workload`, `--backend`, `--workload-dir`, `--results-dir`, `--list-*`), and the slice adds none. **VALID** (minor): the steps cannot run as written. Needs: code. Not raised.
  - Success path raises `ConfigurationError`; the config module defines `ConfigError`. **VALID** (minor): contradicts code. Needs: code. Not raised.
  - F002 "absolute TPS not restated". INVALID: added analysis.
  - Criterion 3 says "no pass/fail", then "slice-stop bug" if the baseline is not beaten; walkthrough 3 says radius-only does "strictly less work" than early-exit k_first. INVALID (borderline): the first is wording; the second is a performance claim I cannot check from the repo (and the design itself says radius-only evaluates every in-radius candidate).
  - `config/x-fractal.yaml` is not in the repo. INVALID (unproven): it may live in the user's config directory.

## 13. migratory-300-slice

- `project-documents/user/slices/300-slice.server-bootstrap-and-configuration.md`; slice (design)
- reviewed-at: `e848c5c` (the design is unchanged since `5a1d72c`). Review `reviews/300-review.slice.server-bootstrap-and-configuration.md`, **PASS**, **minimax/minimax-m2.7**, 9 PASS findings. No code exists at this commit (no `src/`), so only documents could be checked.
- response commit: none
- flaws (none valid):
  - Review claim: the architecture specifies configuration covering "tick rate, world geometry, entity capacity, network binding, logging". INVALID as a reviewer claim (negative control, minor): 300-arch lists "entity population definitions ... environment parameters" and does not list entity capacity in that sentence; the slice omits populations and environment parameters. Not a flaw in the slice: the slice plan assigns population-driven creation to 302 and environment parameters to 304, and the design says unknown fields are ignored for forward compatibility.
  - Design checks that held: dependencies and interfaces match the slice plan (301, 302, 303, 304, 305), validation rules match the schema, the frozen dataclasses match the fields, unknown-field behavior is stated consistently.
  - The `migratory-world-server` directory and "sibling worktree" wording. INVALID: true of the worktree layout at the time.

## 14. migratory-304-slice

- `project-documents/user/slices/304-slice.environment-layer-integration.md`; slice (design)
- reviewed-at: `6e2d822` (design added in `4cb381f`, review committed with `6e2d822`; document unchanged between). Review `reviews/304-review.slice.environment-layer-integration.md`, **PASS**, **z-ai/glm-5**, 6 PASS findings.
- response commit: none
- flaws:
  - "SimulationManager Extension" shows `step()` with `if self._entity_manager.count == 0: return` before `tick(...)`, so `post_tick()` is skipped when there are no entities. The note directly below ("`post_tick()` is called even when there are no entities ... the early return is moved to wrap only `engine.tick()`"), the first `step()` listing under "SimulationManager as Simulation Orchestrator", and Special Considerations all say the opposite. **VALID**: self-contradiction. Needs: doc alone. Not raised. The implementation followed the note.
  - Checked against code and consistent: `Environment(bounds, layers)`, `pre_tick(tick_number, seasonal_parameter)` with range check, `post_tick()` with optional arguments, `WorldBounds` fields, `EnvironmentQuery.zeros`, the server's existing `step()`/`tick_body` call sites, and the `Spawned %d entities` log line.
  - Default `seed: 42` against the "no silent defaults" convention stated in slice 300's design. INVALID (borderline): a convention of a sibling slice, and the document states the default openly.
  - "Fixed 0.0 seasonal parameter produces a mid-season environment". INVALID (unproven): meaning of 0.0 is defined by later layer slices.

## 15. migratory-313-tasks

- `project-documents/user/tasks/313-tasks.world-bounds-policy.md`; tasks. Parent design `slices/313-slice.world-bounds-policy.md` (status complete at this commit).
- reviewed-at: `b5bd8bc^`. Review `reviews/313-review.tasks.world-bounds-policy.md`, **PASS**, **z-ai/glm-5**, 5 PASS and 1 NOTE. At this commit the tasks file has `status: complete` but unchecked boxes; the response commit only checked boxes. The text is the original task breakdown; the implementation (`97c3bc4`..`cb9ed00`) already existed.
- response commit: `b5bd8bc` "docs: add slice 313 review docs and update task status" (read; checkbox changes only)
- flaws:
  - Success Criterion 5 and Task 1.4 require `config_to_yaml` to round-trip the new `policy` field, and the design says "`StrEnum` subclasses `str` so `yaml.dump` will serialize it as a plain string automatically". `config_to_yaml` at `97c3bc4^` is `yaml.dump(dataclasses.asdict(config), ...)`; `asdict` leaves the `StrEnum` instance in place, and `yaml.dump` does not write a `str` subclass as a plain string (it emits a Python object tag, which the loader's `yaml.safe_load` rejects). No task changes `config_to_yaml` (the "Files touched" list shows only `config.py` enum, field and loader changes), so the round-trip test in 1.4 cannot pass as written. **VALID**: the task cannot be completed as written. Needs: code. Not raised (the review lists SC5 as covered by 1.3-1.4). Evidence: the implementing commit `97c3bc4` had to add `_serialize_for_yaml` and call it from `config_to_yaml`. I confirmed the repo side (the unmodified `config_to_yaml` and `safe_load` at line 580); the PyYAML behavior rests on my knowledge of the library, supported by that fix.
  - Task 3.4 "step once, assert `vx < 0`" for an agent at `(99, 50)` with velocity `(10, 0)` gives no `dt`. INVALID: unspecified detail.
  - `np.mod` of a tiny negative float can return exactly `width`, outside the half-open range of SC7. INVALID (unproven): numerical edge, beyond what the documents or repo show.
  - Checked and consistent: success criteria 1-14 map to tasks as the review says; `_VALID_LOG_LEVELS`, `valid_config_dict`, `tmp_config_file`, `build_world_bounds` and the `Forces wired` log line exist at the baseline.

---

## Notes for building the benchmark from these

- 31 valid flaws, 15 document-only and 16 needing code. Only 10 were raised by the original reviewer, so this batch is mostly a recall test: 21 flaws that a model with the document and repo tools could find but that these original reviewers missed or passed.
- The strongest cases (each has a flaw that changes behavior or blocks a task): 113 (post-cap signal drives dispatch), 313-tasks (round-trip cannot pass), 102-tasks (production call site breaks), 109 (cohesion sketch gives a nonzero force; walkthrough grep cannot be empty), 146 (f32 export vs promised f64 TickResult; fallback missing on Linux), 300-arch (overrun path starves the loop), 140-arch (JSON vs binary), 304 (post_tick skipped on empty), 141 (3D schema in a 2D engine; "numpy" runner is the JIT path).
- Weakest valid items (drop them for a strict set): the 15 `minor` flaws (wrong file name, path, class name, command, wording, arithmetic, the `coverage` item in 102-tasks).
- The saved reviews that affirm the opposite of a verified flaw are the best negative controls: 113 F002, 146 F006, 149 F006 (the last for an INVALID-borderline item). Other useful controls: 117 F001 (T14 does list a commit), 300-slice's misquote of the architecture config list, 140 F008 (author-rejected).
- Cases that need the parent document alongside the reviewed one: 300-arch (100-arch at `ecd8f65^`), 140-arch (100-arch at `fc7b39c^`), 102-tasks (slice 102 design), 152 (`140-arch` and `140-slices`), 313-tasks (slice 313 design). Cases that need the repo tree or code at the commit: all `code` items above; for the CLI items (146, 152) the `__main__.py` or `bench/cli.py` argument parsers suffice.
- Reviewed text is not in git for 146, 149 and 152 (design edited after the review ran), and the batch's `reviewedText` commit is not the reviewed text for 100-arch, 300-arch and 102-tasks. Use the `reviewed-at` values here.
