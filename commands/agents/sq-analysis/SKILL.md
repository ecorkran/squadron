---
name: sq-analysis
description: Runs an analysis skill from the squadron analysis pack, such as a tech debt audit. Use when the user asks for a codebase audit, architecture review, or code quality assessment through squadron's analysis pack.
---

# sq analysis

Run an analysis skill from the squadron analysis pack.

## Input parsing

The first word the user typed after `$sq-analysis` is the skill name. The remainder is passed
through as `[target]`.

Valid skills: `tech-debt-audit`

If the skill name is missing or unrecognized, show the usage below and stop.

**Usage:**
```
$sq-analysis tech-debt-audit [target]
```

---

## Skill: tech-debt-audit

Delegate to the tech-debt-audit skill.

Invoke `$analysis-tech-debt-audit`, passing along any `[target]` the user supplied.

The skill performs a thorough tech debt and architecture audit of the current codebase (or
`[target]` if specified). It produces an audit file with file-cited findings, severity ratings,
effort estimates, and a "looks bad but is actually fine" section.

If the skill is not installed, inform the user:
```
The analysis pack is not installed. Run `sq skills install analysis` to install it.
```
