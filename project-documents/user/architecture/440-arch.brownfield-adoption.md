---
docType: architecture
archIndex: 440
component: brownfield-adoption
initiative: brownfield-adoption
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [340, 360]
dateCreated: 20261026
dateUpdated: 20261026
status: not_started
---

# Architecture: Brownfield Adoption

## Overview

Squadron can already read an existing codebase: the understand skill (360) writes a comprehension analysis from the `understand-anything` graph, and it drafts a concept from the graph, the README and the repo's own signals. Nothing strings those steps together, and nothing hands the result to cf so the repo ends up with a plan. A user adopting a brownfield repo today has to know the order, run each step by hand, and know which cf prompt to fetch at the end.

`sq onboard` does the whole adoption, end to end, for one project directory:

1. Ask cf what the directory is (`cf detect`).
2. Hand greenfield, already-planned and opted-out directories to the normal flow, and stop.
3. Ask the PM whether to adopt. On a decline, record it with cf and stop.
4. Register the project with cf (`cf init --json`).
5. Make sure the knowledge graph exists and is current. The PM is asked once before the paid build.
6. Write the comprehension analysis (362's flow).
7. Write the concept (363's flow). The PM confirms it inside that flow.
8. Fetch cf's adoption prompt with the comprehension path, and the agent follows it to write the derived architecture and the existing-state slice plan.
9. Ask cf again. A finished adoption reports `already-planned` and hands off to `cf next`.

**Direction rule.** Squadron calls cf. cf never runs `sq`, never parses squadron output, and never names squadron's files. When cf needs a squadron artifact, squadron passes its path. cf owns its formats: the derived architecture, the existing-state slice plan and its retroactive marker. Squadron never writes those files. The agent writes them from cf's prompt.

**Scope.** The `sq onboard` command and its agent surfaces (`/sq:onboard` and the Codex skill), a typed client for the three cf calls, and retiring the cf-facing half of `sq probe`. The comprehension and concept flows are 360's and are used as they are.

## Design Goals

- **One command adopts a repo.** The user runs `/sq:onboard` and answers the PM questions. They don't need to know the order or the cf prompt's name.
- **Resumable at any point.** Every run starts from what is on disk. A step whose output already exists is skipped. Stopping after the concept and coming back a week later picks up at the adoption prompt.
- **Squadron knows only its own files.** It finds the comprehension doc by its own name and gets cf's artifacts from cf's report. It never looks for cf's files by name.
- **Nothing is overwritten without the PM.** An existing concept is kept. The graph build costs money and is asked about once.

## Architectural Principles

- **Python decides, the agent does.** The deterministic part (call cf, check versions, look at the graph, find squadron's docs, pick the next step) lives in Python as `sq onboard`. The steps that need an LLM session (build the graph, run the comprehension and concept flows, follow the adoption prompt) are done by the agent that `/sq:onboard` drives. The command loops: ask `sq onboard` for the next step, do it, ask again. The CLI, the Claude command and the Codex skill share that one Python state, so they can't disagree about where an adoption stands.

- **The state is the files.** `sq onboard` stores nothing. The current step is computed on every call from cf's report, the graph and squadron's own documents. There is no adoption state file to get out of step with the repo.

- **The project root is the given directory, as is.** `--path` defaults to the current directory and is passed to every cf call. It is not widened to the git root, so a project in a monorepo subdirectory is judged on that folder, matching cf (271 D2). The graph and the comprehension doc are looked for under that root. `sq probe`'s `project_root()` widens to the git toplevel. Onboard does not use that function.

- **Refuse what isn't understood.** cf's reports carry `reportVersion`. Squadron accepts only the version it was built for, separately for `cf detect` and `cf init`, and stops with an error naming the version on any other. An unknown `outcome` value is the same error. Nothing falls back to guessing a step.

- **One error reader.** `cf detect --json` and `cf init --json` fail with the same envelope, `{ reportVersion, error: { code, message } }`, on stdout with exit 1 (271 D5, D8). Squadron parses it in one place and shows the code and message. A failed `cf init` step is not an error object; it is the normal result with `ok: false`, and squadron lists the failed steps and stops.

## Current State

- **Comprehension (362)** and **concept (363)** are flows in `commands/analysis/understand.md`, reached as `/sq:analysis understand comprehension` and `/sq:analysis understand concept` (366). The comprehension doc is written to `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`, index 940 to 949. The concept flow needs the ai-project-guide installed and a cf registration for the project name, and stops without them. It never overwrites a concept without the PM.
- **`sq probe` (366)** reports the analysis skill, the understand plugin and the graph (present, path, build commit, commits behind HEAD) as JSON to a contract cf no longer reads. The contract is deprecated (`capability-probe-contract.md`). Its `entry`, `concept`, `graph_build` and `baseline` fields existed only for cf.
- **`ContextForgeClient`** (`integrations/context_forge.py`) runs `cf` as a subprocess, raises on a non-zero exit, and has no way to set the working directory. It reads stderr on failure, while the 271 calls put their error object on stdout.
- **cf 271** (design final at context-forge `93ee3511`, not built yet) provides `cf detect [--path] --json`, `project_detect` (MCP), `cf init --json`, and `cf prompt get <key> --path <dir> --comprehension <path>`, which appends an "Adoption Inputs" section.

## Envisioned State

`sq onboard [--path DIR] [--json]` is read-only. It runs `cf detect`, checks the graph and squadron's own documents, and reports the outcome, what already exists, and the next step with its reason. The steps are a closed set:

| Next step | When | Who does it |
|---|---|---|
| `handoff` | greenfield, already-planned, or opted-out | nobody; the report says which normal flow applies (`/cf:onboard`, `cf next`) |
| `ask-adopt` | brownfield, not registered with cf yet | agent asks the PM: `sq onboard register` on a yes, `sq onboard decline` on a no |
| `build-graph` | graph absent or stale | agent asks the PM once, then runs the plugin's `/understand` |
| `comprehension` | no comprehension doc | agent runs `/sq:analysis understand comprehension` |
| `concept` | cf reports no concept | agent runs `/sq:analysis understand concept` |
| `adopt` | the rest is in place | agent runs `sq onboard prompt` and follows its output |

A finished adoption needs no `done` step: cf reports it as already-planned, which is a `handoff` to `cf next` like any planned project. Squadron doesn't read the slice plan to tell the two apart.

Three small subcommands make the cf calls, so the agent never parses cf output itself:

- `sq onboard register` runs `cf init --json` in the root and reports the project name and each step's result. It stops on a failed step, and on `worktree-of-registered-project` it tells the user to run `cf worktree init`.
- `sq onboard decline` runs `cf config set adoption.state declined` in the root. The next `cf detect` reports opted-out.
- `sq onboard prompt` runs `cf prompt get brownfield-adoption --path <root> --comprehension <path>` with the newest comprehension doc and prints the result.

`adoption-incomplete` needs no step of its own. cf reports it when a derived architecture exists but no slice plan has a retroactive entry. The step table resolves it the same way as any other run: the earlier outputs exist, so the next step is `adopt`.

A run on a stale graph doesn't force a rebuild. The PM is told how many commits behind it is and decides. A comprehension doc older than the graph is reported but kept, because the doc says which graph commit it came from.

`sq probe` keeps no CLI command. Its graph and plugin checks become functions `sq onboard` calls, and the cf-only fields go away with the contract.

## Technical Considerations

- **The cf client needs a working directory and stdout errors.** `cf init`, `cf config set` and `cf prompt get` act on the directory they run in, and the 271 calls report failures on stdout. The client gains a `cwd` parameter and a JSON-call variant that reads the error envelope from stdout on exit 1, kept separate from today's stderr behavior so other callers don't change.

- **Registration.** `cf init` is safe to run on a registered project (`registration: existing`). `sq onboard` still checks first, so a resumed run doesn't repeat guide and command installs. Whether "registered" comes from cf's project list or from a `cf init --json` dry form is a slice decision. It must come from cf, not from squadron guessing at cf's store.

- **The graph build is the plugin's, not squadron's.** Squadron doesn't install, run or vendor `understand-anything` (360 non-goal). On `build-graph` the agent runs the plugin's own command. If the plugin isn't installed, the step says how to install it and stops.

- **Which prompt.** `brownfield-adoption` is the guide's prompt key. It is a constant in one place in squadron. If the installed guide lacks it, or its profile drops `fileComprehension`, cf's error is shown as is. There is no fallback prompt.

- **Retroactive entries in squadron's gates.** A retroactive slice-plan entry counts as complete and is never treated as reviewed (cf 260 arch). Squadron's pipeline must not start P5 or P6 on one. `cf list slices --json` already gives each entry a `retroactive` boolean (cf, since slice 263), so squadron's `SliceEntry` reads that field and never parses cf's plan format. cf's own `cf check` already errors on a retroactive entry that has a slice design or task file, so squadron's guard is a second check. The listing has no version field. The field has been stable since 263, so squadron reads it unversioned.

- **Interim guide.** Until cf 272 ships the reworked guide prompt, the installed prompt still expects the old Adoption Facts section. The live end-to-end run waits for 272 and ai-project-guide issue #47.

## Anticipated Slices

One slice. The pieces are small and only make sense together.

- **`sq onboard`.** The read-only report and step table, the three subcommands, the cf client changes, `/sq:onboard` and the Codex skill, folding the probe's graph and plugin checks in and retiring `sq probe` and its contract fields, plus a live end-to-end run on a real brownfield repo once cf 271 and 272 are released.

## Non-Goals

- **No cf-only adoption path.** cf stops on brownfield and points at `sq onboard` (271 D6).
- **No writing cf's formats.** Squadron never writes the derived architecture, the existing-state slice plan or the retroactive marker.
- **No changes to the adopted project's code or existing docs.**
- **Adoption is never mandatory.** A declined repo is worked as a new project.
- **No adoption baseline (404) in this pass.** Once `sq onboard` ships, either it offers 404 after `done` or 404 is dropped.
- **No initiative candidates in the flow.** 364 proposes forward work after adoption, as its own step the user chooses.

## Related Work

- **Initiative 360 (Document Intelligence):** the comprehension (362) and concept (363) flows, candidates (364) and routing (366). See [360-arch.document-intelligence.md](360-arch.document-intelligence.md).
- **Initiative 340 (Skill Pack Infrastructure):** the `sq:analysis` dispatcher and the analysis pack install.
- **context-forge initiative 260 and slice 271:** the detection report, `cf init --json` and adoption prompt delivery this component calls. Design at context-forge `project-documents/user/slices/271-slice.adoption-primitives-for-sq-onboard.md` (`93ee3511`).
- **Initiative 400, slice 404:** the deferred adoption baseline.
- **ai-project-guide issue #47:** guide-side adoption work, needed before the live run.
- **Initiative plan:** [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), entry 16.
