---
name: sq-auth
description: Shows squadron's credential and profile status for each provider. Use when the user asks whether their API keys or provider credentials are configured, or asks about auth status.
---

# sq auth

Run an auth command using squadron.

## Input parsing

The first word the user typed after `$sq-auth` is the subcommand. If they typed nothing, or the
subcommand is `status`, run the status command. If the subcommand is unrecognized, show the usage
below and stop.

Valid subcommands: `status`

**Usage:**
```
$sq-auth status    — show credential and profile status
$sq-auth           — same as $sq-auth status
```

---

## Subcommand: status

Run the following command and display the results:

`sq auth status`

Shows configured credentials and their validation status for each provider profile.
