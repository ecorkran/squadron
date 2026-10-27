---
docType: slice-plan
parent: 440-arch.brownfield-adoption.md
project: squadron
dateCreated: 20261026
dateUpdated: 20261026
status: not_started
---

# Slice Plan: Brownfield Adoption

## Parent Document
`440-arch.brownfield-adoption.md`: Architecture: Brownfield Adoption

## Planning Context
Architecture-level. The cf contract is fixed: context-forge slice 271's design is final at `93ee3511`, and the squadron session confirmed its names and shapes on 20261026. 271 is not built yet. This slice can be designed and built against the design while cf builds 271. Its live run needs 271 and 272 released, plus ai-project-guide issue #47.

One slice, as the architecture says. The report, the step table, the subcommands and the agent surfaces don't stand alone, and splitting them would ship a command that can't finish an adoption.

---

## Feature Slices

1. [x] **(440) sq onboard**: `sq onboard [--path DIR] [--json]` reports the outcome, what exists and the next step from the architecture's closed step table, and writes nothing. `sq onboard register`, `decline` and `prompt` make the three cf calls (`cf init --json`, `cf config set adoption.state declined`, `cf prompt get brownfield-adoption --path --comprehension`). `/sq:onboard` and a Codex skill drive the agent through the loop. `ContextForgeClient` gains a working directory and a JSON call that reads cf's error envelope from stdout. The probe's graph and plugin checks fold into onboard. The `sq probe` command and its cf-only fields are removed, and `capability-probe-contract.md` is marked superseded by this slice.
   - **Value:** One command takes an existing repo from nothing to a plan cf can navigate, and it can be stopped and resumed at any step.
   - **Success Criteria:**
     - `sq onboard` runs on an unregistered directory and leaves it unchanged (tree, `.context-forge.toml` and cf's project store compared before and after).
     - Each of cf's five outcomes maps to the step the architecture's table names, in a test per outcome with recorded cf JSON.
     - An unknown `reportVersion`, from `cf detect` or `cf init`, and an unknown `outcome` each stop with an error that names the value. A cf error envelope is shown with its code and message, from one parser used for both commands.
     - `sq onboard register` stops and lists the failed steps when `cf init --json` returns `ok: false`. On `worktree-of-registered-project` it tells the user to run `cf worktree init`.
     - `sq onboard decline` makes the next `cf detect` report opted-out.
     - `sq onboard prompt` passes the newest comprehension doc and the root as `--path`. With no comprehension doc it stops instead of fetching the prompt.
     - An existing concept is never regenerated. A resumed run on a repo with a comprehension doc and a concept goes straight to `adopt`.
     - The project root is the given directory, not the git root, in a monorepo subdirectory test.
     - Live: on a real brownfield repo, `/sq:onboard` runs from detect to `already-planned`, and `cf next` then points at the first unbuilt slice.
   - **Dependencies:** [366], context-forge 271 (design final; built and released before the live run), context-forge 272 and ai-project-guide #47 (before the live run).
   - **Interfaces:** Consumes `cf detect --json`, `cf init --json` and `cf prompt get --path --comprehension` (271 D3, D5, D7, D8), and the comprehension and concept flows (362, 363). Provides `sq onboard` and `/sq:onboard`. Retires `sq probe`.
   - **Risk:** Medium. The cross-repo contract is designed but not built, so recorded cf JSON in tests can drift from what cf ships. The live run is the check.
   - **Effort:** 3/5

---

## Integration Work

- **Retroactive entries in squadron's gates.** Squadron must not start P5 or P6 on a retroactive slice-plan entry. `cf list slices --json` already carries `retroactive: bool` per entry. `SliceEntry` gains the field and the pipeline refuses such an entry with an error naming it. This is part of slice 440.

## Notes

- 404 (adoption baseline) stays deferred. After 440 ships, either `sq onboard` offers it after adoption or 404 is dropped.
- 364 (initiative candidates) stays outside the onboard loop. It is a separate step the user runs after adoption.
