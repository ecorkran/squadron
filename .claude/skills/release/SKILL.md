---
name: release
description: Cut a squadron release — verify cf state, merge the slice, bump version, update CHANGELOG/DEVLOG, tag, push, then watch CI and PyPI until the publish lands. Use when the user says "release", "cut a release", "ship it", or "bump and tag".
---

# Release squadron

Run from the repo root. Stop and report on any failed command; don't work around it.

## 1. Check cf state

Run `cf next`. If it reports something unfinished for the current slice (open review gate, unchecked tasks, failing check), stop and show it. Otherwise continue.

## 2. Merge

Read the target with `cf config get git.integration_branch` (empty means `main`). If the current branch is a slice branch not yet merged into the target, follow the merge steps in CLAUDE.md (Git Rules). If already on the target with the work merged, skip this.

Working tree must be clean before continuing.

## 3. Pick the version

Current version is `version` in `pyproject.toml`. Read `## [Unreleased]` in CHANGELOG.md:

- Anything under `### Added` → minor bump.
- Otherwise → patch bump.
- Major bump only after the user confirms it explicitly.

State the chosen version in one line and proceed (no confirmation for patch/minor).

## 4. Bump and document

1. Set `version` in `pyproject.toml`, then run `uv lock` so `uv.lock` picks it up.
2. CHANGELOG.md: insert `## [X.Y.Z] - YYYYMMDD` directly under `## [Unreleased]`, so the unreleased entries now sit under the new version and `[Unreleased]` is empty. Entries stay short and user-facing.
3. DEVLOG.md: under today's `## YYYYMMDD` heading (create it at the top if missing), add at the top:
   ```
   ### Release X.Y.Z

   - **Contents:** <slices and fixes included, with issue numbers>
   ```
   Update `dateUpdated` in the frontmatter.
4. Run `ruff format`, `ruff check`, `pyright`, and the test suite. Any failure stops the release — CI would block the publish anyway.
5. Commit: `package: bump version to X.Y.Z`.

## 5. Tag and push

```
git tag -a vX.Y.Z -m "vX.Y.Z"
git push
git push --tags
```

## 6. Watch CI and PyPI

The `publish` job in `.github/workflows/ci.yml` runs only on the tag and needs `test` to pass. A red test job means nothing publishes, silently.

Start a loop via the `loop` skill with a 5 minute interval and this check:

1. `gh run list --workflow ci.yml --branch vX.Y.Z --json databaseId,status,conclusion,headSha` — match `headSha` to the tagged commit. (`--commit` is unreliable right after a push.)
2. If the run is still going, report status and wait for the next tick.
3. If it failed, pull the failing job log (`gh run view <id> --log-failed`), report the actual error, stop the loop.
4. If it passed, confirm `curl -sf https://pypi.org/pypi/squadron-ai/X.Y.Z/json` returns. If yes, report "X.Y.Z live on PyPI" and stop the loop. If not yet, wait for the next tick.

Always stop the loop yourself when it resolves either way.
