"""Register a checkout as a cf project under a given environment (slices 177 D3, 426 D9).

P4-P6 run cf operations, and cf resolves the project from the working directory, so a
sandbox must be a registered cf project. cf reads its registry from ``HOME``, so the
registration has to run under the same environment as the process that will use it: the
harness's for a replay sandbox, the scrubbed home's for a benchmark producer.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from squadron.core.process_runner import ProcessResult, ProcessRunner
from squadron.replay.history_free_sandbox import (
    PROCESS_FAILURES,
    SANDBOX_COMMAND_TIMEOUT_SECONDS,
)
from squadron.stats.planning_docs import UnknownSliceError, plan_file_for

_logger = logging.getLogger(__name__)


class CfRegistrationError(Exception):
    """A registration step failed; the message is the command and its stderr."""


class SliceNotInPlanError(CfRegistrationError):
    """The slice is in no slice plan in the tree, so there is no initiative to register."""

    def __init__(self, slice_index: int) -> None:
        super().__init__(f"slice {slice_index} is in no slice plan")
        self.slice_index = slice_index


class CfRegistration:
    """Runs the three cf steps that make a tree a project cf can build context for."""

    def __init__(self, runner: ProcessRunner, env: Mapping[str, str] | None) -> None:
        self._runner = runner
        self._env = env
        self._registered = False

    @property
    def registered(self) -> bool:
        """True once ``cf init`` succeeded, so a failed later step still needs cleanup."""
        return self._registered

    def register(self, tree: Path, name: str, branch: str, slice_index: int) -> None:
        """Register ``tree`` as project ``name`` and point cf at the slice's initiative.

        The branch guard compares the checkout to ``git.integration_branch``, so ``branch``
        is set as it; a fresh cf project has no slice plan, so ``cf set arch`` names the
        initiative whose plan lists the slice. The initiative is resolved first, so a slice in
        no plan leaves nothing registered.
        """
        initiative = _initiative(tree, slice_index)
        self._run(("cf", "init", "--lite", "--no-ide", "--name", name), tree)
        self._registered = True
        self._run(("cf", "config", "set", "git.integration_branch", branch), tree)
        self._run(("cf", "set", "arch", initiative), tree)

    def _run(self, argv: Sequence[str], tree: Path) -> None:
        command = " ".join(argv)
        try:
            result = self._invoke(argv, tree)
        except PROCESS_FAILURES as exc:
            _logger.exception("cf registration step failed: %s: %s", command, exc)
            raise CfRegistrationError(f"{command}: {exc}") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip()
            _logger.error("cf registration step failed: %s: %s", command, stderr)
            raise CfRegistrationError(f"{command} failed: {stderr}")

    def _invoke(self, argv: Sequence[str], tree: Path) -> ProcessResult:
        if self._env is None:
            return self._runner.run(argv, cwd=str(tree), timeout=SANDBOX_COMMAND_TIMEOUT_SECONDS)
        # A given environment is the child's whole environment: nothing of the harness's.
        return self._runner.run(
            argv,
            cwd=str(tree),
            timeout=SANDBOX_COMMAND_TIMEOUT_SECONDS,
            env=self._env,
            replace_env=True,
        )


def _initiative(tree: Path, slice_index: int) -> str:
    """The initiative index of the slice plan listing the slice in ``tree``."""
    try:
        plan = plan_file_for(slice_index, tree)
    except UnknownSliceError as exc:
        _logger.exception("slice %d is in no slice plan under %s", slice_index, tree)
        raise SliceNotInPlanError(slice_index) from exc
    return plan.name.split("-", 1)[0]
