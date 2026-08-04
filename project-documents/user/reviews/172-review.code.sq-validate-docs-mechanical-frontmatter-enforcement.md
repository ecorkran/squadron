---
docType: review
layer: project
reviewType: code
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260804
dateUpdated: 20260804
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Schema module centralizes canonical docType/status values"
    location: src/squadron/documents/schema.py:1-92
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Validator is pure and well-tested"
    location: src/squadron/documents/validate.py:1-320
  - id: F003
    severity: pass
    category: uncategorized
    summary: "dateUpdated stamping is centralized"
    location: src/squadron/documents/frontmatter.py:118-160
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Pre-commit hook fails explicitly rather than silently"
    location: .githooks/pre-commit:25-34
  - id: F005
    severity: concern
    category: uncategorized
    summary: "Pre-commit hook excludes renamed .md files from validation"
    location: .githooks/pre-commit:18
  - id: F006
    severity: concern
    category: uncategorized
    summary: "`_resolve_git_hooks_path` does not check `git config --get` return code"
    location: src/squadron/cli/commands/doctor.py:110-124
  - id: F007
    severity: concern
    category: uncategorized
    summary: "Schema-drift regex can match docstrings/comments as canonical-value examples"
    location: tests/documents/test_schema_drift.py:99-108
  - id: F008
    severity: note
    category: uncategorized
    summary: "CLI double-walks the document root"
    location: src/squadron/cli/commands/validate.py:55-57
  - id: F009
    severity: note
    category: uncategorized
    summary: "`validate_document` exceeds the 50-line guideline"
    location: src/squadron/documents/validate.py:96-179
  - id: F010
    severity: note
    category: uncategorized
    summary: "`update_frontmatter` requires `today` keyword; positional callers will break"
    location: src/squadron/documents/frontmatter.py:118-160
---

# Review: code — slice 172

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Schema module centralizes canonical docType/status values

The new `schema.py` module is the single source of truth for `DocumentStatus`, `DocType`, machine-artifact docTypes, and the context-forge marker — exactly what CLAUDE.md demands ("Never scatter comparison values across code"). The `test_no_canonical_literal_outside_schema_module` drift guard prevents regressions.

### [PASS] Validator is pure and well-tested

The module's docstring claims "Pure: takes paths, returns `list[Violation]`. No printing, no `sys.exit`." and the implementation honors that — `select_document_paths` only raises `DocumentRootError`, and `validate_document` collects every violation rather than short-circuiting. This is exactly the right shape for being called later from `sq doctor` or an MCP tool. Tests cover FM001-FM008, valid paths, machine artifacts, and round-trip cases.

### [PASS] dateUpdated stamping is centralized

Moving the `today` parameter into `update_frontmatter` rather than asking each caller to stamp by hand is the right call — `frontmatter.py` is the one primitives module that touches documents in place, and the comment explaining why this is "squadron's only in-place document edit" is well-reasoned. All call sites (`pipeline/executor.py`, `pipeline/actions/devlog.py`, tests) are updated.

### [PASS] Pre-commit hook fails explicitly rather than silently

The hook rejects commits when `uv` is missing on PATH rather than passing through. Per CLAUDE.md ("Never use silent fallback values"), this is correct: a hook that silently skips when its tool is missing enforces nothing while appearing to work.

### [CONCERN] Pre-commit hook excludes renamed .md files from validation

The filter `--diff-filter=ACM` includes Added/Copied/Modified but excludes Renamed (R). For a renamed process document (`git mv notes.md new-notes.md`), the new file's status is R, so it is silently dropped from validation. Suggested fix: change to `--diff-filter=ACMR`. Renames preserve frontmatter content, so this is not a correctness regression for already-valid docs, but it is a coverage gap on a slice whose explicit purpose is mechanical enforcement.

### [CONCERN] `_resolve_git_hooks_path` does not check `git config --get` return code

The function returns `process.stdout.strip()` unconditionally whenever `process is not None`, even when `process.returncode != 0`. `git config --get core.hooksPath` exits non-zero both when the key is unset (expected) and when the config cannot be read (corrupt `.git/config`, permission denied). In the error case the doctor would diagnose "core.hooksPath is '', not '.githooks'" — which is misleading. Either inspect the return code or document explicitly that all non-zero return codes are collapsed to "unset".

### [CONCERN] Schema-drift regex can match docstrings/comments as canonical-value examples

The regex `["']?(docType|status):\s*["']?{value}["']?` has no anchoring and no exclusion for comments or docstrings. A future docstring like `"""Example: docType: review"""` (perfectly reasonable documentation) would fail this test. Since the comment around it explicitly worries about "gate fatigue" from false positives, scoping this to a tighter shape — or excluding `^#` and `^\s*"""` lines — would reduce that risk.

### [NOTE] CLI double-walks the document root

`validate_docs` calls `select_document_paths(paths or None, root=resolved_root)` (for the summary count) and then `validate_paths(paths or None, root=resolved_root)` (which internally calls `select_document_paths` again). With `paths=None` the directory walk runs twice. Acceptable for the current corpus, but `validate_paths` could accept a precomputed candidates list, or `validate_docs` could derive the summary from `violations` alone (`len({v.path for v in violations})` for the violating-file count).

### [NOTE] `validate_document` exceeds the 50-line guideline

The function is roughly 80 lines and packs the UnicodeDecodeError branch, the YAML parse branch, the non-mapping branch, and five field-level checks into one body. Each check could be a small private helper (`_check_doc_type`, `_check_required_fields`, `_check_status`, `_check_dates`), which would both shorten the function and make each violation source self-contained — easier to extend with FM009+ codes later without further bloating this function.

### [NOTE] `update_frontmatter` requires `today` keyword; positional callers will break

The new required keyword argument is a deliberate API change and is well-documented in the docstring. Both production callers (`executor.py`, `devlog.py`) and the test suite were updated in the same change, so the blast radius is contained. Flagging only because any third-party code that imported this function will get a `TypeError` at call time.
