---
docType: review
layer: project
reviewType: code
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: c85beb2d702dc43fc194085d0dae47286cb805c2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 79339
cachedTokens: 3232
cacheWriteTokens: 76105
completionTokens: 3555
durationSeconds: 34.9
costUsd: 0.346213
costBasis: provider
squadronVersion: 0.23.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Cost cap fails open on an unreadable usage record"
    location: "src/squadron/pipeline/run_spend.py#RunSpend.add"
  - id: F002
    severity: concern
    category: testing
    summary: "No load or concurrency test for the shared `RunSpend` tally"
    location: "tests/pipeline/test_executor_cost_cap.py"
  - id: F003
    severity: concern
    category: design
    summary: "Tests patch private methods to isolate behaviour"
    location: "tests/conftest.py:138-150"
  - id: F004
    severity: note
    category: style
    summary: "Redundant and loosely typed checks in turn handling"
    location: "src/squadron/pipeline/sdk_turns.py#DispatchTurns.collect"
  - id: F005
    severity: note
    category: style
    summary: "`assert isinstance` used for type narrowing in an event action"
    location: "src/squadron/events/builtin/blocked_tasks.py#BlockedTasksAction.execute"
  - id: F006
    severity: note
    category: design
    summary: "Resume flag lifecycle relies on mutate-and-pop of the shared params dict"
    location: "src/squadron/pipeline/executor.py:625-657"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Parser, config validation and failure-kind plumbing"
    location: "src/squadron/pr/tasks.py#parse_blocked_markers"
---

# Review (fixture: frontmatter copied verbatim, body omitted)
