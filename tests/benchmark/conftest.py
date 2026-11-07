"""Benchmark test configuration.

The fixture projects hold deliberately failing tests; the repo's own pytest run must not
collect them (``testpaths = ["tests"]``).
"""

collect_ignore_glob = ["fixtures/*"]
