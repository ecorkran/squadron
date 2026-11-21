"""The benchmark's standing answer to a producer that pauses for the PM.

Nothing answers pauses inside a benchmark, so a run that asks would end blocked, and asking
would score worse than guessing. Every pause gets the same answer for every config, which
keeps the comparison fair, and the record counts how often a run asked.
"""

from __future__ import annotations

#: The instructions every paused producer run is resumed with.
STANDING_PAUSE_ANSWER = (
    "No one is available to answer questions during this run. Decide the question yourself "
    "from the design, task and issue documents you were given and the project's rules. "
    "Record the decision and your reason where you record task notes, remove any BLOCKED "
    "line you wrote, and continue."
)

#: Pauses answered per replay; a run still paused after this many ends blocked.
MAX_PAUSES_ANSWERED = 3
