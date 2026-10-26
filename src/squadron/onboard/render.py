"""Plain-text rendering of an ``OnboardReport`` (slice 440 D9)."""

from __future__ import annotations

from squadron.onboard import OnboardReport


def _graph_line(report: OnboardReport) -> str:
    graph = report.graph
    if not graph["present"]:
        return "absent"
    behind = graph["commits_behind"]
    if behind is None:
        return "present, staleness unknown"
    return "present, current" if behind == 0 else f"present, {behind} commits behind"


def _comprehension_line(report: OnboardReport) -> str:
    if report.comprehension is None:
        return "none"
    name = report.comprehension.relative_to(report.root).as_posix()
    return f"{name} (older than the graph)" if report.comprehension_older_than_graph else name


def format_report_text(report: OnboardReport) -> str:
    """Outcome, what exists, cf's notices, then the next step and why."""
    lines = [
        f"Root: {report.root}",
        f"Outcome: {report.outcome.value}",
        f"Registered with cf: {'yes' if report.registered else 'no'}",
        f"Knowledge graph: {_graph_line(report)}",
        f"Comprehension doc: {_comprehension_line(report)}",
        f"Concept: {report.concept or 'none'}",
        *(f"Notice: {notice}" for notice in report.notices),
    ]
    step = report.next
    next_line = f"Next: {step.step.value} ({step.reason})"
    if step.handoff is not None:
        next_line += f" -> {step.handoff.value}"
    return "\n".join([*lines, next_line])
