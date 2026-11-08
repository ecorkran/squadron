"""A project module that calls a dependency directly and holds mutable module state."""

from subprocess import run

REGISTRY = {"a": 1}
setting = 1


def execute(command):
    return run(command, capture_output=True, text=True, check=False)
