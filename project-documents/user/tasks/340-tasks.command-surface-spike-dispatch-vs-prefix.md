---
docType: tasks
parent: 340-slice.command-surface-spike-dispatch-vs-prefix.md
slice: 340
project: squadron
dateCreated: 20260625
dateUpdated: 20260625
status: complete
---

# Tasks: Command Surface Spike — Dispatch vs. Prefix

## Context

Spike to determine whether `/sq:analysis <skill>` (single dispatcher markdown file) is a reliable command surface for skill packs, or whether prefix-per-pack (`/analysis:tech-debt`) is required. The output is a decision record and an updated arch doc — no persistent code deliverable. Spike files are removed after the decision is recorded.

Reference: `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`

---

## Tasks

### T1 — Create dispatcher markdown file

- [x] Create `commands/sq/analysis.md` in the squadron repo with the following behavior:
  - [x] Parse `$ARGUMENTS`: first word is `<skill>`, remainder is `<skill-args>`
  - [x] If `<skill>` is empty: list available skills (`tech-debt`, `understand`) and stop
  - [x] If `<skill>` is `tech-debt`: execute the tech-debt stub with `<skill-args>`
  - [x] If `<skill>` is `understand`: execute the understand stub with `<skill-args>`
  - [x] Otherwise: print `Unknown skill "<skill>". Available: tech-debt, understand.`
- [x] Verify the file is valid markdown and follows the format of existing `commands/sq/*.md` files (no YAML frontmatter, plain prose instructions)

### T2 — Create stub skill files

- [x] Create `commands/sq/analysis-tech-debt.md` — content: prints "tech-debt skill invoked with args: $ARGUMENTS" and stops. No real skill logic.
- [x] Create `commands/sq/analysis-understand.md` — content: prints "understand skill invoked with args: $ARGUMENTS" and stops. No real skill logic.

### T3 — Install spike files

- [x] Run `sq install-commands` to copy the three new files to `~/.claude/commands/sq/`
- [x] Confirm all three files are present:
  ```
  ls ~/.claude/commands/sq/analysis*.md
  ```
  Expected: `analysis.md`, `analysis-tech-debt.md`, `analysis-understand.md`

### T4 — Run test invocations and record results

Open a Claude Code session (any project directory). Run each invocation and record observed output in the `## Spike Results` section of the slice design doc.

- [x] **Test 1:** `/sq:analysis tech-debt src/`
  - [x] Expected: routes to tech-debt stub; output confirms "tech-debt skill invoked with args: src/"
  - [x] Record: did routing fire? did args arrive intact?

- [x] **Test 2:** `/sq:analysis understand src/squadron/`
  - [x] Expected: routes to understand stub; output confirms "understand skill invoked with args: src/squadron/"
  - [x] Record: did routing fire? did args arrive intact?

- [x] **Test 3:** `/sq:analysis` (no args)
  - [x] Expected: skill listing appears (tech-debt, understand)
  - [x] Record: did listing render? any confusion or error?

- [x] **Test 4:** `/sq:analysis bogus`
  - [x] Expected: unknown-skill error message
  - [x] Record: did error message appear? was it clear?

### T5 — Record decision

- [x] Before writing the verdict, verify each of the four test cases against the criteria:
  - [x] Test 1: args arrived intact (exact string `src/` passed through, not truncated or modified)
  - [x] Test 2: args arrived intact (`src/squadron/` passed through correctly)
  - [x] Test 3: listing rendered without error or confusion
  - [x] Test 4: unknown-skill error appeared and was clear
  - [x] If any test case fails the criteria, the verdict is **unreliable** — do not classify a marginal result as reliable
- [x] Open `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`
- [x] Fill in the `## Spike Results` section with all four test outcomes
- [x] State the verdict: **dispatch reliable** or **dispatch unreliable**:
  - [x] Reliable: all four pass, no context loss, no degraded UX
  - [x] Unreliable: any argument mangling, silent wrong routing, or confusing intermediate output

### T6 — Update arch doc

- [x] Open `user/architecture/340-arch.skill-pack-infrastructure.md`
- [x] Update the "open dispatch question" bullet under Architectural Principles to reflect the closed decision:
  - [x] If **reliable**: state dispatch is adopted; manifest will support `dispatch_file` option alongside `prefix`
  - [x] If **unreliable**: confirm prefix-per-pack; close the open question note
- [x] Set `dateUpdated` to today in the arch doc frontmatter

### T7 — Clean up spike files

- [x] Remove the three spike files from the repo:
  ```
  rm commands/sq/analysis.md
  rm commands/sq/analysis-tech-debt.md
  rm commands/sq/analysis-understand.md
  ```
- [x] Run `sq install-commands` again to sync the removal to `~/.claude/commands/sq/`
- [x] Confirm the files are gone — the following command must return a non-zero exit code (no matches):
  ```
  ls ~/.claude/commands/sq/analysis*.md 2>&1; echo "exit:$?"
  ```
  Expected: `ls: ... No such file or directory` with `exit:1`. If any file is still listed, the cleanup failed — do not proceed to T8.

### T8 — Mark slice complete and commit

- [x] Confirm all preconditions before marking complete:
  - [x] T5: `## Spike Results` section is filled in with a clear verdict (not blank, not "TBD")
  - [x] T6: `340-arch.skill-pack-infrastructure.md` frontmatter `dateUpdated` is set to today
  - [x] T7: `ls ~/.claude/commands/sq/analysis*.md` returns non-zero (no files remain)
  - [x] If any precondition fails, resolve it before continuing
- [x] Update `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md` frontmatter: `status: complete`, `dateUpdated: <today>`
- [x] Update `user/architecture/340-slices.skill-pack-infrastructure.md`: check off slice 340 entry (`[x]`)
- [x] Stage and commit from repo root:
  ```
  git add project-documents/user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md
  git add project-documents/user/architecture/340-arch.skill-pack-infrastructure.md
  git add project-documents/user/architecture/340-slices.skill-pack-infrastructure.md
  git add project-documents/DEVLOG.md
  git commit -m "docs: complete slice 340 — command surface spike results and decision"
  ```
