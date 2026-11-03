---
name: "source-command-cf-onboard"
description: "Guide a user through Context Forge project setup and into their first phase of work"
---

# source-command-cf-onboard

Use this skill when the user asks to run the migrated source command `cf-onboard`.

## Command Template

You are guiding a user through Context Forge project onboarding. Follow these
steps in order — skip any step whose precondition is already met.

## Step 1 — Detect existing project

Check whether a Context Forge project is already registered at the current
working directory.

**MCP:** Call `project_list`. Scan results for a project whose `projectPath`
matches the current directory.
**CLI:** Run `cf project list` and check the output.

- If a project exists at this path → skip to Step 3.
- If no project exists → continue to Step 2.

## Step 2 — Create project

Ask the user what they'd like to name their project. If a project name argument
was provided with the command, use that. If the user declines to choose, default
to the current directory name.

**Primary:** Run `cf init <name>` via the shell. This single command handles
everything: git initialization, project registration, guide installation,
command installation, and IDE setup. After `cf init` completes, skip to Step 3.

**Important:** Do not rely on environment context (like "Is a git repository")
to determine git status — `cf init` checks the actual directory and handles
git initialization itself.

**MCP fallback** (if shell access is unavailable):
1. Call `project_create` with `name` and `projectPath` (the CWD).
2. Call `guide_install` to install the AI Project Guide.
Note: the MCP fallback cannot initialize git. If the directory is not a git
repository, inform the user they need to run `git init` first.

## Step 3 — Transition to concept discussion

The project is set up. Now begin the Phase 0 (Concept) conversation.

**MCP:** Call `context_build` to generate the concept-phase context prompt.
Use the returned prompt as your working context to guide the conversation.

**CLI:** Run `cf build` and use the output as your working context.

Begin by asking the user to describe what they want to build. Guide them
through the concept exploration naturally — the context prompt provides the
structure. The goal is a concept document at the end of this conversation.

## Step 4 — Mention ongoing guidance

After the concept conversation concludes (or if the user wants to pause),
mention: "You can run `cf next` (or `/cf:next`) anytime to see what to do
next. It adapts as your project progresses."

## Notes

- If any MCP tool call fails, fall back to the CLI equivalent.
- If the user already has a project but is in a later phase (not Phase 0),
  acknowledge this and suggest `cf next` instead of starting a concept
  discussion.
- Keep the conversation natural. This is onboarding, not a checklist.
  Adapt to what the user is telling you.
