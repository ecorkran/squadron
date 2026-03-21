Run an architectural review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand** and perform a holistic review. Otherwise, pass `$ARGUMENTS` directly to `sq review arch` as before.

### Slice number shorthand (holistic review)

When `$ARGUMENTS` is a bare number:

1. Run `cf slice list --json` and find the entry where `index` matches the number. If no match, report the error and stop — do not guess or fall back.
2. Extract the `designFile` from the matching entry. If `designFile` is null, report that no slice design file exists for this slice and stop.
3. Extract the slice name from the design file path (the part after `nnn-slice.` and before `.md`).
4. Extract the `name` field from the matching entry — this is the slice plan entry title describing what this slice should accomplish.
5. Run `cf get` to resolve the Architecture document field. This is the `--against` target.
6. Run the review:

`sq review arch {design-file-path} --against {architecture-doc-path} -v`

7. This is a **holistic review** answering one question: "does this slice design effectively cover what it's supposed to?" The review should check the slice design against both:
   - **Architecture document** — does the design align with the system architecture?
   - **Slice plan entry** ("{entry-name}") — does the design deliver what the plan says this slice should do?

Present both dimensions in the review output.

8. Save the full review output to `project-documents/user/reviews/{nnn}-review.arch.{slice-name}.md` with this YAML frontmatter:

```yaml
---
docType: review
reviewType: arch
slice: {slice-name}
project: squadron
verdict: {PASS|CONCERNS|FAIL}
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

If this file already exists (re-review), overwrite it. Git handles version history.

9. Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When `$ARGUMENTS` contains paths (not a bare number), run:

`sq review arch $ARGUMENTS`

Required arguments:
- Positional: path to the document to review
- `--against PATH`: architecture or context document to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review arch slices/105-slice.md --against architecture/100-arch.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
