Run an analysis skill from the squadron analysis pack.

## Input parsing

The first word of `$ARGUMENTS` is the skill name. The remainder is passed through to the skill as its
arguments (`[target]` for `tech-debt-audit`, `[flow]` for `understand`).

Valid skills: `tech-debt-audit`, `understand`

If the skill name is missing or unrecognized, show the usage below and stop.

**Usage:**
```
/sq:analysis tech-debt-audit [target]
/sq:analysis understand [flow]
```

---

## Skill: tech-debt-audit

Delegate to the tech-debt-audit skill.

Invoke `/analysis:tech-debt-audit` passing any `[target]` from `$ARGUMENTS` as the arguments.

The skill performs a thorough tech debt and architecture audit of the current codebase (or `[target]` if specified). It produces an audit file with file-cited findings, severity ratings, effort estimates, and a "looks bad but is actually fine" section.

If the skill is not installed, inform the user:
```
The analysis pack is not installed. Run `sq skills install analysis` to install it.
```

---

## Skill: understand

Delegate to the understand skill.

Invoke `/analysis:understand` passing the remainder of `$ARGUMENTS` as the arguments.

The skill reads an existing `understand-anything` knowledge graph of the current codebase and writes squadron planning documents from it. `[flow]` is optional; the skill's "Flow selection" section defines the valid flows and rejects any other.

If the skill is not installed, inform the user:
```
The analysis pack is not installed. Run `sq skills install analysis` to install it.
```
