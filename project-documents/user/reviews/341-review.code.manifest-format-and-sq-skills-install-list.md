---
docType: review
layer: project
reviewType: code
slice: manifest-format-and-sq-skills-install-list
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/341-slice.manifest-format-and-sq-skills-install-list.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260625
dateUpdated: 20260625
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "Temp directory leak on GitHub clone failure"
    location: src/squadron/skills/resolver.py:77
  - id: F002
    severity: concern
    category: uncategorized
    summary: "Fragile GC-dependent file copy in GitHub install path"
    location: src/squadron/skills/installer.py:29-34
  - id: F003
    severity: concern
    category: uncategorized
    summary: "Unreachable `return` statements after `_require_manifest()`"
    location: src/squadron/cli/commands/skills.py:39,73
  - id: F004
    severity: concern
    category: uncategorized
    summary: "Late/buried imports inside function bodies"
    location: src/squadron/cli/commands/skills.py:104-117
  - id: F005
    severity: concern
    category: uncategorized
    summary: "`_detect_origin` silently swallows all manifest errors"
    location: src/squadron/cli/commands/skills.py:108-117
  - id: F006
    severity: concern
    category: uncategorized
    summary: "Incomplete test assertions for GitHub clone"
    location: tests/skills/test_resolver.py:54-62
  - id: F007
    severity: concern
    category: uncategorized
    summary: "`shutil` imported at function level instead of module level"
    location: tests/skills/test_resolver.py:56
  - id: F008
    severity: note
    category: uncategorized
    summary: "`cwd` parameter is unused in `resolve_source`"
    location: src/squadron/skills/resolver.py:16
  - id: F009
    severity: note
    category: uncategorized
    summary: "`_detect_origin` logic may return incorrect origin"
    location: src/squadron/cli/commands/skills.py:103
  - id: F010
    severity: pass
    category: uncategorized
    summary: "Proper exception handling in CLI commands"
    location: src/squadron/cli/commands/skills.py
  - id: F011
    severity: pass
    category: uncategorized
    summary: "Good test structure and isolation"
    location: tests/skills/*.py
  - id: F012
    severity: pass
    category: uncategorized
    summary: "Type hints throughout"
    location: src/squadron/skills/*.py
  - id: F013
    severity: pass
    category: uncategorized
    summary: "Dataclass for internal DTO, Pydantic for external boundary"
    location: src/squadron/skills/models.py
---

# Review: code — slice 341

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Temp directory leak on GitHub clone failure

In `_resolve_github`, when `git clone` fails (returncode != 0), the `tmp_dir` that was already created is removed via `shutil.rmtree`. However, when `resolve_source` successfully clones but the returned path is later used by `_install_from_path`, the temp directory is **never cleaned up**. Each successful GitHub install leaves `~/.tmp/squadron-skills-*` directories on disk permanently.

```python
def _resolve_github(source: str, pack_name: str) -> Path:
    # ...
    tmp_dir = tempfile.mkdtemp(prefix="squadron-skills-")  # Created here
    result = subprocess.run(["git", "clone", "--depth=1", url, tmp_dir], ...)
    if result.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # Only cleaned on failure
        raise SkillSourceError(...)
    return Path(tmp_dir)  # Returned but temp dir is never cleaned up later
```

Additionally, in `_install_with_temp_dir` in `installer.py:27`, a separate temp dir is created but never used—the actual cloned content lives in a different temp dir returned by `resolve_source`. The outer temp dir is cleaned but the inner one leaks.

### [CONCERN] Fragile GC-dependent file copy in GitHub install path

When installing a GitHub pack, `resolve_source` returns a path to a cloned repo inside a temp directory. The code relies on Python's garbage collector to not have collected that temp dir by the time `shutil.copy2` executes in `_install_from_path`. While this works in practice, it's fragile:

```python
def _install_with_temp_dir(pack_name: str, entry: PackEntry, commands_dir: Path) -> InstallResult:
    tmp = tempfile.mkdtemp(prefix="squadron-skills-install-")
    try:
        source_path = resolve_source(entry, pack_name)  # Returns path to different tmp dir
        return _install_from_path(pack_name, entry, commands_dir, source_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # Cleans wrong tmp; source_path's tmp still alive
```

The `source_path` variable in the outer function keeps a reference to the inner temp dir, but this pattern is unclear and depends on implementation details of how long Python delays GC of temporary directory objects.

### [CONCERN] Unreachable `return` statements after `_require_manifest()`

Both `install` and `list_packs` have `return` statements immediately after `_require_manifest()`, which always raises `typer.Exit`:

```python
if manifest is None:
    _require_manifest()
    return  # unreachable
```

These should be removed for clarity.

### [CONCERN] Late/buried imports inside function bodies

In `_detect_origin`, `load` is imported inside the function body rather than at module level. This creates two separate import paths for the same function and makes static analysis harder:

```python
def _detect_origin(pack_name: str) -> str:
    from squadron.skills.manifest import PROJECT_MANIFEST_NAME, USER_MANIFEST
    # ...
    if USER_MANIFEST.exists():
        from squadron.skills.manifest import load  # <-- nested import
```

### [CONCERN] `_detect_origin` silently swallows all manifest errors

When manifest files exist but have parse errors, `_detect_origin` silently catches and ignores `ValueError` and `OSError`. A corrupted user manifest would cause `_detect_origin` to return "unknown" for all packs, potentially misleading users:

```python
try:
    user_m = load(USER_MANIFEST)
except (ValueError, OSError):
    pass  # Silent - no logging of the corruption
```

### [CONCERN] Incomplete test assertions for GitHub clone

The GitHub clone test lacks meaningful assertions. It checks `path.is_dir()` but doesn't verify that the expected `.md` files were actually cloned, nor that the clone contains correct content:

```python
def test_clone_succeeds(self, tmp_path: Path) -> None:
    entry = PackEntry(source="github:anthropics/anthropic-cookbook", prefix="cookbook")
    path = resolve_source(entry, "cookbook")
    assert path.is_dir()  # Only checks directory exists
    # Missing: assert (path / "some_expected_file.md").exists()
    # Missing: check for actual skill content
```

### [CONCERN] `shutil` imported at function level instead of module level

Import statement placed inside a test method body rather than at the top of the file:

```python
def test_clone_succeeds(self, tmp_path: Path) -> None:
    # ...
    import shutil
    shutil.rmtree(str(path), ignore_errors=True)
```

### [NOTE] `cwd` parameter is unused in `resolve_source`

The `cwd` parameter is accepted but never used. If relative paths were intended to resolve from a working directory, the implementation doesn't support that:

```python
def resolve_source(entry: PackEntry, pack_name: str) -> Path:
    # Note: cwd parameter accepted but not used
```

### [NOTE] `_detect_origin` logic may return incorrect origin

When `manifest.origin` is "merged", `_detect_origin` is called, but the result is used unconditionally without verifying the pack is actually from that origin. If a pack is in both user and project manifests, whichever is checked second "wins" due to the if/elif chain order:

```python
if proj_m and pack_name in proj_m.packs:
    return "project"
if user_m and pack_name in user_m.packs:
    return "user"
```

Project is checked first, so if a pack exists in both manifests, "project" is always returned—matching the merge behavior but not clearly documented.

### [PASS] Proper exception handling in CLI commands

The CLI commands properly catch specific exceptions (`ValueError` for parse errors, `SkillSourceError` for source issues) and exit with meaningful error messages and exit code 1.

### [PASS] Good test structure and isolation

Tests properly use `pytest.MonkeyPatch` to isolate manifest paths, use `tmp_path` fixtures for clean test environments, and include appropriate error-case coverage. Network-dependent tests are marked with `@pytest.mark.network`.

### [PASS] Type hints throughout

All functions have proper type annotations using modern Python 3.12+ patterns (`str | None` instead of `Optional[str]`).

### [PASS] Dataclass for internal DTO, Pydantic for external boundary

`InstallResult` correctly uses `@dataclass` (internal DTO), while `PackEntry` uses Pydantic `BaseModel` with a model validator for input validation from TOML.
