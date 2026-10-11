---
docType: slice-design
slice: standing-fixes
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261011
dateUpdated: 20261011
status: in_progress
review: none
---

# Slice Design: Standing Fixes

## Overview

A permanent container for fixes. It is never "done": when a fix is too big to just make, add tasks for it to the task file and work them here. Closed or complete items in it are reopened freely. The fixes in it need not be related.

## Rules

- A small fix that needs no tasks is made directly and committed as `fix:` with `Fixes #n`. It is not recorded here.
- A fix that needs several steps becomes a task group in [944-tasks.standing-fixes.md](project-documents/user/tasks/944-tasks.standing-fixes.md), titled with its issue number.
- Work is committed on the target branch. No slice branch, no design, no review (`review: none`).
- If the fix needs a new user-facing option, a changed file or state format, or a new component, it is a feature and gets its own slice.
