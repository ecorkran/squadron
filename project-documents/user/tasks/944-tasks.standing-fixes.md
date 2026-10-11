---
docType: tasks
slice: standing-fixes
project: squadron
lldReference: project-documents/user/slices/944-slice.standing-fixes.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Standing container for multi-step fixes. Add a task group per issue.
status: in_progress
dateCreated: 20261011
dateUpdated: 20261011
---

# Tasks: Standing Fixes

## #189 Pipelines merge slices with unchecked task boxes

- [x] Merge refuses unchecked task items; close-out dispatch added to the implement body (e602d4e5)
- [x] Guide wording (ai-project-guide v0.20.8)

## #200 Failed dispatch in a revise loop still merges

- [x] A failed dispatch ends the loop with the loop's `on_exhaust` status (451644ac)
- [ ] `ProviderError` prints as one line, not a traceback
- [ ] An unusable SDK session is replaced with a fresh one, and the replacement is logged
- [ ] The run's final status says which steps succeeded (including the merge) when a later step fails
