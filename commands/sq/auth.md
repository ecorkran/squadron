Run an auth command using squadron.

## Input parsing

The first word of `$ARGUMENTS` is the subcommand. If `$ARGUMENTS` is empty or the subcommand is `status`, run the status command. If the subcommand is unrecognized, show the usage below and stop.

Valid subcommands: `status`

**Usage:**
```
/sq:auth status    — show credential and profile status
/sq:auth           — same as /sq:auth status
```

---

## Subcommand: status

Run the following command and display the results:

`sq auth status`

Shows configured credentials and their validation status for each provider profile.
