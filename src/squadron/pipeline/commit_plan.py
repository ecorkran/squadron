"""What a pipeline commit stages and says (slice 196 D1, D2).

One builder serves both executors: ``CommitAction`` (SDK) and the hidden
``sq _commit`` command (prompt-only) call the same function, so their results
cannot drift.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, replace
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
    resolve_slice_plan_file,
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


def template_for_subject(subject: CommitSubject) -> str:
    """The review template whose reviews ``subject``'s artifact gets; raises when none does."""
    for template, mapped in _SUBJECT_BY_TEMPLATE.items():
        if mapped is subject:
            return template
    raise UnmappedTemplateError(f"commit subject {subject!r} has no review template")


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
    is_context: bool = False  # a parent planning document (slice plan, architecture)


@dataclass(frozen=True)
class SubjectPaths:
    """Every path a target's commits may touch, as the repository root names it.

    The candidates are computed; archived review copies cannot be (their names carry
    a timestamp), so they are matched by the prefix rule in ``is_archived_review``.
    """

    root: Path
    candidates: tuple[_Candidate, ...]
    archive_prefixes: tuple[str, ...]  # repo path of each review, ``.md`` removed, under archive/

    def is_archived_review(self, repo_path: str) -> bool:
        """Whether ``repo_path`` is an archived copy of one of the target's reviews."""
        return any(
            repo_path == f"{prefix}.md"
            or (repo_path.startswith(f"{prefix}.") and repo_path.endswith(".md"))
            for prefix in self.archive_prefixes
        )

    def is_artifact(self, repo_path: str) -> bool:
        """Whether ``repo_path`` is the target's artifact itself (not a review, plan or DEVLOG)."""
        return any(c.is_artifact and c.repo_path == repo_path for c in self.candidates)

    def contains(self, repo_path: str) -> bool:
        """Whether ``repo_path`` (relative to the repository root) belongs to the target."""
        return any(c.repo_path == repo_path for c in self.candidates) or self.is_archived_review(
            repo_path
        )

    def is_context(self, repo_path: str) -> bool:
        """Whether ``repo_path`` is a parent planning document of the target."""
        return any(c.is_context and c.repo_path == repo_path for c in self.candidates)

    def with_context(self, paths: Iterable[str], cwd: Path) -> SubjectPaths:
        """A copy that also covers ``paths`` (relative to ``cwd``) as parent documents."""
        extra = tuple(_candidate(p, cwd, self.root, is_context=True) for p in paths)
        return replace(self, candidates=(*self.candidates, *extra))


def subject_paths(target: CommitTarget, cwd: Path, cf_client: CfClientProtocol) -> SubjectPaths:
    """The path set ``target`` covers; reads no git status, so dirtiness is irrelevant.

    Raises:
        GitEnvironmentError: git could not report the repository root.
        ValueError: ``target`` lacks the slice or plan its subject needs.
    """
    root = _repo_root(cwd)
    candidates = tuple(_candidates(target, cwd, root, cf_client))
    prefixes: list[str] = []
    for review in (c for c in candidates if c.is_review):
        directory, _, filename = review.repo_path.rpartition("/")
        prefixes.append(f"{directory}/{ARCHIVE_SUBDIR}/{filename.removesuffix('.md')}")
    return SubjectPaths(root, candidates, tuple(prefixes))


def slice_plan_paths(plan_index: int, cwd: Path) -> SubjectPaths:
    """The path set of initiative ``plan_index``'s slice plan: the plan file and ``DEVLOG.md``.

    No review template targets a slice plan, so there are no reviews to include.

    Raises:
        GitEnvironmentError: git could not report the repository root.
        FileNotFoundError: no slice plan file exists for ``plan_index``.
    """
    root = _repo_root(cwd)
    plan_file = resolve_slice_plan_file(plan_index, cwd)
    candidates = (
        _candidate(plan_file, cwd, root, is_artifact=True),
        _candidate(DEVLOG_FILE, cwd, root),
    )
    return SubjectPaths(root, candidates, ())


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

    subject = subject_paths(target, cwd, cf_client)
    dirty = _read_dirty_paths(cwd)
    present = [c for c in subject.candidates if c.repo_path in dirty]
    present += _archived_reviews(subject, dirty, cwd)

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


def _archived_reviews(subject: SubjectPaths, dirty: dict[str, _Dirty], cwd: Path) -> list[_Candidate]:
    """Dirty archive copies of the reviews this commit covers.

    Saving a review archives the one it replaces under ``archive/``, with a timestamp in
    the name for older generations, so the exact names cannot be computed. They are
    matched against what git reports as changed, and travel with their review.
    """
    return [
        _Candidate(
            path=Path(os.path.relpath(subject.root / repo_path, cwd)).as_posix(), repo_path=repo_path
        )
        for repo_path in sorted(dirty)
        if subject.is_archived_review(repo_path)
    ]


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
        found.append(_candidate(f"{ARCHITECTURE_DIR}/{plan_file}", cwd, root, is_context=True))
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
    path: str,
    cwd: Path,
    root: Path,
    *,
    is_artifact: bool = False,
    is_review: bool = False,
    is_context: bool = False,
) -> _Candidate:
    repo_path = Path(os.path.relpath((cwd / path).resolve(), root)).as_posix()
    return _Candidate(path, repo_path, is_artifact, is_review, is_context)


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
