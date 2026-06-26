---
docType: tasks
parent: 340-slice.command-surface-spike-dispatch-vs-prefix.md
slice: 340
project: squadron
dateCreated: 20260625
dateUpdated: 20260625
status: not_started
---

# Tasks: Command Surface Spike — Dispatch vs. Prefix

## Context

Spike to determine whether `/sq:analysis <skill>` (single dispatcher markdown file) is a reliable command surface for skill packs, or whether prefix-per-pack (`/analysis:tech-debt`) is required. The output is a decision record and an updated arch doc — no persistent code deliverable. Spike files are removed after the decision is recorded.

Reference: `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`

---

## Tasks

### T1 — Create dispatcher markdown file

- [ ] Create `commands/sq/analysis.md` in the squadron repo with the following behavior:
  - Parse `$ARGUMENTS`: first word is `<skill>`, remainder is `<skill-args>`
  - If `<skill>` is empty: list available skills (`tech-debt`, `understand`) and stop
  - If `<skill>` is `tech-debt`: execute the tech-debt stub with `<skill-args>`
  - If `<skill>` is `understand`: execute the understand stub with `<skill-args>`
  - Otherwise: print `Unknown skill "<skill>". Available: tech-debt, understand.`
- [ ] Verify the file is valid markdown and follows the format of existing `commands/sq/*.md` files (no YAML frontmatter, plain prose instructions)

### T2 — Create stub skill files

- [ ] Create `commands/sq/analysis-tech-debt.md` — content: prints "tech-debt skill invoked with args: $ARGUMENTS" and stops. No real skill logic.
- [ ] Create `commands/sq/analysis-understand.md` — content: prints "understand skill invoked with args: $ARGUMENTS" and stops. No real skill logic.

### T3 — Install spike files

- [ ] Run `sq install-commands` to copy the three new files to `~/.claude/commands/sq/`
- [ ] Confirm all three files are present:
  ```
  ls ~/.claude/commands/sq/analysis*.md
  ```
  Expected: `analysis.md`, `analysis-tech-debt.md`, `analysis-understand.md`

### T4 — Run test invocations and record results

Open a Claude Code session (any project directory). Run each invocation and record observed output in the `## Spike Results` section of the slice design doc.

- [ ] **Test 1:** `/sq:analysis tech-debt src/`
  - Expected: routes to tech-debt stub; output confirms "tech-debt skill invoked with args: src/"
  - Record: did routing fire? did args arrive intact?

- [ ] **Test 2:** `/sq:analysis understand src/squadron/`
  - Expected: routes to understand stub; output confirms "understand skill invoked with args: src/squadron/"
  - Record: did routing fire? did args arrive intact?

- [ ] **Test 3:** `/sq:analysis` (no args)
  - Expected: skill listing appears (tech-debt, understand)
  - Record: did listing render? any confusion or error?

- [ ] **Test 4:** `/sq:analysis bogus`
  - Expected: unknown-skill error message
  - Record: did error message appear? was it clear?

### T5 — Record decision

- [ ] Before writing the verdict, verify each of the four test cases against the criteria:
  - Test 1: args arrived intact (exact string `src/` passed through, not truncated or modified)
  - Test 2: args arrived intact (`src/squadron/` passed through correctly)
  - Test 3: listing rendered without error or confusion
  - Test 4: unknown-skill error appeared and was clear
  - If any test case fails the criteria, the verdict is **unreliable** — do not classify a marginal result as reliable
- [ ] Open `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`
- [ ] Fill in the `## Spike Results` section with all four test outcomes
- [ ] State the verdict: **dispatch reliable** or **dispatch unreliable**:
  - Reliable: all four pass, no context loss, no degraded UX
  - Unreliable: any argument mangling, silent wrong routing, or confusing intermediate output

### T6 — Update arch doc

- [ ] Open `user/architecture/340-arch.skill-pack-infrastructure.md`
- [ ] Update the "open dispatch question" bullet under Architectural Principles to reflect the closed decision:
  - If **reliable**: state dispatch is adopted; manifest will support `dispatch_file` option alongside `prefix`
  - If **unreliable**: confirm prefix-per-pack; close the open question note
- [ ] Set `dateUpdated` to today in the arch doc frontmatter

### T7 — Clean up spike files

- [ ] Remove the three spike files from the repo:
  ```
  rm commands/sq/analysis.md
  rm commands/sq/analysis-tech-debt.md
  rm commands/sq/analysis-understand.md
  ```
- [ ] Run `sq install-commands` again to sync the removal to `~/.claude/commands/sq/`
- [ ] Confirm the files are gone — the following command must return a non-zero exit code (no matches):
  ```
  ls ~/.claude/commands/sq/analysis*.md 2>&1; echo "exit:$?"
  ```
  Expected: `ls: ... No such file or directory` with `exit:1`. If any file is still listed, the cleanup failed — do not proceed to T8.

### T8 — Mark slice complete and commit

- [ ] Confirm all preconditions before marking complete:
  - T5: `## Spike Results` section is filled in with a clear verdict (not blank, not "TBD")
  - T6: `340-arch.skill-pack-infrastructure.md` frontmatter `dateUpdated` is set to today
  - T7: `ls ~/.claude/commands/sq/analysis*.md` returns non-zero (no files remain)
  - If any precondition fails, resolve it before continuing
- [ ] Update `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md` frontmatter: `status: complete`, `dateUpdated: <today>`
- [ ] Update `user/architecture/340-slices.skill-pack-infrastructure.md`: check off slice 340 entry (`[x]`)
- [ ] Stage and commit from repo root:
  ```
  git add project-documents/user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md
  git add project-documents/user/architecture/340-arch.skill-pack-infrastructure.md
  git add project-documents/user/architecture/340-slices.skill-pack-infrastructure.md
  git add project-documents/DEVLOG.md
  git commit -m "docs: complete slice 340 — command surface spike results and decision"
  ```
