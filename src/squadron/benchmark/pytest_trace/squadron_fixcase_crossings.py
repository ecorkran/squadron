"""Dynamic crossings for the fix-case trace plugin (slice 422 D6).

A crossing is a call whose *immediate* caller frame is test-side code and whose callee frame
is project source, recorded as ``(module, co_qualname, kind)``. A project function that a
dependency calls back (``ExitStack.callback``, a framework invoking a command) has a library
frame as its caller, so it is not a crossing. That is what lets a test "drive the CLI".

Records only while a phase is started with ``start`` (a test's call phase and its fixtures'
setup), and restores whatever profiler was installed before. Runs inside the project's own
environment, so it imports only the standard library and its sibling plugin module.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from typing import Any

import squadron_fixcase_closure

KIND_FUNCTION = "function"
KIND_CONSTRUCTOR = "constructor"
KIND_METHOD = "method"
_CONSTRUCTOR_NAMES = frozenset({"__init__", "__new__"})
_LOCALS_MARKER = "<locals>"

Crossing = tuple[str, str, str]
ProfileFunction = Callable[[types.FrameType, str, Any], Any]


def crossing_kind(code_name: str, qualname: str) -> str:
    """``constructor`` for ``__init__``/``__new__``, ``method`` with a class prefix, else function."""
    if code_name in _CONSTRUCTOR_NAMES:
        return KIND_CONSTRUCTOR
    if "." not in qualname:
        return KIND_FUNCTION
    owner = qualname.rsplit(".", 1)[0]
    # A function nested in another function has "<locals>" before its name, not a class.
    return KIND_FUNCTION if owner.endswith(_LOCALS_MARKER) else KIND_METHOD


class CrossingRecorder:
    def __init__(self, closures: squadron_fixcase_closure.ClosureBuilder) -> None:
        self._closures = closures
        self._sides: dict[types.CodeType, tuple[bool, bool]] = {}
        self._recorded: dict[str, set[Crossing]] = {}
        self._node_id: str | None = None
        self._previous: ProfileFunction | None = None

    def start(self, node_id: str) -> None:
        """Begin recording for ``node_id``, remembering the profiler to restore."""
        self._node_id = node_id
        self._recorded.setdefault(node_id, set())
        self._previous = sys.getprofile()
        sys.setprofile(self._profile)

    def stop(self) -> None:
        """Stop recording and put back the profiler that was there before ``start``."""
        sys.setprofile(self._previous)
        self._previous = None
        self._node_id = None

    def crossings(self, node_id: str) -> list[list[str]]:
        return [list(crossing) for crossing in sorted(self._recorded.get(node_id, ()))]

    def _sides_of(self, code: types.CodeType) -> tuple[bool, bool]:
        """(is test-side, is project source) for a code object, cached per code object."""
        if code not in self._sides:
            filename = code.co_filename
            self._sides[code] = (
                self._closures.relative_file(filename) is not None,
                self._closures.is_project_file(filename),
            )
        return self._sides[code]

    def _profile(self, frame: types.FrameType, event: str, arg: Any) -> None:
        if event != "call" or self._node_id is None:
            return
        caller = frame.f_back
        if caller is None:
            return
        if not self._sides_of(caller.f_code)[0] or not self._sides_of(frame.f_code)[1]:
            return
        code = frame.f_code
        qualname = getattr(code, "co_qualname", code.co_name)
        module = str(frame.f_globals.get("__name__", ""))
        self._recorded[self._node_id].add((module, qualname, crossing_kind(code.co_name, qualname)))
