"""The audit harness: run the tech-debt-audit skill against a project.

Surface-agnostic — no Typer imports — matching the 320/321/322 core/CLI
split. The CLI shells in ``cli/commands/metrology.py`` are thin wrappers
over this module.
"""

from __future__ import annotations

#: Prefixed to the audit prompt to suppress the skill's repeat-run mode.
#:
#: The skill is a living document by default: on a repeat run it reads the
#: previous audit file and emits a RESOLVED/NEW diff. That behavior is
#: correct for interactive use and fatal for variance measurement — run 2
#: of a series would be anchored to run 1 rather than an independent
#: sample, biasing the measured floor toward zero.
#:
#: Defined once here and asserted against the skill file by
#: ``tests/metrology/test_audit_skill_sync.py``, so the string the harness
#: sends and the string the skill documents cannot drift apart.
INDEPENDENT_RUN_MARKER = "INDEPENDENT RUN: do not read or update any existing audit file"
