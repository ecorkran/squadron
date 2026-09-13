---
docType: review
layer: project
reviewType: slice
slice: code-host-adapter-and-pr-target-resolution
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/381-slice.code-host-adapter-and-pr-target-resolution.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 00199ce340130acaecc200975ccd76c531330e02
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "ProcessRunner protocol definition omits the `stdin` parameter that the design says it gains"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md#technical-decisions"
  - id: F002
    severity: note
    category: uncategorized
    summary: "`repo#n` target form is an addition beyond the five forms the architecture enumerates"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md#target-grammar-codethosttargetspy"
  - id: F003
    severity: note
    category: uncategorized
    summary: "`MAX_DISCUSSION_PAGES` pagination cap is referenced but its value is not specified"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md#github-implementation-codethostgithub_clipy"
---

# Review: slice — slice 381

**Verdict:** PASS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] ProcessRunner protocol definition omits the `stdin` parameter that the design says it gains

The "Process-runner seam" section shows the `ProcessRunner` protocol with this signature:

```python
def run(self, argv: Sequence[str], *, cwd: str | None, timeout: float,
        env: Mapping[str, str] | None = None) -> ProcessResult: ...
```

Later, in the GitHub implementation section, the document states: "Body text for writes goes over stdin (`-f body=@-`)… The runner gains an optional `stdin: str | None` parameter for this." The protocol definition as shown does not include `stdin`, yet the `FakeProcessRunner` must also accept it for write-operation tests, and every call site that sends body text depends on it being part of the seam. The protocol definition should show the final signature including `stdin: str | None = None` so the contract that 384 and 385 rely on is unambiguous.

### [NOTE] `repo#n` target form is an addition beyond the five forms the architecture enumerates

The architecture and slice plan both enumerate five target forms: number, URL, `owner/repo#n`, branch, absent. The slice adds a sixth form, `REPO_NUMBER` (`squadron#7`), resolved by matching the repository name across all host-serving remotes regardless of owner. The addition is well-justified — the operator knows the repository name and the remotes already know the owner — and it does not violate any architectural principle. The ambiguity it introduces (more than one owner for that repository name) is explicitly handled with `AmbiguousHostRemoteError`. This is a reasonable scope expansion, noted for transparency.

### [NOTE] `MAX_DISCUSSION_PAGES` pagination cap is referenced but its value is not specified

The `list_unresolved_discussions` operation pages through `reviewThreads(first:100, after:$cursor)` until `hasNextPage` is false or `MAX_DISCUSSION_PAGES`. The constant is named but its numeric value is not stated anywhere in the document. This is a minor under-specification; the cap exists and is testable, but the specific bound is left to implementation. Resolving the exact limit during design (e.g., 10 pages → 1000 threads) would make the contract fully explicit for 382, which injects these discussions into the prompt.
