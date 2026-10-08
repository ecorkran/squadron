"""What a pipeline commit stages and says (slice 196 D1, D2).

One builder serves both executors: ``CommitAction`` (SDK) and the hidden
``sq _commit`` command (prompt-only) call the same function, so their results
cannot drift.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.documents.frontmatter import read_frontmatter
from squadron.integrations.context_forge import ARCHITECTURE_DIR
from squadron.pipeline.git_ops import GitEnvironmentError, SliceNotInPlanError
from squadron.review.git_utils import run_git
from squadron.review.parts import worst_verdict
from squadron.review.persistence import (
    ARCHIVE_SUBDIR,
    REVIEWS_DIR,
    CfClientProtocol,
    SliceInfo,
    resolve_arch_file,
    resolve_slice_info,
)
from squadron.review.save_target import ArchTarget
from squadron.review.template_inputs import review_artifact_stems
from squadron.review.templates import BuiltinReviewTemplate

_logger = logging.getLogger(__name__)

# The development log the devlog step appends to; also a candidate path for every
# planning commit, since a step may write an entry as it works.
DEVLOG_FILE = "DEVLOG.md"

# Action param keys a scoped commit reads. The step or loop that builds the commit
# action sets them; ``CommitAction`` and the hidden ``sq _commit`` read them.
SUBJECT_PARAM = "commit_subject"
SLICE_PARAM = "slice"
PLAN_PARAM = "plan"
REVIEW_TEMPLATE_PARAM = "review_template"
# A user pipeline's own commit: explicit paths, and a message used verbatim.
PATHS_PARAM = "paths"
MESSAGE_PARAM = "message"


class CommitSubject(StrEnum):
    """What a commit is about; it decides the candidate paths and the message."""

    DESIGN = "design"
    TASKS = "tasks"
    ARCHITECTURE = "architecture"
    CODE = "code"
    DEVLOG = "devlog"


class CommitTargetError(ValueError):
    """A commit target lacks the slice or plan its subject needs (an item failure)."""


class UnmappedTemplateError(ValueError):
    """A review template has no commit subject, so a loop round's scope is unknown."""


# The one template -> subject definition. A loop round takes its subject from its
# last review action's template; the executor and the prompt renderer both use it.
_SUBJECT_BY_TEMPLATE: dict[str, CommitSubject] = {
    BuiltinReviewTemplate.SLICE: CommitSubject.DESIGN,
    BuiltinReviewTemplate.TASKS: CommitSubject.TASKS,
    BuiltinReviewTemplate.CODE: CommitSubject.CODE,
    BuiltinReviewTemplate.ARCH: CommitSubject.ARCHITECTURE,
}


def subject_for_template(template: str) -> CommitSubject:
    """The commit subject a review ``template`` implies; raises when it has none."""
    try:
        return _SUBJECT_BY_TEMPLATE[template]
    except KeyError:
        known = ", ".join(sorted(_SUBJECT_BY_TEMPLATE))
        raise UnmappedTemplateError(
            f"commit scope unknown: review template {template!r} has no commit subject (known: {known})"
        ) from None


@dataclass(frozen=True)
class CommitTarget:
    """The work a commit covers."""

    subject: CommitSubject
    slice_index: int | None  # None means initiative-scoped (plan)
    plan: str | None
    review_template: str | None
    round: int  # 0 for the step's own commit, n for loop round n


@dataclass(frozen=True)
class CommitPlan:
    """What to stage and the message to commit with."""

    paths: tuple[str, ...]  # empty means nothing to commit
    stage_all: bool  # CODE only (D3)
    message: str
    left_out: tuple[str, ...]  # dirty paths not staged, named in a WARNING


class _Dirty(StrEnum):
    """How a path shows up in ``git status``."""

    NEW = "new"  # untracked or added
    CHANGED = "changed"  # modified or deleted


@dataclass(frozen=True)
class _Candidate:
    """A path a commit may stage."""

    path: str  # as cf and the persistence helpers name it, relative to cwd
    repo_path: str  # relative to the repository root, which is how git status reports it
    is_artifact: bool = False
    is_review: bool = False


def build_commit_plan(target: CommitTarget, cwd: Path, cf_client: CfClientProtocol) -> CommitPlan:
    """What ``target``'s commit stages, and the message to commit it with (D1, D2).

    Staged paths are the target's candidate paths that git shows as changed. Every
    candidate is computed from cf and the persistence helpers, never searched for.
    The review verdict in the message is read from the review file on disk, so the
    SDK executor and prompt-only mode agree.

    Raises:
        GitEnvironmentError: git could not report its status or repository root.
        ValueError: ``target`` lacks the slice or plan its subject needs.
    """
    from squadron.pipeline.commit_message import ArtifactChange, StagedFacts, compose_message

    root = _repo_root(cwd)
    dirty = _read_dirty_paths(cwd)
    candidates = _candidates(target, cwd, root, cf_client)
    present = [c for c in candidates if c.repo_path in dirty]
    present += _archived_reviews(candidates, dirty, cwd, root)

    if target.subject is CommitSubject.CODE:
        # Code can touch any file (D3): everything dirty belongs to the slice.
        paths = tuple(sorted(dirty))
        left_out: tuple[str, ...] = ()
    else:
        paths = tuple(c.path for c in present)
        left_out = tuple(sorted(dirty.keys() - {c.repo_path for c in present}))

    artifact = next((c for c in present if c.is_artifact), None)
    reviews = [c for c in present if c.is_review]
    facts = StagedFacts(
        artifact=(
            None
            if artifact is None
            else ArtifactChange.ADD
            if dirty[artifact.repo_path] is _Dirty.NEW
            else ArtifactChange.REVISE
        ),
        review_staged=bool(reviews),
        review_verdict=_staged_verdict(reviews, cwd),
    )
    return CommitPlan(
        paths=paths,
        stage_all=target.subject is CommitSubject.CODE,
        message=compose_message(target, facts),
        left_out=left_out,
    )


def _staged_verdict(reviews: list[_Candidate], cwd: Path) -> str | None:
    """The worst verdict across the staged review parts, or None if any is unreadable.

    A split review is judged by its worst part, as the review action folds it; a
    part with no readable verdict leaves the message without one (each is logged).
    """
    verdicts = [read_review_verdict(cwd / review.path) for review in reviews]
    readable = [v for v in verdicts if v is not None]
    if not readable or len(readable) < len(verdicts):
        return None
    try:
        return worst_verdict(readable)
    except ValueError:
        # A verdict outside Verdict is written by hand or by an older squadron;
        # the message still commits, it just omits the verdict.
        _logger.warning("commit: unrecognized review verdict in %s; message omits it", readable)
        return None


def _archived_reviews(
    candidates: list[_Candidate], dirty: dict[str, _Dirty], cwd: Path, root: Path
) -> list[_Candidate]:
    """Dirty archive copies of the reviews this commit covers.

    Saving a review archives the one it replaces under ``archive/``, with a timestamp in
    the name for older generations, so the exact names cannot be computed. They are
    matched by prefix against what git reports as changed, and travel with their review.
    """
    found: list[_Candidate] = []
    for review in (c for c in candidates if c.is_review):
        directory, _, filename = review.repo_path.rpartition("/")
        stem = filename.removesuffix(".md")
        archive_prefix = f"{directory}/{ARCHIVE_SUBDIR}/{stem}"
        for repo_path in sorted(dirty):
            if repo_path == f"{archive_prefix}.md" or (
                repo_path.startswith(f"{archive_prefix}.") and repo_path.endswith(".md")
            ):
                relative = Path(os.path.relpath(root / repo_path, cwd)).as_posix()
                found.append(_Candidate(path=relative, repo_path=repo_path))
    return found


def read_review_verdict(review_file: Path) -> str | None:
    """The ``verdict`` frontmatter value as written, or ``None`` when unreadable (logged)."""
    if not review_file.is_file():
        # A deleted review is still a change to commit; it just has no verdict.
        _logger.warning("commit: review %s is not on disk; message omits its verdict", review_file)
        return None
    frontmatter = read_frontmatter(review_file)
    verdict = frontmatter.get("verdict") if frontmatter is not None else None
    if not isinstance(verdict, str) or not verdict:
        _logger.warning("commit: no readable verdict in %s; message omits it", review_file)
        return None
    return verdict


def _candidates(
    target: CommitTarget, cwd: Path, root: Path, cf_client: CfClientProtocol
) -> list[_Candidate]:
    """Every path ``target``'s commit may stage, computed and never searched for."""
    paths: list[_Candidate]
    match target.subject:
        case CommitSubject.DEVLOG:
            return [_candidate(DEVLOG_FILE, cwd, root)]
        case CommitSubject.ARCHITECTURE:
            paths = _architecture_candidates(target, cwd, root)
        case CommitSubject.CODE:
            # Only the review is read; the staged set is everything dirty.
            paths = _review_candidates(target, _slice_info(target, cf_client), cwd, root)
            return paths
        case CommitSubject.DESIGN | CommitSubject.TASKS:
            paths = _slice_candidates(target, cwd, root, cf_client)
    return [*paths, _candidate(DEVLOG_FILE, cwd, root)]


def _slice_candidates(
    target: CommitTarget, cwd: Path, root: Path, cf_client: CfClientProtocol
) -> list[_Candidate]:
    """The slice artifact, its review, and the slice plan file."""
    from squadron.events.builtin.artifact_paths import artifact_paths
    from squadron.pipeline.steps.phase import ArtifactKind

    info = _slice_info(target, cf_client)
    kind = ArtifactKind.DESIGN if target.subject is CommitSubject.DESIGN else ArtifactKind.TASKS
    found = [_candidate(p, cwd, root, is_artifact=True) for p in artifact_paths(kind, info)]
    found += _review_candidates(target, info, cwd, root)
    slice_plan = str(cf_client.get_project().slice_plan)
    if slice_plan:
        # cf reports the plan as a bare stem; tolerate one that already has its suffix.
        plan_file = slice_plan if slice_plan.endswith(".md") else f"{slice_plan}.md"
        found.append(_candidate(f"{ARCHITECTURE_DIR}/{plan_file}", cwd, root))
    return found


def _architecture_candidates(target: CommitTarget, cwd: Path, root: Path) -> list[_Candidate]:
    """The initiative's architecture document and its review."""
    if target.plan is None:
        raise CommitTargetError("an architecture commit needs a plan index")
    try:
        index = int(target.plan)
    except ValueError:
        raise CommitTargetError(
            f"an architecture commit needs a plan index, got {target.plan!r}"
        ) from None
    arch_file = resolve_arch_file(index, cwd)
    found = [_candidate(arch_file, cwd, root, is_artifact=True)]
    if target.review_template is not None:
        stem = ArchTarget(index, arch_file, str(cwd)).filename_stem(target.review_template)
        found.append(_candidate(str(REVIEWS_DIR / f"{stem}.md"), cwd, root, is_review=True))
    return found


def _review_candidates(
    target: CommitTarget, info: SliceInfo, cwd: Path, root: Path
) -> list[_Candidate]:
    """Every review file for ``target``'s template — one per part of a split review —
    named exactly as the save path names it."""
    if target.review_template is None:
        return []
    stems = review_artifact_stems(target.review_template, info, str(cwd))
    return [_candidate(str(REVIEWS_DIR / f"{stem}.md"), cwd, root, is_review=True) for stem in stems]


def _slice_info(target: CommitTarget, cf_client: CfClientProtocol) -> SliceInfo:
    """cf's facts for the target's slice; a slice missing from the plan is an item failure."""
    try:
        return resolve_slice_info(cf_client, _require_slice(target))
    except CommitTargetError:
        raise
    except ValueError as exc:
        raise SliceNotInPlanError(str(exc)) from exc


def _require_slice(target: CommitTarget) -> int:
    if target.slice_index is None:
        raise CommitTargetError(f"a {target.subject} commit needs a slice index")
    return target.slice_index


def _candidate(
    path: str, cwd: Path, root: Path, *, is_artifact: bool = False, is_review: bool = False
) -> _Candidate:
    repo_path = Path(os.path.relpath((cwd / path).resolve(), root)).as_posix()
    return _Candidate(path, repo_path, is_artifact=is_artifact, is_review=is_review)


def _repo_root(cwd: Path) -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], cwd=str(cwd))
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(
            f"cannot find the git repository root from {cwd}: "
            f"{result.stderr.strip() if result else 'git timed out or could not run'}"
        )
    return Path(result.stdout.strip()).resolve()


def _read_dirty_paths(cwd: Path) -> dict[str, _Dirty]:
    """Every changed or untracked path, relative to the repository root.

    ``-z`` output is unquoted; ``-uall`` lists files inside wholly untracked
    directories, so a candidate inside one is not hidden behind its parent.
    """
    result = run_git(["status", "--porcelain", "-z", "-uall"], cwd=str(cwd))
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(
            "cannot read git status: "
            f"{result.stderr.strip() if result else 'git timed out or could not run'}"
        )
    dirty: dict[str, _Dirty] = {}
    entries = iter(result.stdout.split("\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            next(entries, None)  # a rename or copy carries its source path as the next entry
        dirty[path] = _Dirty.NEW if code == "??" or code[0] == "A" else _Dirty.CHANGED
    return dirty
