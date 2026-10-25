"""Collapse the newest planning commit run into one commit (slice 948 D1-D4, #271).

The run is the newest stretch of consecutive first-parent commits whose changed paths
all belong to one planning artifact's path set (D1). It may sit anywhere in the
unpushed history, not only at HEAD; the commits above it are recreated unchanged
(``squash_rewrite``). It is found by file, never by commit subject (D2). Unsafe
states refuse before anything is touched (D3), and a backup tag at the old HEAD
makes every rewrite recoverable (D4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from squadron.pipeline.commit_plan import (
    CommitSubject,
    CommitTarget,
    SubjectPaths,
    slice_plan_paths,
    subject_paths,
    template_for_subject,
)
from squadron.pipeline.git_ops import GitEnvironmentError, current_branch
from squadron.pipeline.squash_rewrite import (
    failure_text,
    fork_inside_run,
    git_stdout,
    later_commits,
    rewrite_run,
)
from squadron.review.git_utils import run_git
from squadron.review.persistence import (
    CfClientProtocol,
    resolve_slice_plan_file,
)

_logger = logging.getLogger(__name__)

BACKUP_TAG_PREFIX = "squash-backup/"
SHORT_SHA_LENGTH = 8  # backup tags and printed shas use the same length
_MINIMUM_RUN = 2


class SquashKind(StrEnum):
    """The planning artifact a squash collapses; the index names a slice or an initiative."""

    SLICE = "slice"  # slice design
    TASKS = "tasks"  # task breakdown
    ARCH = "arch"  # initiative architecture
    PLAN = "plan"  # initiative slice plan


# The commit subject whose path set each kind uses; PLAN has none (``slice_plan_paths``).
_SUBJECT_BY_KIND: dict[SquashKind, CommitSubject] = {
    SquashKind.SLICE: CommitSubject.DESIGN,
    SquashKind.TASKS: CommitSubject.TASKS,
    SquashKind.ARCH: CommitSubject.ARCHITECTURE,
}


class SquashRefusedError(ValueError):
    """The repository is in a state a squash will not rewrite (D3); nothing was touched."""


class SquashRewriteError(RuntimeError):
    """The rewrite failed after it started; HEAD was restored unless the text says otherwise."""


@dataclass(frozen=True)
class SquashTarget:
    """What to squash: a slice's design or tasks, or an initiative's architecture or plan."""

    kind: SquashKind
    index: int


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
    parent: str  # the commit the run starts on; the squashed commit's parent
    head: str  # HEAD at plan time; apply refuses if it has moved
    tree: str  # HEAD^{tree} at plan time; the new HEAD must have it
    later: int  # commits above the run, recreated with new parents and unchanged content
    backup_tag: str
    tag_exists: bool  # the backup tag already points at HEAD (a rerun)


def backup_tag_name(target: SquashTarget, head_sha: str) -> str:
    """The backup tag for squashing ``target`` at ``head_sha`` (D4)."""
    return f"{BACKUP_TAG_PREFIX}{target.kind}-{target.index}-{head_sha[:SHORT_SHA_LENGTH]}"


def plan_squash(
    target: SquashTarget, target_branch: str, cwd: Path, cf_client: CfClientProtocol
) -> SquashPlan | None:
    """The newest run for ``target``, or ``None`` when there is nothing to squash (D2).

    Raises:
        ValueError: cf does not know the slice, or the initiative has no such document.
        FileNotFoundError: the initiative has no architecture or slice plan file.
        SquashRefusedError: the repository state is unsafe to rewrite (D3).
        GitEnvironmentError: git could not answer.
    """
    paths = _path_set(target, cwd, cf_client)
    run = _trim_to_artifact(_find_run(paths, cwd), paths)
    if len(run) < _MINIMUM_RUN:
        _logger.info(
            "squash: nothing to squash for %s %d (run of %d)", target.kind, target.index, len(run)
        )
        return None

    run_shas = [sha for sha, _ in run]
    head = git_stdout(["rev-parse", "HEAD"], cwd).strip()
    tag = backup_tag_name(target, head)
    parent = _check_refusals(run_shas, head, tag, target_branch, cwd)
    commits = tuple(RunCommit(sha, _commit_subject(sha, cwd)) for sha in run_shas)
    return SquashPlan(
        commits=commits,
        survivor=run_shas[0],
        parent=parent.sha,
        head=head,
        tree=git_stdout(["rev-parse", "HEAD^{tree}"], cwd).strip(),
        later=len(later_commits(run_shas[-1], cwd)),
        backup_tag=tag,
        tag_exists=parent.tag_exists,
    )


def _path_set(target: SquashTarget, cwd: Path, cf_client: CfClientProtocol) -> SubjectPaths:
    """The files ``target``'s commits may touch: the commit rules' set plus parent documents.

    Answering a review often edits a parent document too (a design review response
    amends the architecture), so those edits must not end the run. The slice plan gets
    no parent: architecture review responses often amend the plan, and a commit touching
    both must belong to the architecture run alone, or squashing one would swallow the other.
    """
    if target.kind is SquashKind.PLAN:
        return slice_plan_paths(target.index, cwd)
    subject = _SUBJECT_BY_KIND[target.kind]
    template = template_for_subject(subject)
    if subject is CommitSubject.ARCHITECTURE:
        commit_target = CommitTarget(subject, None, str(target.index), template, 0)
        paths = subject_paths(commit_target, cwd, cf_client)
        return paths.with_context(_existing(resolve_slice_plan_file, target.index, cwd), cwd)
    commit_target = CommitTarget(subject, target.index, None, template, 0)
    paths = subject_paths(commit_target, cwd, cf_client)
    arch_file = cf_client.get_project().arch_file  # the client already made it a path
    return paths.with_context([arch_file] if arch_file else [], cwd)


def _existing(resolve: Callable[[int, Path], str], index: int, cwd: Path) -> list[str]:
    """The initiative document ``resolve`` finds, or none."""
    try:
        return [resolve(index, cwd)]
    except FileNotFoundError:
        # An initiative without this document has nothing to add to the path set.
        return []


def apply_squash(plan: SquashPlan, cwd: Path) -> str:
    """Collapse ``plan``'s run into one commit; returns the squashed commit's sha.

    Commits above the run are recreated onto it, then the branch moves with one
    compare-and-swap ref update. The working tree and index are never touched: the
    new HEAD has the old HEAD's tree.

    Raises:
        SquashRewriteError: the rewrite failed; HEAD was restored to the backup tag
            unless the error text says the restore failed too.
        SquashRefusedError: HEAD moved or the tree got dirty since planning; nothing touched.
        GitEnvironmentError: git could not create the backup tag.
    """
    _check_unchanged_since_plan(plan, cwd)
    if plan.tag_exists:
        _logger.info("squash: reusing existing backup tag %s at HEAD", plan.backup_tag)
    else:
        git_stdout(["tag", plan.backup_tag, "HEAD"], cwd)
    _logger.info(
        "squash: backup tag %s; recover with: git reset --hard %s", plan.backup_tag, plan.backup_tag
    )

    newest = plan.commits[-1].sha
    try:
        rewritten = rewrite_run(plan.survivor, newest, plan.parent, plan.head, cwd)
    except GitEnvironmentError as exc:
        _restore(plan, cwd, f"writing the rewritten commits failed: {exc}")
    message = f"sq squash: {len(plan.commits)} commits, {plan.later} later commits recreated"
    moved = run_git(["update-ref", "-m", message, "HEAD", rewritten.head, plan.head], cwd=str(cwd))
    if moved is None or moved.returncode != 0:
        _restore(plan, cwd, f"git update-ref HEAD failed: {failure_text(moved)}")
    tree = run_git(["rev-parse", "HEAD^{tree}"], cwd=str(cwd))
    if tree is None or tree.returncode != 0 or tree.stdout.strip() != plan.tree:
        found = tree.stdout.strip() if tree is not None else failure_text(tree)
        _restore(plan, cwd, f"tree mismatch after squash: expected {plan.tree}, got {found}")
    _logger.info("squash: %s; new HEAD %s", message, rewritten.head[:SHORT_SHA_LENGTH])
    return rewritten.squashed


def _check_unchanged_since_plan(plan: SquashPlan, cwd: Path) -> None:
    """Refuse if HEAD moved or the tree got dirty since ``plan_squash`` checked them.

    The restore path runs ``reset --hard``, so it must only ever discard the squash itself.
    """
    head = git_stdout(["rev-parse", "HEAD"], cwd).strip()
    if head != plan.head:
        moved = f"{plan.head[:SHORT_SHA_LENGTH]} -> {head[:SHORT_SHA_LENGTH]}"
        _refuse(f"HEAD moved since the squash was planned ({moved}); nothing rewritten")
    if git_stdout(["status", "--porcelain"], cwd).strip():
        _refuse("the working tree changed since the squash was planned; nothing rewritten")


@dataclass(frozen=True)
class _Checked:
    """What a passed refusal check learned."""

    sha: str  # the run's parent
    tag_exists: bool


def _check_refusals(run: list[str], head: str, tag: str, target_branch: str, cwd: Path) -> _Checked:
    """Refuse an unsafe rewrite (D3); touches nothing. Returns the run's parent.

    Pushed commits need no check here: ``_find_run`` never walks past them.
    """
    if git_stdout(["status", "--porcelain"], cwd).strip():
        _refuse("the working tree is not clean; commit or stash changes first")
    parents = git_stdout(["rev-list", "--parents", "-n", "1", run[0]], cwd).split()
    if len(parents) < 2:
        _refuse(f"the run reaches the root commit {run[0][:SHORT_SHA_LENGTH]}; no parent to build on")
    branch = current_branch(str(cwd))
    if branch != target_branch:
        _refuse(f"HEAD is on {branch!r}, not the target branch {target_branch!r}")
    forked = fork_inside_run(run, cwd)
    if forked is not None:
        _refuse(
            f"a branch forked from inside the run (at {forked[:SHORT_SHA_LENGTH]}) was merged "
            "above it; squashing would leave the run's commits in history"
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
    """The newest run, oldest first, with each commit's changed paths (D1, #271).

    Walks unpushed first-parent history from HEAD. A merge or a commit touching any
    other file ends a stretch; the run is the newest stretch with at least one commit
    that touches the artifact itself. Stretches without one (DEVLOG-only commits
    between other work) are skipped. Commits in a remote-tracking ref are never
    walked, so a pushed commit is never rewritten.
    """
    stretch: list[tuple[str, frozenset[str]]] = []
    unpushed = git_stdout(
        ["rev-list", "--first-parent", "--parents", "HEAD", "--not", "--remotes"], cwd
    )
    for line in unpushed.splitlines():
        sha, *parents = line.split()
        changed = _changed_paths(sha, cwd) if len(parents) < 2 else None
        if changed is not None and all(paths.contains(p) for p in changed):
            stretch.append((sha, changed))
            continue
        if _touches_artifact(stretch, paths):
            break
        stretch = []
    if not _touches_artifact(stretch, paths):
        return []
    stretch.reverse()
    return stretch


def _changed_paths(sha: str, cwd: Path) -> frozenset[str]:
    listing = git_stdout(["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", sha], cwd)
    return frozenset(p for p in listing.split("\0") if p)


def _touches_artifact(stretch: list[tuple[str, frozenset[str]]], paths: SubjectPaths) -> bool:
    return any(paths.is_artifact(p) for _, changed in stretch for p in changed)


def _trim_to_artifact(
    run: list[tuple[str, frozenset[str]]], paths: SubjectPaths
) -> list[tuple[str, frozenset[str]]]:
    """Drop commits from both ends that do not belong at that end of the run (D1, #271).

    The survivor's message names the artifact, so a leading commit that touched only
    DEVLOG, a parent document or a review is left out of the run. A trailing commit
    that touched only a parent document (and DEVLOG or reviews) is left out too.
    """
    start = 0
    while start < len(run) and not any(paths.is_artifact(p) for p in run[start][1]):
        start += 1
    end = len(run)
    # A trailing commit that only edits a parent document belongs to that document's run.
    while end > start and _parent_document_only(run[end - 1][1], paths):
        end -= 1
    return run[start:end]


def _parent_document_only(changed: frozenset[str], paths: SubjectPaths) -> bool:
    return any(paths.is_context(p) for p in changed) and not any(paths.is_artifact(p) for p in changed)


def _commit_subject(sha: str, cwd: Path) -> str:
    return git_stdout(["show", "-s", "--format=%s", sha], cwd).strip()


def _restore(plan: SquashPlan, cwd: Path, cause: str) -> NoReturn:
    """Put HEAD back on the backup tag after a failed rewrite, then raise (D3)."""
    _logger.error("squash: %s; restoring %s", cause, plan.backup_tag)
    restored = run_git(["reset", "-q", "--hard", plan.backup_tag], cwd=str(cwd))
    if restored is None or restored.returncode != 0:
        _logger.error("squash: restore failed: %s", failure_text(restored))
        raise SquashRewriteError(
            f"{cause}; restoring failed ({failure_text(restored)}); "
            f"recover with: git reset --hard {plan.backup_tag}"
        )
    raise SquashRewriteError(f"{cause}; HEAD restored to {plan.backup_tag}")


def _refuse(message: str) -> NoReturn:
    _logger.warning("squash refused: %s", message)
    raise SquashRefusedError(message)
