Review ingest fixtures (a .txt so a directory ingest does not pick it up)

Frontmatter copied verbatim from squadron's own reviews (body omitted), plus synthetic files named for what each tests.

| File | What it is |
|---|---|
| `156-review.code.pipeline-executor-hardening.md` | Real. No `reviewedSha`, no `targetKind`, free-form categories (read-side mapped) |
| `947-review.code.*` | Real. `targetKind: slice`, `reviewedSha`, slice 947 |
| `github.com-ecorkran-squadron-116-review.code.md` | Real. A PR review whose verdict is `UNKNOWN` (degraded) |
| `0-review.code.review-1.md` | Real. Blank `sourceDocument`, `slice: unknown`, verdict `UNKNOWN` |
| `320-review.arch.*` | Real. An arch review, not a code review |
| `synthetic-pr-review.code.md` | PR source, known verdict: the record has no slice index |
| `synthetic-new-format.code.md` | `categoriesNormalized: true`, one `rawCategory`, one `uncategorized` |
| `synthetic-bad-severity.code.md` | One finding whose severity isn't a review severity |
| `synthetic-new-format-bad-category.code.md` | A normalized file storing a category that isn't a `ReviewCategory` |
| `synthetic-missing-verdict.code.md` | No `verdict` key (and no `docType: review`, which the repo's verdict gate would refuse to commit) |
| `synthetic-malformed-frontmatter.code.md` | Frontmatter that isn't valid YAML |

The non-UTF-8 file is created at test time, not committed.
