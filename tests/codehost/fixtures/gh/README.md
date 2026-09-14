# `gh` response fixtures

Captured from **real** `gh` responses. A fixture invented by hand proves nothing
about a response shape squadron does not control, so every file here came off
the wire.

## Provenance

- `gh` version: **2.96.0 (2026-07-02)**
- Captured: **20260913**
- Source repository: `ecorkran/squadron` unless noted otherwise

| File | Command | Notes |
|---|---|---|
| `pr83-resolve.json` | `gh api graphql` PR query | PR 83, MERGED, cross-repository |
| `repo.json` | `gh api repos/ecorkran/squadron` | `default_branch` is `main` |
| `user.json` | `gh api user` | operator identity |
| `branch-404.json` | `gh api repos/.../branches/no-such-branch-xyz` | REST 404; carries `"status": "404"` as a **string** |
| `pr83-reviewthreads.json` | `gh api graphql` reviewThreads | the **empty** case |
| `reviewthreads-populated.json` | `gh api graphql` reviewThreads | see caveat below |
| `graphql-notfound.json` | `gh api graphql` on a nonexistent repo | GraphQL `NOT_FOUND` error type |
| `rest-422.json` | `gh api repos/.../pulls -X POST` with a bad head | REST 422 |

## Caveat: the populated `reviewThreads` fixture

`ecorkran/squadron` has only three pull requests (64, 66, 83) and **none of them
has a single review thread**, so the populated case could not be captured from
this repository. It was captured from a public repository instead.

That is a deliberate choice over the alternative of writing one by hand. The
shape being pinned is GitHub's GraphQL schema, not squadron's data, so a real
response from any repository exercises the same parser. If a squadron PR ever
accumulates review threads, recapture it here and drop this note.

## When these go stale

The design's risk register names `gh` output drift as the live risk.
`HostResponseMalformedError` is the runtime half of that defense; this file is
the other half. If a test starts failing against a newer `gh`, compare the
version above with the one installed before assuming the parser is wrong.
