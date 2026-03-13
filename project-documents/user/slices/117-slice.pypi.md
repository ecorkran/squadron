---
docType: slice-design
slice: pypi
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [sq-slash-command]
interfaces: []
dateCreated: 20260306
dateUpdated: 20260313
status: complete
---

# Slice Design: PyPI Publishing & Global Install

## Overview

Publish the `squadron` package to PyPI so users can install globally via `pipx install squadron` or `uv tool install squadron`, making `sq` available on PATH without venv activation. This is the delivery mechanism that makes slices 1-116 usable by anyone with a Python toolchain.

## Value

Currently, using squadron requires cloning the repo and activating a virtualenv. Publishing to PyPI removes that friction entirely. A single `pipx install squadron` gives users the `sq` binary on PATH, and `sq install-commands` (slice 116) works from the global install because the wheel already bundles command files via `force-include`.

This also establishes the release infrastructure (CI workflow, version management) that all future slices benefit from — every subsequent feature ships automatically on the next tag.

## Technical Scope

### Included

- Version strategy decision (SemVer) and implementation
- `sq --version` / `squadron --version` CLI output
- `pyproject.toml` metadata polish: classifiers, license, project-urls, `readme` field
- GitHub Actions CI workflow: lint + test on push/PR, publish to PyPI on version tag
- TestPyPI dry-run step in CI (validates packaging before real publish)
- README install instructions for `pipx` and `uv tool`
- LICENSE file reference in pyproject.toml (already exists as MIT)

### Excluded

- Custom version bumping tooling (manual tag workflow is sufficient at this scale)
- Changelog generation (DEVLOG serves this role for now)
- Homebrew formula or other non-Python distribution channels
- Signed releases / Sigstore attestations (can be added later)
- PyPI trusted publisher setup via OIDC (recommended but can be done as a follow-up if token-based publish works first)

## Dependencies

### Prerequisites

- **Claude Code Commands (slice 116)** (complete): `commands/` directory and `force-include` in pyproject.toml. Ensures `sq install-commands` works from a wheel install.

### External Services

- **PyPI account**: Owner must create a PyPI account and generate an API token (or configure trusted publisher). Token stored as a GitHub Actions secret (`PYPI_API_TOKEN`).
- **TestPyPI account**: Separate account/token for dry-run publishes (`TEST_PYPI_API_TOKEN`).
- **GitHub Actions**: Repository must have Actions enabled.

## Technical Decisions

### Version Strategy: SemVer

SemVer (`MAJOR.MINOR.PATCH`) is the standard for Python packages and what PyPI/pip tooling expects. CalVer was considered but offers no advantage for a package that doesn't have time-based release commitments.

- Start at `0.1.0` (already set in pyproject.toml — this is correct for pre-1.0 software)
- Bump minor for feature slices, patch for fixes
- The version lives in one place: `pyproject.toml`'s `version` field
- `sq --version` reads the version at runtime via `importlib.metadata`

### Version Output

Add a `--version` callback to the Typer app:

```python
import importlib.metadata

def version_callback(value: bool) -> None:
    if value:
        print(f"squadron {importlib.metadata.version('squadron')}")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Multi-agent squadron CLI."""
```

No hardcoded version string — `importlib.metadata.version()` reads from the installed package metadata, which hatchling populates from `pyproject.toml`.

### pyproject.toml Metadata

Fields to add or update:

```toml
[project]
name = "squadron"
version = "0.1.0"
description = "Multi-agent squadron framework"
readme = "README.md"
license = {file = "LICENSE"}
requires-python = ">=3.12"
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Quality Assurance",
    "Topic :: Software Development :: Testing",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/manta/squadron"
Repository = "https://github.com/manta/squadron"
Issues = "https://github.com/manta/squadron/issues"
```

The `readme = "README.md"` is already present. The `license` field and `classifiers` are new. `project.urls` is new.

### GitHub Actions Workflow

Two jobs in a single workflow file (`.github/workflows/ci.yml`):

**Job 1: `test`** — Runs on every push and PR to `main`.
- Checkout, setup Python 3.12 + 3.13, install with `uv`
- `ruff check`, `ruff format --check`
- `pyright`
- `pytest`

**Job 2: `publish`** — Runs only on version tags (`v*`).
- Depends on `test` job passing
- Build with `hatch build`
- Upload to TestPyPI first (catch packaging errors)
- Upload to PyPI
- Uses `pypa/gh-action-pypi-publish` action (standard, maintained by PyPA)

```yaml
name: CI

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install ${{ matrix.python-version }}
      - run: uv sync --dev
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run pyright
      - run: uv run pytest

  publish:
    needs: test
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # for trusted publisher (OIDC)
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.12
      - run: uv sync
      - run: uv run hatch build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
          skip-existing: true
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### Release Process

Manual, tag-driven:

1. Update `version` in `pyproject.toml`
2. Commit: `package: bump version to X.Y.Z`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`
5. CI runs tests, then publishes to TestPyPI and PyPI

No release-please, no automatic version bumping. This is appropriate for the project's current pace and team size.

### README Install Section

Add a section before the current "Quickstart" that covers global install:

```markdown
## Install

### Global install (recommended)

```bash
# Using pipx (recommended)
pipx install squadron

# Or using uv
uv tool install squadron
```

After install, `sq` is available on PATH:

```bash
sq --version
sq install-commands   # Install Claude Code slash commands
sq review code --diff main -v
```

### Development install

```bash
git clone https://github.com/manta/squadron.git
cd squadron
uv sync --dev
```
```

## Integration Points

### Provides to Other Slices

- **All future slices**: Established CI pipeline runs tests on every push. New features are automatically validated.
- **All future slices**: Tag-based publish means any merged feature can be released by tagging.

### Consumes from Prior Slices

- **Slice 116**: `force-include` in `pyproject.toml` ensures command files are in the wheel.
- **Slice 115**: Package name is `squadron`, entry points are `sq` and `squadron`.

## Success Criteria

### Functional Requirements

- `sq --version` outputs `squadron X.Y.Z`
- `pip install squadron` (or `pipx install squadron`) from PyPI succeeds
- After global install: `sq --help`, `sq review code --help`, `sq install-commands` all work
- `sq install-commands` correctly locates bundled command files from the wheel
- GitHub Actions CI runs lint + test on push to main
- GitHub Actions publishes to PyPI on version tag push
- TestPyPI upload succeeds before PyPI upload (catches packaging errors)
- README documents both global install and dev install paths

### Technical Requirements

- Version is single-sourced in `pyproject.toml`
- `importlib.metadata` used for runtime version (no hardcoded string)
- `pyproject.toml` includes classifiers, license, and project-urls
- CI matrix tests Python 3.12 and 3.13
- `pyright` and `ruff` pass in CI
- All existing tests pass in CI

## Implementation Notes

### Suggested Implementation Order

1. **`--version` flag** (effort: 0.5/5) — Add version callback to Typer app. Test it.
2. **pyproject.toml metadata** (effort: 0.5/5) — Add classifiers, license field, project-urls.
3. **GitHub Actions CI workflow** (effort: 1/5) — Create `.github/workflows/ci.yml` with test and publish jobs. Test the `test` job by pushing. The `publish` job can't be fully tested until PyPI account is configured.
4. **README updates** (effort: 0.5/5) — Add global install section.
5. **PyPI account setup & first publish** (effort: 0.5/5) — Manual step: create accounts, add secrets, tag and push.

### Testing Strategy

- **`--version` flag**: Unit test via `CliRunner` — invoke `sq --version`, assert output matches `importlib.metadata.version("squadron")`.
- **pyproject.toml metadata**: Build the wheel (`hatch build`), inspect metadata with `pkginfo` or `zipfile` — verify classifiers, license, urls present.
- **CI workflow**: Push to a branch, verify the `test` job runs and passes. Full publish validation requires a real tag push (TestPyPI first).
- **Global install**: Manual smoke test — `pipx install squadron` from TestPyPI, run `sq --version`, `sq --help`, `sq install-commands --target /tmp/test`.

### Special Considerations

- **PyPI name squatting**: Verify `squadron` is available on PyPI before attempting publish. If taken, consider `squadron-ai` or `sq-cli` as alternatives.
- **Trusted publisher vs. API token**: The CI workflow is structured to support both. Trusted publisher (OIDC) is preferred — it requires no stored secrets and is more secure. Configuration is done in PyPI's web UI by linking the GitHub repo. Falls back to `PYPI_API_TOKEN` secret if OIDC isn't set up.
- **claude-agent-sdk dependency**: This package must be installable from PyPI for `pip install squadron` to work. If it's not on PyPI (private/beta), this blocks publishing. Verify availability before attempting the first publish.
