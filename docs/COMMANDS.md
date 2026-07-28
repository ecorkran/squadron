# Command Reference

Complete reference for all squadron CLI commands.

## review

Run structured reviews using built-in templates.

### review arch

Run an architectural review comparing a document against an architecture reference.

```
sq review arch <INPUT_FILE> --against <ARCH_DOC> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `INPUT_FILE` | string | yes | — | Document to review |
| `--against` | string | yes | — | Architecture document to review against |
| `--cwd` | string | no | config or `.` | Working directory |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level (use `-v` or `-vv`) |
| `--output` | string | no | `terminal` | Output format: `terminal`, `json`, `file` |
| `--output-path` | string | no | — | File path (required when `--output file`) |

```bash
sq review arch slice-design.md --against hld.md -v
sq review arch spec.md --against arch.md --output json
sq review arch spec.md --against arch.md --model sonnet
```

### review tasks

Run a task plan review comparing a task breakdown against its parent slice design.

```
sq review tasks <INPUT_FILE> --against <SLICE_DOC> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `INPUT_FILE` | string | yes | — | Task breakdown file to review |
| `--against` | string | yes | — | Parent slice design to review against |
| `--cwd` | string | no | config or `.` | Working directory |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level |
| `--output` | string | no | `terminal` | Output format |
| `--output-path` | string | no | — | File path for `--output file` |

```bash
sq review tasks 105-tasks.md --against 105-slice.md -v
```

### review code

Run a code review against the current project.

```
sq review code [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | config or `.` | Project directory to review |
| `--files` | string | no | — | Glob pattern to scope the review |
| `--diff` | string | no | — | Git ref to diff against |
| `--rules` | string | no | config `default_rules` | Path to additional rules file |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level |
| `--output` | string | no | `terminal` | Output format |
| `--output-path` | string | no | — | File path for `--output file` |

```bash
# Review all code in current directory
sq review code

# Review changes against main
sq review code --diff main -v

# Review specific files with custom rules
sq review code --files "src/**/*.py" --rules rules/python.md -vv

# Output JSON
sq review code --diff main --output json > review.json
```

### review list

List all available review templates.

```
sq review list
```

No options. Outputs template names and descriptions.

## config

Manage persistent configuration.

### config set

Set a configuration value.

```
sq config set <KEY> <VALUE> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `KEY` | string | yes | — | Config key to set |
| `VALUE` | string | yes | — | Value to set |
| `--project` | flag | no | false | Write to project-level config |
| `--cwd` | string | no | `.` | Working directory (for project config location) |

```bash
sq config set cwd ~/source/repos/myproject
sq config set verbosity 1
sq config set default_rules ./rules/python.md --project
sq config set default_model opus
```

### config get

Show the resolved value of a configuration key and its source.

```
sq config get <KEY> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `KEY` | string | yes | — | Config key to read |
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config get cwd
cwd = ~/source/repos/myproject  (user)
```

### config list

Show all configuration keys with their resolved values and sources.

```
sq config list [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config list
  cwd            ~/source/repos/myproject  (user)
  default_rules  ./rules/python.md         (project)
  verbosity      0                         (default)
```

### config path

Show configuration file locations and whether they exist.

```
sq config path [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config path
  User:    ~/.config/squadron/config.toml  exists
  Project: ./.squadron.toml                not found
```

### Metrology keys

Settings for judge calibration and the tech-debt audit harness. Run
`sq config list` to see resolved values and their source.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `metrology.store_dir` | string | `~/.config/squadron/metrology` | Where records are written |
| `metrology.project_id` | string | derived from git remote | Overrides the project identity on records |
| `metrology.sample_budget` | int | 20 | Samples retained per judge configuration |
| `metrology.min_evidence_n` | int | 5 | Samples required before a recommendation is offered |
| `metrology.trend_bucket` | string | `month` | Bucket size for trend reporting |
| `metrology.graduate_match_rate` | float | 0.9 | Agreement rate at which a config is offered for graduation |
| `metrology.tighten_match_rate` | float | 0.6 | Agreement rate below which tightening is suggested |
| `metrology.residual_sample_rate` | float | 0.1 | Sampling rate retained after graduation |
| `metrology.audit_profile` | string | review default | Provider profile for audit runs |
| `metrology.audit_model` | string | *(unset)* | **Model for audit runs — see below** |
| `metrology.audit_variance_runs` | int | 3 | Runs per project in a variance series |
| `metrology.audit_timeout_s` | int | 3600 | Wall-clock cap per audit run |
| `metrology.audit_run_cooldown_s` | int | 60 | Pause between runs in a series |
| `metrology.audit_rate_limit_retries` | int | 10 | Retries before a rate-limited run gives up |
| `metrology.audit_rate_limit_cap_s` | int | 60 | Ceiling on exponential rate-limit backoff |
| `metrology.preemption_fragment_dir` | string | `~/.config/squadron/metrology/preemption` | Where `preempt generate` writes fragment files |

#### Pinning the audit model

`metrology.audit_model` is unset by default, which means squadron sends no
model to the CLI and the CLI picks its own — measured as a 1M-context Opus,
the most expensive option available, chosen silently and subject to change
when the CLI updates.

Pin it for two reasons:

- **Cost.** The default is the priciest model, selected without being asked for.
- **Comparability.** Models produce systematically different finding counts on
  identical code. Measured on one unchanged repository: Opus returned 22-30
  findings across four runs, Sonnet 5 returned 12-16. An unpinned model is not
  a fixed instrument, so a noise floor measured today is not comparable to one
  measured after the default shifts.

```bash
sq config set metrology.audit_model claude-sonnet-5 --project
```

An explicit `--model` on the command still overrides the pin. The resolved
model is stored on each record, so an audit can say what produced it.

## spawn

Spawn a new agent instance.

```
sq spawn --name <NAME> [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | yes | — | Unique agent name |
| `--type` | string | no | `sdk` | Agent type |
| `--provider` | string | no | `sdk` | Provider to use |
| `--cwd` | string | no | `.` | Working directory |
| `--system-prompt` | string | no | — | System prompt |
| `--permission-mode` | string | no | `acceptEdits` | Permission mode |
| `--model` | string | no | config `default_model` | Model override (e.g. `opus`, `sonnet`) |

## list

List running agents.

```
sq list [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--state` | string | no | — | Filter by agent state |
| `--provider` | string | no | — | Filter by provider |

## task

Send a task prompt to an agent.

```
sq task <AGENT_NAME> <PROMPT>
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `AGENT_NAME` | string | yes | Target agent name |
| `PROMPT` | string | yes | Task prompt to send |

## shutdown

Shutdown agents.

```
sq shutdown <AGENT_NAME>
sq shutdown --all
```

| Argument/Option | Type | Required | Description |
|----------------|------|----------|-------------|
| `AGENT_NAME` | string | no | Agent to shut down |
| `--all` | flag | no | Shutdown all agents |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid arguments, missing files, runtime error, unknown config key) |
| 2 | Review verdict is FAIL |
