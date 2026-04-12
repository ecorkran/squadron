Generate a clipboard summary of this conversation for manual context reset.

## Input parsing

If `$ARGUMENTS` starts with `--restore`:
- Run the restore flow (Steps R1–R2 below).
- Skip the normal summary generation flow entirely.

Otherwise: the first word of `$ARGUMENTS` is an optional template name. If empty, no template argument is passed to the CLI (it will use the configured default).

---

## Step R1: Get restore content

Run via Bash:

```bash
sq _summary-instructions --restore
```

If the command exits non-zero, show the error output to the user and **stop** — do not continue.

---

## Step R2: Seed context

Output the returned summary text directly as a context block for the conversation.

**Do NOT copy to clipboard** — this is a context restore, not a clipboard operation.

After outputting the context block, print exactly one line:

```
Context restored from {filename} (N chars).
```

Where `{filename}` is the name of the file that was used (from the stderr output of Step R1), and `N` is the character count of the restored text.

---

## Step 1: Get summary instructions, suffix, and project name

Run all three commands via Bash:

```bash
sq _summary-instructions $ARGUMENTS
sq _summary-instructions $ARGUMENTS --suffix
sq _summary-instructions --project
```

Capture the first command's stdout as the **instruction text**.
Capture the second command's stdout as the **suffix text** (may be empty).
Capture the third command's stdout (trimmed) as the **project name** (may be empty if CF is not configured; non-fatal).

If the first or second command exits non-zero, show the error output to the user and **stop** — do not continue. A non-zero exit from the third command is non-fatal; treat project name as empty.

---

## Step 2: Generate the summary

Using the instruction text from Step 1 as your guide, generate a summary of the **current conversation**.

Follow the instructions exactly. Output ONLY the summary text — no preface, no explanation, no follow-up questions, no markdown fences around the summary.

---

## Step 3: Copy to clipboard

Pipe the summary text (followed by the suffix text, if any) to the system clipboard via Bash. Use a heredoc to handle special characters. If the suffix is non-empty, append it after the summary with a newline separator:

```bash
cat << '__SQ_END__' | pbcopy 2>/dev/null || cat << '__SQ_END__' | xclip -selection clipboard 2>/dev/null || cat << '__SQ_END__' | wl-copy 2>/dev/null || { echo "No clipboard tool found (install xclip or wl-clipboard on Linux)" >&2; exit 1; }
SUMMARY_TEXT
SUFFIX_TEXT
__SQ_END__
```

Replace `SUMMARY_TEXT` with the actual summary and `SUFFIX_TEXT` with the suffix (omit the suffix line entirely if it is empty).

---

## Step 4: Write to file

If the project name from Step 1 is non-empty, write the summary text (without suffix) to the conventional summaries location via Bash:

```bash
mkdir -p ~/.config/squadron/runs/summaries
cat << '__SQ_END__' > ~/.config/squadron/runs/summaries/{project}-interactive.md
SUMMARY_TEXT
__SQ_END__
```

Replace `{project}` with the project name and `SUMMARY_TEXT` with the actual summary text.

If the project name is empty, skip this step silently.

---

## Step 5: Confirm

Print exactly one line:

```
Summary copied to clipboard (N chars, template: T).
```

Where `N` is the character count of the full clipboard content (summary + suffix) and `T` is the template name used (from arguments or default).

If Step 4 wrote a file, append the filename on the same line, separated by a space:

```
Summary copied to clipboard (N chars, template: T). Saved: {project}-interactive.md
```
