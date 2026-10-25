"""Shared by the vocabulary sync tests (slices 323 and 402)."""

from __future__ import annotations

import re

#: Category values are backticked kebab-case tokens. Matching backticked tokens (rather
#: than a fixed table or list layout) keeps the sync tests lenient about formatting:
#: reflowing a table into a bullet list must not break the guard.
BACKTICKED = re.compile(r"`([a-z][a-z-]*[a-z])`")
