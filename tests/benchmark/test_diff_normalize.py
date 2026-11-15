"""Diff normalization for the slice-case judge (slice 426 D11): synthetic and real git diffs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from squadron.benchmark.diff_normalize import (
    DROPPED_PREFIXES,
    DROPPED_ROOT_FILES,
    EMPTY_DIFF_TEXT,
    is_dropped,
    normalize,
)
from squadron.integrations.context_forge import DOCS_ROOT
from tests.conftest import run_test_git

_CODE = "src/app.py"
_DROPPED_SAMPLES = [
    "DEVLOG.md",
    "CHANGELOG.md",
    "uv.lock",
    f"{DOCS_ROOT}/user/tasks/426-tasks.x.md",
    f"{DOCS_ROOT}/user/reviews/426-review.code.x.md",
    f"{DOCS_ROOT}/user/reviews/archive/426-review.code.x.md",
    f"{DOCS_ROOT}/user/slices/426-slice.x.md",
]


def _modified(path: str, body: str = "-old\n+new\n") -> str:
    return (
        f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n"
        f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n{body}"
    )


def _renamed(old: str, new: str) -> str:
    return f"diff --git a/{old} b/{new}\nsimilarity index 100%\nrename from {old}\nrename to {new}\n"


def _binary_patch(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..1111111\n"
        "GIT binary patch\nliteral 4\nLcmZQzU|?ooSy2cE\n\nliteral 0\nHcmV?d00001\n\n"
    )


def _text(*sections: str) -> bytes:
    return "".join(sections).encode()


@pytest.mark.parametrize("path", _DROPPED_SAMPLES)
def test_is_dropped_is_true_for_each_dropped_path(path: str) -> None:
    assert is_dropped(path)


def test_dropped_constants_are_what_the_samples_exercise() -> None:
    assert {"DEVLOG.md", "CHANGELOG.md", "uv.lock"} == DROPPED_ROOT_FILES
    assert len(DROPPED_PREFIXES) == 3


@pytest.mark.parametrize("path", [_CODE, "tests/test_app.py", "docs/DEVLOG.md", "pyproject.toml"])
def test_is_dropped_is_false_for_code_and_nested_lookalikes(path: str) -> None:
    assert not is_dropped(path)


@pytest.mark.parametrize("path", _DROPPED_SAMPLES)
def test_each_dropped_path_is_removed_and_the_code_section_kept(path: str) -> None:
    code = _modified(_CODE)

    result = normalize(_text(_modified(path), code))

    assert result.text == code
    assert result.dropped_paths == (path,)


def test_a_nested_docs_user_tasks_file_is_kept_outside_the_repo_docs_root() -> None:
    nested = _modified("docs/user/tasks/1-tasks.x.md")

    result = normalize(_text(nested))

    assert result.text == nested
    assert result.dropped_paths == ()


def test_a_rename_with_one_side_kept_is_kept() -> None:
    renamed = _renamed(f"{DOCS_ROOT}/user/tasks/old.md", "src/moved.md")

    result = normalize(_text(renamed))

    assert result.text == renamed


def test_a_rename_with_both_sides_dropped_is_dropped() -> None:
    old, new = f"{DOCS_ROOT}/user/tasks/a.md", f"{DOCS_ROOT}/user/reviews/b.md"

    result = normalize(_text(_renamed(old, new), _modified(_CODE)))

    assert result.text == _modified(_CODE)
    assert result.dropped_paths == (old, new)


@pytest.mark.parametrize(
    "binary_section",
    [
        _binary_patch("assets/logo.png"),
        "diff --git a/assets/logo.png b/assets/logo.png\nindex 1111111..2222222 100644\n"
        "Binary files a/assets/logo.png and b/assets/logo.png differ\n",
    ],
    ids=["git-binary-patch", "binary-files-differ"],
)
def test_a_binary_section_becomes_one_marker_line(binary_section: str) -> None:
    code = _modified(_CODE)

    result = normalize(_text(binary_section, code))

    assert result.text == f"Binary file assets/logo.png changed\n{code}"
    assert result.binary_paths == ("assets/logo.png",)


def test_a_dropped_binary_section_is_dropped_not_marked() -> None:
    result = normalize(_text(_binary_patch(f"{DOCS_ROOT}/user/reviews/chart.png"), _modified(_CODE)))

    assert result.binary_paths == ()
    assert result.dropped_paths == (f"{DOCS_ROOT}/user/reviews/chart.png",)


@pytest.mark.parametrize("diff", [b"", _text(_modified("DEVLOG.md"), _modified("uv.lock"))])
def test_a_diff_that_normalizes_to_nothing_has_the_placeholder_text(diff: bytes) -> None:
    assert normalize(diff).text == EMPTY_DIFF_TEXT


def test_a_quoted_path_with_spaces_and_escapes_is_read() -> None:
    quoted = '"src/caf\\303\\251 notes.py"'
    section = (
        f'diff --git "a/src/caf\\303\\251 notes.py" "b/src/caf\\303\\251 notes.py"\n'
        f"index 1111111..2222222 100644\n--- a/{quoted[1:-1]}\t\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    )
    dropped_name = '"docs space/DEVLOG.md"'
    binary = f'diff --git "a/{dropped_name[1:-1]}" "b/{dropped_name[1:-1]}"\nBinary files differ\n'

    result = normalize(_text(section, binary))

    assert result.text == section + "Binary file docs space/DEVLOG.md changed\n"


def test_an_unquoted_path_with_spaces_is_read_from_the_header() -> None:
    result = normalize(
        _text(
            "diff --git a/DEVLOG.md b/DEVLOG.md\nindex 1..2 100644\n"
            "Binary files a/DEVLOG.md and b/DEVLOG.md differ\n",
            "diff --git a/my dir/file.png b/my dir/file.png\nindex 1..2 100644\n"
            "Binary files a/my dir/file.png and b/my dir/file.png differ\n",
        )
    )

    assert result.dropped_paths == ("DEVLOG.md",)
    assert result.binary_paths == ("my dir/file.png",)


def test_crlf_content_survives_unchanged() -> None:
    section = (
        f"diff --git a/{_CODE} b/{_CODE}\r\nindex 1..2 100644\r\n--- a/{_CODE}\r\n"
        f"+++ b/{_CODE}\r\n@@ -1 +1 @@\r\n-old\r\n+new\r\n"
    )

    assert normalize(section.encode()).text == section


def test_a_real_git_diff_with_rename_binary_and_bookkeeping_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_test_git(repo, "init", "-q", "-b", "main")
    files = {
        "src/old_name.py": "\n".join(f"line {n}" for n in range(30)) + "\n",
        "DEVLOG.md": "log\n",
        "uv.lock": "lock\n",
        "src/crlf.py": "a\r\nb\r\n",
        "src/café notes.py": "x\n",
        "my dir/spaced.py": "x\n",
    }
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_bytes(text.encode())
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "start")
    start = run_test_git(repo, "rev-parse", "HEAD").strip()
    run_test_git(repo, "mv", "src/old_name.py", "src/new_name.py")
    (repo / "DEVLOG.md").write_text("log\nmore\n")
    (repo / "uv.lock").write_text("lock\nmore\n")
    (repo / "src/crlf.py").write_bytes(b"a\r\nc\r\n")
    (repo / "src/café notes.py").write_text("y\n")
    (repo / "my dir/spaced.py").write_text("y\n")
    (repo / "assets.png").write_bytes(bytes(range(256)))
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "work")
    # Bytes, not text: text mode would turn the CRLF content into LF.
    raw = subprocess.run(
        ["git", "diff", "--binary", start, "HEAD"], cwd=repo, capture_output=True, check=True
    ).stdout

    result = normalize(raw)

    assert set(result.dropped_paths) == {"DEVLOG.md", "uv.lock"}
    assert result.binary_paths == ("assets.png",)
    assert "Binary file assets.png changed" in result.text
    # git writes a path with non-ASCII characters quoted and octal-escaped, one with a space bare.
    kept_headers = (
        "diff --git a/src/old_name.py b/src/new_name.py",
        "diff --git a/src/crlf.py b/src/crlf.py",
        'diff --git "a/src/caf\\303\\251 notes.py" "b/src/caf\\303\\251 notes.py"',
        "diff --git a/my dir/spaced.py b/my dir/spaced.py",
    )
    for header in kept_headers:
        assert header in result.text
    assert "-b\r\n+c\r\n" in result.text
    assert "rename from src/old_name.py" in result.text
    assert "DEVLOG" not in result.text
    assert "GIT binary patch" not in result.text


_REAL_DIFF = Path(__file__).parent / "fixtures" / "slice_diff.diff"
_HEADER = re.compile(r"^diff --git a/(?P<old>\S+) b/(?P<new>\S+)$", re.MULTILINE)


def test_a_real_slice_diff_loses_only_bookkeeping_and_keeps_hunks_byte_identical() -> None:
    """Slice 402's ``fork..tip`` (git diff --binary): DEVLOG, CHANGELOG, a task file, review
    files and a slice document, around code and test files."""
    raw = _REAL_DIFF.read_bytes()
    text = raw.decode()
    headers = list(_HEADER.finditer(text))
    ends = [match.start() for match in headers[1:]] + [len(text)]
    sections = {
        match.group("new"): text[match.start() : end] for match, end in zip(headers, ends, strict=True)
    }
    dropped = {path for path in sections if is_dropped(path)}
    kept = set(sections) - dropped
    assert {"DEVLOG.md", "CHANGELOG.md"} <= dropped, "the fixture must hold bookkeeping changes"
    assert any(path.startswith("src/") for path in kept)
    assert any(path.startswith("tests/") for path in kept)

    result = normalize(raw)

    assert set(result.dropped_paths) == dropped
    assert {match.group("new") for match in _HEADER.finditer(result.text)} == kept
    assert all(not is_dropped(match.group("new")) for match in _HEADER.finditer(result.text))
    for path in kept:
        assert sections[path] in result.text  # the hunk bodies are byte-identical
