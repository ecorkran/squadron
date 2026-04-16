"""Built-in FanInReducer implementations.

Reducers are registered at module level in ``_REDUCER_REGISTRY``.
Slice 189 registers ``merge_findings`` at its own import time — no changes here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadron.pipeline.intelligence.fan_in.protocol import FanInReducer

if TYPE_CHECKING:
    from squadron.pipeline.executor import StepResult
    from squadron.pipeline.models import ActionResult

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REDUCER_REGISTRY: dict[str, FanInReducer] = {}


def get_reducer(name: str) -> FanInReducer:
    """Return the reducer registered under *name*.

    Raises:
        KeyError: If no reducer is registered under *name*, with the
            list of registered names in the message.
    """
    if name not in _REDUCER_REGISTRY:
        registered = list(_REDUCER_REGISTRY.keys())
        raise KeyError(
            f"Fan-in reducer '{name}' is not registered. "
            f"Available reducers: {registered}"
        )
    return _REDUCER_REGISTRY[name]


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


class CollectReducer:
    """Gathers all branch outputs into ``outputs["branches"]``.

    ``success`` is True only if every branch succeeded.
    """

    def reduce(
        self,
        branch_results: list[StepResult],
        config: dict[str, object],
    ) -> ActionResult:
        from squadron.pipeline.models import ActionResult

        branches: list[dict[str, object]] = []
        all_succeeded = True

        for result in branch_results:
            if result.status != "completed":
                all_succeeded = False

            action_results_data: list[dict[str, object]] = [
                {
                    "action_type": ar.action_type,
                    "success": ar.success,
                    "outputs": ar.outputs,
                    "verdict": ar.verdict,
                }
                for ar in result.action_results
            ]
            branches.append(
                {
                    "step_name": result.step_name,
                    "status": str(result.status),
                    "action_results": action_results_data,
                }
            )

        return ActionResult(
            success=all_succeeded,
            action_type="fan_out",
            outputs={"branches": branches},
        )


# ---------------------------------------------------------------------------
# first_pass
# ---------------------------------------------------------------------------


class FirstPassReducer:
    """Returns the ActionResult from the first branch with a PASS verdict.

    Falls back to the last branch if no branch passes.
    ``success`` is always True (reducer succeeded; caller inspects verdict).
    """

    def reduce(
        self,
        branch_results: list[StepResult],
        config: dict[str, object],
    ) -> ActionResult:
        from squadron.pipeline.models import ActionResult

        last_result: StepResult | None = None

        for result in branch_results:
            last_result = result
            for ar in result.action_results:
                if ar.verdict == "PASS":
                    return ActionResult(
                        success=True,
                        action_type="fan_out",
                        outputs=ar.outputs,
                        verdict=ar.verdict,
                    )

        # No branch passed — return last branch's first action result, or empty.
        if last_result is not None and last_result.action_results:
            ar = last_result.action_results[0]
            return ActionResult(
                success=True,
                action_type="fan_out",
                outputs=ar.outputs,
                verdict=ar.verdict,
            )

        return ActionResult(
            success=True,
            action_type="fan_out",
            outputs={},
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_REDUCER_REGISTRY["collect"] = CollectReducer()
_REDUCER_REGISTRY["first_pass"] = FirstPassReducer()
