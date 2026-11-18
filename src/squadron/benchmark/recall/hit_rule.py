"""The hit rule: a mechanical file-level location gate, then a stored label (slice 430 D3).

The gate is deliberately loose. A finding that cites no file path is a candidate for every
bug; one whose cited paths match none of a bug's files is a decided miss for that bug.
Only a stored label turns a candidate into a hit. No model takes part.
"""

from __future__ import annotations

import re
from enum import StrEnum

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.metrology.recall_case_models import KnownBug
from squadron.metrology.recall_label_models import HitVerdict
from squadron.metrology.recall_run_models import RecallFinding

#: File extensions a cited token must end in to count as a path. A fixed list, so dotted
#: code references (``self.client``, ``parts[0].metadata``) are not read as files.
SOURCE_EXTENSIONS = frozenset(
    {
        "py", "pyi", "ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "yaml", "yml", "toml",
        "md", "sh", "rs", "go", "java", "kt", "sql", "css", "scss", "html", "txt", "cfg",
        "ini", "lock", "rb", "c", "h", "cpp", "hpp", "cs", "swift", "vue", "svelte",
    }
)  # fmt: skip
_PATH_TOKEN = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w-][\w.-]*\.([A-Za-z][A-Za-z0-9]*))(?![\w/])")
_LEADING_CURRENT_DIR = "./"


class GateResult(StrEnum):
    CANDIDATE = "candidate"
    DECIDED_MISS = "decided_miss"


class HitOutcome(StrEnum):
    """A finding's verdict for one bug after the gate and the labels."""

    HIT = "HIT"
    ADJACENT = "ADJACENT"
    MISS = "MISS"
    UNDECIDED = "UNDECIDED"


_FROM_LABEL = {
    HitVerdict.HIT: HitOutcome.HIT,
    HitVerdict.ADJACENT: HitOutcome.ADJACENT,
    HitVerdict.MISS: HitOutcome.MISS,
}


def cited_paths(finding: RecallFinding) -> list[str]:
    """Path-like tokens with a source extension from the location and the description.

    Lenient: ``path:12-30``, ``path#symbol``, ``path (text)``, backticked paths and bare
    basenames all yield the path.
    """
    found: list[str] = []
    for text in (finding.location or "", finding.description):
        for match in _PATH_TOKEN.finditer(text):
            if match.group(2).lower() not in SOURCE_EXTENSIONS:
                continue
            path = match.group(1).removeprefix(_LEADING_CURRENT_DIR)
            if path not in found:
                found.append(path)
    return found


def path_matches(cited: str, bug_file: str) -> bool:
    """One path ends with the other at a ``/`` boundary (``minute.py`` ~ ``src/x/minute.py``)."""
    return cited == bug_file or bug_file.endswith(f"/{cited}") or cited.endswith(f"/{bug_file}")


def gate(finding: RecallFinding, bug: KnownBug) -> GateResult:
    paths = cited_paths(finding)
    if not paths:
        return GateResult.CANDIDATE
    files = [location.file for location in bug.locations]
    if any(path_matches(path, file) for path in paths for file in files):
        return GateResult.CANDIDATE
    return GateResult.DECIDED_MISS


def resolve(finding: RecallFinding, bug: KnownBug, labels: ResolvedLabels) -> HitOutcome:
    """The gate first; a candidate takes its label, and with none it is undecided."""
    if gate(finding, bug) is GateResult.DECIDED_MISS:
        return HitOutcome.MISS
    label = labels.hit(finding.content_key, bug.id)
    return HitOutcome.UNDECIDED if label is None else _FROM_LABEL[label]
