"""Collapse the newest planning commit run into one commit (slice 948 D1-D4).

The run is the newest consecutive first-parent commits ending at HEAD whose changed
paths all belong to one planning artifact's path set (D1). It is found by file,
never by commit subject (D2). Unsafe states refuse before anything is touched (D3),
and a backup tag at the old HEAD makes every rewrite recoverable (D4).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NoReturn

from squadron.pipeline.commit_plan import (
    DEVLOG_FILE,
    CommitSubject,
    CommitTarget,
    SubjectPaths,
    subject_paths,
    template_for_subject,
)
from squadron.pipeline.git_ops import GitEnvironmentError, current_branch
from squadron.review.git_utils import run_git
from squadron.review.persistence import CfClientProtocol

_logger = logging.getLogger(__name__)

# The planning artifacts a squash may collapse; every caller validates against this.
SQUASHABLE_SUBJECTS = frozenset({CommitSubject.DESIGN, CommitSubject.TASKS, CommitSubject.ARCHITECTURE})
BACKUP_TAG_PREFIX = "squash-backup/"
_SHORT_SHA_LENGTH = 8
_MINIMUM_RUN = 2


class SquashRefusedError(ValueError):
    """The repository is in a state a squash will not rewrite (D3); nothing was touched."""


class SquashRewriteError(RuntimeError):
    """The rewrite failed after it started; HEAD was restored unless the text says otherwise."""


@dataclass(frozen=True)
class RunCommit:
    """One commit of a run."""

    sha: str
    subject: str


@dataclass(frozen=True)
class SquashPlan:
    """A run to collapse, and everything the rewrite needs to do and verify it."""

    commits: tuple[RunCommit, ...]  # oldest first
    survivor: str  # the oldest commit: its message and author are kept (D5)
    parent: str  # the commit the run starts on; the soft reset target
    tree: str  # HEAD^{tree} at plan time; the new commit must have it
    backup_tag: str
    tag_exists: bool  # the backup tag already points at HEAD (a rerun)


def backup_tag_name(subject: CommitSubject, index: int | str, head_sha: str) -> str:
    """The backup tag for a squash of ``subject`` ``index`` at ``head_sha`` (D4)."""
    return f"{BACKUP_TAG_PREFIX}{subject}-{index}-{head_sha[:_SHORT_SHA_LENGTH]}"


def check_squash_scope(subject: str, has_slice: bool, has_plan: bool) -> CommitSubject:
    """The subject as a ``CommitSubject``, if it may be squashed with this scope.

    ``architecture`` is initiative-scoped and takes a plan; ``design`` and ``tasks``
    take a slice. Exactly one of the two is allowed.

    Raises:
        ValueError: the subject is not squashable, or the scope does not match it.
    """
    allowed = ", ".join(sorted(SQUASHABLE_SUBJECTS))
    if subject not in SQUASHABLE_SUBJECTS:
        raise ValueError(f"cannot squash {subject!r}: the subject must be one of {allowed}")
    parsed = CommitSubject(subject)
    if parsed is CommitSubject.ARCHITECTURE:
        if has_slice or not has_plan:
            raise ValueError("an architecture squash takes --plan N and no --slice")
    elif has_plan or not has_slice:
        raise ValueError(f"a {parsed} squash takes --slice N and no --plan")
    return parsed


def plan_squash(
    target: CommitTarget, target_branch: str, cwd: Path, cf_client: CfClientProtocol
) -> SquashPlan | None:
    """The newest run for ``target``, or ``None`` when there is nothing to squash (D2).

    Raises:
        ValueError: the target's subject or scope cannot be squashed.
        SquashRefusedError: the repository state is unsafe to rewrite (D3).
        GitEnvironmentError: git could not answer.
    """
    subject = check_squash_scope(
        target.subject, target.slice_index is not None, target.plan is not None
    )
    scoped = replace(target, review_template=template_for_subject(subject))
    paths = subject_paths(scoped, cwd, cf_client)
    run = _trim_devlog_only(_find_run(paths, cwd), _devlog_repo_path(paths, cwd))
    if len(run) < _MINIMUM_RUN:
        _logger.info("squash: nothing to squash for %s (run of %d)", subject, len(run))
        return None

    oldest_sha = run[0][0]
    head = _git(["rev-parse", "HEAD"], cwd).strip()
    index = target.plan if target.slice_index is None else target.slice_index
    tag = backup_tag_name(subject, str(index), head)
    parent = _check_refusals(oldest_sha, head, tag, target_branch, cwd)
    commits = tuple(RunCommit(sha, _commit_subject(sha, cwd)) for sha, _ in run)
    return SquashPlan(
        commits=commits,
        survivor=oldest_sha,
        parent=parent.sha,
        tree=_git(["rev-parse", "HEAD^{tree}"], cwd).strip(),
        backup_tag=tag,
        tag_exists=parent.tag_exists,
    )


def apply_squash(plan: SquashPlan, cwd: Path) -> str:
    """Collapse ``plan``'s run into one commit; returns the new commit's sha.

    Raises:
        SquashRewriteError: the rewrite failed; HEAD was restored to the backup tag
            unless the error text says the restore failed too.
        GitEnvironmentError: git could not create the backup tag.
    """
    if plan.tag_exists:
        _logger.info("squash: reusing existing backup tag %s at HEAD", plan.backup_tag)
    else:
        _git(["tag", plan.backup_tag, "HEAD"], cwd)
    _logger.info(
        "squash: backup tag %s; recover with: git reset --hard %s", plan.backup_tag, plan.backup_tag
    )

    reset = run_git(["reset", "-q", "--soft", plan.parent], cwd=str(cwd))
    if reset is None or reset.returncode != 0:
        _restore(plan, cwd, f"git reset --soft {plan.parent} failed: {_failure_text(reset)}")
    commit = run_git(["commit", "-q", "-C", plan.survivor], cwd=str(cwd))
    if commit is None or commit.returncode != 0:
        _restore(plan, cwd, f"git commit -C {plan.survivor} failed: {_failure_text(commit)}")
    tree = run_git(["rev-parse", "HEAD^{tree}"], cwd=str(cwd))
    if tree is None or tree.returncode != 0 or tree.stdout.strip() != plan.tree:
        found = tree.stdout.strip() if tree is not None else _failure_text(tree)
        _restore(plan, cwd, f"tree mismatch after squash: expected {plan.tree}, got {found}")
    return _git(["rev-parse", "HEAD"], cwd).strip()


@dataclass(frozen=True)
class _Checked:
    """What a passed refusal check learned."""

    sha: str  # the run's parent
    tag_exists: bool


def _check_refusals(oldest_sha: str, head: str, tag: str, target_branch: str, cwd: Path) -> _Checked:
    """Refuse an unsafe rewrite (D3); touches nothing. Returns the run's parent."""
    if _git(["status", "--porcelain"], cwd).strip():
        _refuse("the working tree is not clean; commit or stash changes first")
    parents = _git(["rev-list", "--parents", "-n", "1", oldest_sha], cwd).split()
    if len(parents) < 2:
        _refuse(
            f"the run reaches the root commit {oldest_sha[:_SHORT_SHA_LENGTH]}; no parent to reset to"
        )
    branch = current_branch(str(cwd))
    if branch != target_branch:
        _refuse(f"HEAD is on {branch!r}, not the target branch {target_branch!r}")
    remotes = _git(
        ["for-each-ref", "--format=%(refname)", "--contains", oldest_sha, "refs/remotes"], cwd
    ).split()
    if remotes:
        _refuse(
            f"the run is already in remote-tracking ref(s) {', '.join(remotes)}; "
            "this check uses refs as of the last fetch and does not contact the remote"
        )
    tagged = run_git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"], cwd=str(cwd))
    if tagged is None:
        raise GitEnvironmentError(
            f"git rev-parse --verify refs/tags/{tag}: git timed out or could not run"
        )
    tag_exists = tagged.returncode == 0
    if tag_exists and tagged.stdout.strip() != head:
        _refuse(f"backup tag {tag} already exists and points at {tagged.stdout.strip()}, not HEAD")
    return _Checked(parents[1], tag_exists)


def _find_run(paths: SubjectPaths, cwd: Path) -> list[tuple[str, frozenset[str]]]:
    """The run ending at HEAD, oldest first, with each commit's changed paths (D1)."""
    run: list[tuple[str, frozenset[str]]] = []
    for line in _git(["rev-list", "--first-parent", "--parents", "HEAD"], cwd).splitlines():
        sha, *parents = line.split()
        if len(parents) > 1:
            break  # a merge commit ends the run
        changed = frozenset(
            p
            for p in _git(
                ["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", sha], cwd
            ).split("\0")
            if p
        )
        if not all(paths.contains(p) for p in changed):
            break  # a foreign commit ends the run
        run.append((sha, changed))
    run.reverse()
    return run


def _trim_devlog_only(
    run: list[tuple[str, frozenset[str]]], devlog: str
) -> list[tuple[str, frozenset[str]]]:
    """Drop DEVLOG-only commits from the oldest end, so the survivor is an artifact commit."""
    start = 0
    while start < len(run) and run[start][1] <= {devlog}:
        start += 1
    return run[start:]


def _devlog_repo_path(paths: SubjectPaths, cwd: Path) -> str:
    return Path(os.path.relpath((cwd / DEVLOG_FILE).resolve(), paths.root)).as_posix()


def _commit_subject(sha: str, cwd: Path) -> str:
    return _git(["show", "-s", "--format=%s", sha], cwd).strip()


def _restore(plan: SquashPlan, cwd: Path, cause: str) -> NoReturn:
    """Put HEAD back on the backup tag after a failed rewrite, then raise (D3)."""
    _logger.error("squash: %s; restoring %s", cause, plan.backup_tag)
    restored = run_git(["reset", "-q", "--hard", plan.backup_tag], cwd=str(cwd))
    if restored is None or restored.returncode != 0:
        _logger.error("squash: restore failed: %s", _failure_text(restored))
        raise SquashRewriteError(
            f"{cause}; restoring failed ({_failure_text(restored)}); "
            f"recover with: git reset --hard {plan.backup_tag}"
        )
    raise SquashRewriteError(f"{cause}; HEAD restored to {plan.backup_tag}")


def _refuse(message: str) -> NoReturn:
    _logger.warning("squash refused: %s", message)
    raise SquashRefusedError(message)


def _git(args: list[str], cwd: Path) -> str:
    """git's stdout; raises ``GitEnvironmentError`` naming the command when it fails."""
    result = run_git(args, cwd=str(cwd))
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(f"git {' '.join(args)} failed: {_failure_text(result)}")
    return result.stdout


def _failure_text(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return "git timed out or could not run"
    return result.stderr.strip() or f"exit {result.returncode}"
