Generate a clipboard summary of this conversation for manual context reset.

## Input parsing

The first word of `$ARGUMENTS` is an optional template name. If empty, no template argument is passed to the CLI (it will use the configured default).

---

## Step 1: Get summary instructions

Run via Bash:

```bash
sq _summary-instructions $ARGUMENTS
```

Capture stdout as the **instruction text**.

If the command exits non-zero, show the error output to the user and **stop** — do not continue.

---

## Step 2: Generate the summary

Using the instruction text from Step 1 as your guide, generate a summary of the **current conversation**.

Follow the instructions exactly. Output **ONLY** the summary text — no preface, no explanation, no follow-up questions, no markdown fences around the summary.

**Do NOT print the summary text into the chat.** Store it in a variable for the next step.

---

## Step 3: Copy to clipboard

Pipe the summary text to the system clipboard via Bash:

```bash
echo 'SUMMARY_TEXT' | pbcopy 2>/dev/null || echo 'SUMMARY_TEXT' | xclip -selection clipboard 2>/dev/null || echo 'SUMMARY_TEXT' | wl-copy 2>/dev/null || { echo "No clipboard tool found (install xclip or wl-clipboard on Linux)" >&2; exit 1; }
```

Replace `SUMMARY_TEXT` with the actual summary. Use appropriate quoting to handle special characters (prefer a heredoc or printf if the summary contains single quotes).

---

## Step 4: Confirm

Print exactly one line:

```
Summary copied to clipboard (N chars, template: T).
```

Where `N` is the character count of the summary and `T` is the template name used (from arguments or default).
