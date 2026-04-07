---
slice: pypi
project: squadron
lld: user/slices/117-slice.pypi.md
dependencies: [sq-slash-command]
projectState: Slice 116 complete. CLI entry points `sq`/`squadron` working. Wheel bundles command files via force-include. pyproject.toml has name, version (0.1.0), description, readme, requires-python, dependencies, scripts, build-system. Missing classifiers, license field, project-urls. No CI workflow. No --version flag.
dateCreated: 20260307
dateUpdated: 20260313
status: complete
docType: tasks
---

## Context Summary

- Working on `pypi` slice — publish squadron to PyPI for global install
- Slice 116 (Claude Code Commands) is complete; wheel bundling works
- `pyproject.toml` has basic metadata but needs classifiers, license, project-urls
- CLI app has no `--version` flag
- No GitHub Actions CI workflow exists
- README has a Quickstart section but no global install instructions
- Both `claude-agent-sdk` (on PyPI) and the `squadron` name (available) are confirmed
- Next planned slice: 118 (Composed Workflows)

---

## Tasks

### T1: Add `--version` flag to CLI

- [x] Add a `version_callback` function and `@app.callback()` to `src/squadron/cli/app.py`
  - [x] Use `importlib.metadata.version("squadron")` for the version string
  - [x] Output format: `squadron X.Y.Z`
  - [x] `--version` is an eager option (fires before any subcommand)
  - [x] Refer to slice design "Version Output" section for implementation pattern
  - [x] `sq --version` prints version and exits with code 0
  - [x] `sq squadron --version` also works (both entry points)

### T2: Test `--version` flag

- [x] Add test(s) in `tests/cli/test_version.py`
  - [x] Test `sq --version` via `CliRunner` — assert output contains `squadron` and a version string
  - [x] Test that version matches `importlib.metadata.version("squadron")`
  - [x] Test exit code is 0
  - [x] `pytest` passes, `pyright` clean, `ruff` clean

### T3: Commit — version flag

- [x] Commit T1-T2 work
  - [x] Message: `feat: add --version flag to CLI`

### T4: Add `pyproject.toml` metadata

- [x] Update `pyproject.toml` `[project]` section
  - [x] Add `license = {file = "LICENSE"}`
  - [x] Add `classifiers` list per slice design (Development Status :: 3 - Alpha, Environment :: Console, Intended Audience :: Developers, License :: OSI Approved :: MIT License, Programming Language :: Python :: 3, Programming Language :: Python :: 3.12, Programming Language :: Python :: 3.13, Topic :: Software Development :: Quality Assurance, Topic :: Software Development :: Testing, Typing :: Typed)
  - [x] Add `[project.urls]` section with Homepage, Repository, Issues pointing to the GitHub repo
  - [x] Verify existing fields are correct (name, version, description, readme, requires-python)
  - [x] Run `uv sync` to confirm pyproject.toml parses correctly

### T5: Verify wheel metadata

- [x] Build wheel and verify metadata includes new fields
  - [x] Run `hatch build` (or `uv run hatch build`)
  - [x] Inspect the built wheel (zipfile or `unzip -l`) — confirm `METADATA` file contains classifiers, license, project-urls
  - [x] Confirm `commands/` directory is still included in the wheel (force-include from slice 116)
  - [x] Clean up dist/ after verification

### T6: Commit — metadata polish

- [x] Commit T4-T5 work
  - [x] Message: `package: add classifiers, license, and project-urls to pyproject.toml`

### T7: Create GitHub Actions CI workflow — test job

- [x] Create `.github/workflows/ci.yml` with the `test` job
  - [x] Trigger on push to `main` and pull requests to `main`, and on `v*` tags
  - [x] Python version matrix: 3.12, 3.13
  - [x] Use `actions/checkout@v4`
  - [x] Use `astral-sh/setup-uv@v4`
  - [x] Steps: `uv python install`, `uv sync --dev`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest`
  - [x] Refer to slice design "GitHub Actions Workflow" section for the full YAML structure

### T8: Create GitHub Actions CI workflow — publish job

- [x] Add the `publish` job to `.github/workflows/ci.yml`
  - [x] Runs only on `v*` tags: `if: startsWith(github.ref, 'refs/tags/v')`
  - [x] Depends on `test` job: `needs: test`
  - [x] Set `permissions: id-token: write` for OIDC trusted publisher support
  - [x] Steps: checkout, setup-uv, install Python, sync, `hatch build`
  - [x] Upload to TestPyPI first with `skip-existing: true`
  - [x] Upload to PyPI
  - [x] Uses `pypa/gh-action-pypi-publish@release/v1`
  - [x] Refer to slice design "GitHub Actions Workflow" section for the full YAML

### T9: Commit — CI workflow

- [x] Commit T7-T8 work
  - [x] Message: `chore: add GitHub Actions CI workflow`

### T10: Update README with install instructions

- [x] Update `README.md` with global install section
  - [x] Add an "Install" section before the existing "Quickstart" section
  - [x] Include "Global install (recommended)" with `pipx install squadron` and `uv tool install squadron`
  - [x] Include post-install examples: `sq --version`, `sq install-commands`, `sq review code --diff main -v`
  - [x] Add "Development install" subsection with clone + `uv sync --dev`
  - [x] Rework existing Quickstart to avoid duplicating install steps (reference the Install section or remove redundant install info)
  - [x] Refer to slice design "README Install Section" for content

### T11: Commit — README updates

- [x] Commit T10 work
  - [x] Message: `docs: add global install instructions to README`

### T12: Validation pass

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass
  - [x] `sq --version` outputs correct version
  - [x] `hatch build` produces a valid wheel with correct metadata
  - [x] `.github/workflows/ci.yml` exists with both `test` and `publish` jobs
  - [x] README contains global install instructions

### T13: Commit — validation pass

- [x] Commit any fixes from T12
  - [x] Message: `chore: slice 117 validation pass`
  - [x] Skip commit if no changes needed

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [x] **PyPI account setup**: Create account at pypi.org, configure trusted publisher for the GitHub repo (or generate API token and add as `PYPI_API_TOKEN` secret)
- [x] **TestPyPI account setup**: Create account at test.pypi.org, configure similarly
- [x] **First publish**: Bump version if needed, tag `v0.1.0`, push tag, verify CI publishes successfully
- [x] **Smoke test**: `pipx install squadron` from PyPI, verify `sq --version`, `sq --help`, `sq install-commands --target /tmp/test`
