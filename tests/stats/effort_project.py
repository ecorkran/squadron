"""One temp project for the effort report and CLI tests: slice 176 with real structure."""

from __future__ import annotations

from tests.stats.repo_support import StatsRepo

ARCH_FILE = "project-documents/user/architecture/140-slices.x.md"
TASKS_FILE = "project-documents/user/tasks/176-tasks.x.md"
SLICE_REVIEW = "project-documents/user/reviews/176-review.slice.x.md"
CODE_REVIEW = "project-documents/user/reviews/176-review.code.x.md"
DESIGN_FILE = "project-documents/user/slices/176-slice.x.md"
DESIGN_TEXT = "---\nstatus: complete\ndateCreated: 20261105\n---\n\nBody\n"

PLAN_TEXT = "1. [ ] **(176) Effort Example** — Does a thing. Dependencies: []. Risk: Low. Effort: 3/5\n"
TASK_FILE_TEXT = """## Tasks

### Task 1: First

**Effort**: 2

- [x] done
- [ ] Commit: `feat: one`

### Task 2: Second

- [x] done

Commit: `feat: two`

### Task 3: Never committed

- [ ] Commit: `docs: never made`
"""


def commit_date(day: int) -> str:
    return f"2026-11-{day:02d}T10:00:00+00:00"  # after the 941 cutoff, so not a lower bound


def review_text(verdict: str, cost: str = "") -> str:
    return f"---\ndocType: review\nverdict: {verdict}\naiModel: m\n{cost}---\n\n{verdict}\n"


def build_project(repo: StatsRepo, *, branch: bool = True, tasks: bool = True) -> None:
    """Slice 176 in a temp repo: plan, task file, design, a branch, review versions, a fix-up."""
    repo.commit("init", {"README.md": "x\n"}, commit_date(1))
    plan_files = {ARCH_FILE: PLAN_TEXT}
    if tasks:
        plan_files[TASKS_FILE] = TASK_FILE_TEXT
    repo.commit("docs: plan", plan_files, commit_date(2))
    repo.commit("docs: design", {DESIGN_FILE: DESIGN_TEXT}, commit_date(2))
    repo.commit("review: slice 1", {SLICE_REVIEW: review_text("FAIL")}, commit_date(2))
    if branch:
        repo.branch("176-slice.x")
    repo.commit("feat: one", {"src/one.py": "1\n"}, commit_date(3))
    repo.commit("wip", {"src/one.py": "1b\n"}, commit_date(4))
    repo.commit("feat: two", {"src/two.py": "2\n"}, commit_date(5))
    cost = "promptTokens: 100\ncostUsd: 0.25\ncostBasis: provider\n"
    repo.commit("review: slice 2", {SLICE_REVIEW: review_text("PASS", cost)}, commit_date(6))
    repo.commit("review: code", {CODE_REVIEW: review_text("PASS")}, commit_date(7))
    repo.commit("fix: after review", {"src/two.py": "2b\n"}, commit_date(8))


def stamp_artifacts(repo: StatsRepo, *, design: bool = True, tasks: bool = True) -> None:
    """Add 178 usage stamps to slice 176's design and task file in the working tree."""
    if design:
        stamp = "costUsd: 2.5\nusageRounds: 2\npricedRounds: 2\n"
        (repo.root / DESIGN_FILE).write_text(
            DESIGN_TEXT.replace("---\n\nBody", f"{stamp}---\n\nBody"), encoding="utf-8"
        )
    if tasks:
        stamp = "costUsd: 1.1\nusageRounds: 2\npricedRounds: 1\n"
        (repo.root / TASKS_FILE).write_text(
            f"---\nstatus: not_started\n{stamp}---\n\n{TASK_FILE_TEXT}", encoding="utf-8"
        )
