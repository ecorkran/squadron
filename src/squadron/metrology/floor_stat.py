"""The measured spread of one quantity across a variance series (slice 320).

Its own module so records outside ``models.py`` (the benchmark grade records, slice 425)
can embed it without importing the envelope that embeds them. ``models.py`` re-exports it.
"""

from __future__ import annotations

from pydantic import BaseModel


class FloorStat(BaseModel):
    """The measured spread of one quantity across a variance series.

    ``stddev`` is the sample standard deviation. At the default n=3 it is a
    coarse figure, and every surface presenting it says so — it bounds
    interpretation of a later delta, it does not support a significance
    claim.
    """

    min: int
    max: int
    mean: float
    stddev: float
