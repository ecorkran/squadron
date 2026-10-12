"""Project conventions and rule-file selection shared by dispatch and review.

Imports nothing from ``squadron.review`` or ``squadron.pipeline``: callers
resolve the rules directory, the provider's native file, and the budget, and
pass them in.
"""
