"""Per-file diff cap, per-file record, and reviewer notice (#278)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from squadron.config.keys import CONFIG_KEYS
from squadron.review.coverage import CoverageLimits, impose_diff_coverage
from squadron.review.diff_files import split_diff_by_file
from squadron.review.models import (
    DiffFileInjection,
    DiffInjection,
    ReviewResult,
    Verdict,
)
from squadron.review.persistence import SliceInfo, format_review_markdown
from squadron.review.review_client import _inject_file_contents

_MAX_FILE_SIZE = CONFIG_KEYS["review.max_file_size_bytes"].default
_MAX_TOTAL_INJECTION = CONFIG_KEYS["review.max_total_injection_bytes"].default


def _file_diff(path: str, size: int) -> str:
    """A git-shaped diff section of exactly *size* characters."""
    header = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n+"
    return header + "x" * (size - len(header) - 1) + "\n"


def _inject(diff: str, tmp_path: Path):
    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = diff
        return _inject_file_contents("Review code", {"diff": "main", "cwd": str(tmp_path)})


def test_split_names_each_file_by_its_new_path() -> None:
    diff = _file_diff("src/a.py", 200) + _file_diff("src/dir/b.py", 300)
    assert [path for path, _ in split_diff_by_file(diff)] == ["src/a.py", "src/dir/b.py"]


def test_split_keeps_a_headerless_diff_whole() -> None:
    sections = split_diff_by_file("+just text\n")
    assert [text for _, text in sections] == ["+just text\n"]


def test_many_files_over_the_cap_in_total_are_not_truncated(tmp_path: Path) -> None:
    diff = "".join(_file_diff(f"src/f{i}.py", _MAX_FILE_SIZE - 5000) for i in range(3))
    assert len(diff) > _MAX_FILE_SIZE

    injected = _inject(diff, tmp_path)

    assert injected.diff is not None
    assert not injected.diff.truncated
    assert injected.diff.cut_files == ()
    assert "Part of this diff did not reach you" not in injected.prompt


def test_one_oversized_file_is_cut_and_the_others_arrive_whole(tmp_path: Path) -> None:
    small_before = _file_diff("src/before.py", 2000)
    huge = _file_diff("src/huge.py", _MAX_FILE_SIZE + 20_000)
    small_after = _file_diff("src/after.py", 2000)

    injected = _inject(small_before + huge + small_after, tmp_path)

    assert injected.diff is not None
    assert [(f.path, f.injected_chars) for f in injected.diff.cut_files] == [
        ("src/huge.py", _MAX_FILE_SIZE)
    ]
    assert small_before in injected.prompt
    assert small_after in injected.prompt
    assert "- src/huge.py: cut" in injected.prompt
    assert "do not report PASS on them" in injected.prompt


def test_total_limit_drop_omits_every_file_and_names_them(tmp_path: Path) -> None:
    count = _MAX_TOTAL_INJECTION // (_MAX_FILE_SIZE - 10_000) + 2
    diff = "".join(_file_diff(f"src/f{i}.py", _MAX_FILE_SIZE - 10_000) for i in range(count))

    injected = _inject(diff, tmp_path)

    assert injected.diff is not None
    assert injected.diff.injected_chars == 0
    assert len(injected.diff.cut_files) == count
    assert all(f.omitted for f in injected.diff.cut_files)
    assert "- src/f0.py: omitted" in injected.prompt


def _result_with_cut_file() -> ReviewResult:
    files = (
        DiffFileInjection(path="src/ok.py", total_chars=100, injected_chars=100),
        DiffFileInjection(path="src/lost.py", total_chars=900, injected_chars=0),
    )
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="",
        template_name="code",
        input_files={},
        diff_injection=DiffInjection.from_files(files),
        tool_calls_made=0,
        failed_tool_calls=0,
    )


def test_pass_with_an_omitted_unread_file_is_capped_naming_it() -> None:
    result = _result_with_cut_file()

    impose_diff_coverage(
        result,
        CoverageLimits(max_unseen_fraction=1.0, large_diff_chars=10**9, min_tool_calls_large_diff=0),
    )

    assert result.verdict is Verdict.CONCERNS
    assert "src/lost.py" in result.findings[0].description
    assert "src/ok.py" not in result.findings[0].description


def test_artifact_and_json_list_the_cut_files() -> None:
    result = _result_with_cut_file()

    slice_info = SliceInfo(
        index=1,
        name="s",
        slice_name="s",
        design_file=None,
        task_files=[],
        arch_file="arch.md",
        project="squadron",
    )
    markdown = format_review_markdown(result, "code", slice_info)

    assert "  - src/lost.py: omitted (0 of 900 characters)" in markdown
    assert 'diffCutFiles:\n  - "src/lost.py"' in markdown
    assert "src/ok.py" not in markdown
    assert result.to_dict()["diff_cut_files"] == [
        {"path": "src/lost.py", "total_chars": 900, "injected_chars": 0}
    ]
