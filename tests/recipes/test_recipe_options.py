"""Recipe reviewer options and the category filter (slice 437 D1, D3, D5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.recipes.recipe import (
    KEEP_CATEGORIES_COMBS_ISSUE,
    Recipe,
    RecipeError,
    ReviewerOptions,
    load_recipe,
    rules_sha256,
)
from squadron.recipes.recipe_record import recipe_hash

RULES_NAME = "check.rules.md"
RULES_TEXT = "Read every changed line.\n"
WITH_OPTIONS = f"""name: r
reviewers: [a, b]
reviewer_options:
  b:
    tools: false
    rules: {RULES_NAME}
keep_categories: [correctness, security-hygiene]
"""


def _write(directory: Path, text: str, stem: str = "r") -> Path:
    path = directory / f"{stem}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _with_rules(directory: Path, text: str = WITH_OPTIONS) -> Path:
    (directory / RULES_NAME).write_text(RULES_TEXT, encoding="utf-8")
    return _write(directory, text)


def test_recipe_without_the_new_keys_loads_with_defaults(tmp_path: Path) -> None:
    recipe = load_recipe(_write(tmp_path, "name: r\nreviewers: [a]\n"))
    assert dict(recipe.reviewer_options) == {}
    assert recipe.keep_categories is None


def test_recipe_with_options_and_filter_loads(tmp_path: Path) -> None:
    text = "name: r\nreviewers: [a, b]\nreviewer_options:\n  b: {tools: false}\n"
    text += "keep_categories: [correctness]\n"
    recipe = load_recipe(_write(tmp_path, text))
    assert recipe.reviewer_options["b"] == ReviewerOptions(tools=False)
    assert recipe.keep_categories == (ReviewCategory.CORRECTNESS,)
    assert "a" not in recipe.reviewer_options


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("reviewer_options: {zzz: {tools: false}}\n", "zzz"),
        ("reviewer_options: {a: {tool: false}}\n", "tool"),
        ("reviewer_options: {a: {rules_path: /x}}\n", "rules_path"),
        ("reviewer_options: {a: {rules_content: x}}\n", "rules_content"),
        ("keep_categories: [correctness, bogus-category]\n", "bogus-category"),
        ("keep_categories: []\n", "empty"),
        ("combs: [c]\nkeep_categories: [correctness]\n", KEEP_CATEGORIES_COMBS_ISSUE),
    ],
)
def test_refusals(tmp_path: Path, text: str, reason: str) -> None:
    path = _write(tmp_path, "name: r\nreviewers: [a, b]\n" + text)
    with pytest.raises(RecipeError, match=reason) as caught:
        load_recipe(path)
    assert str(path) in str(caught.value)


def test_unknown_category_message_lists_valid_values(tmp_path: Path) -> None:
    path = _write(tmp_path, "name: r\nreviewers: [a]\nkeep_categories: [nonsense]\n")
    with pytest.raises(RecipeError) as caught:
        load_recipe(path)
    assert "nonsense" in caught.value.reason and ReviewCategory.CORRECTNESS.value in caught.value.reason


def test_rules_file_is_read_beside_the_recipe(tmp_path: Path) -> None:
    recipe = load_recipe(_with_rules(tmp_path))
    options = recipe.reviewer_options["b"]
    assert options.rules == RULES_NAME
    assert options.rules_path is not None and options.rules_path.is_absolute()
    assert options.rules_path.parent == tmp_path.resolve()
    assert options.rules_content == RULES_TEXT


def _rules_recipe(directory: Path, rules: str) -> Path:
    return _write(directory, f"name: r\nreviewers: [a]\nreviewer_options:\n  a: {{rules: '{rules}'}}\n")


@pytest.mark.parametrize("name", ["sub/x.md", "/abs/x.md", "..", "../x.md"])
def test_rules_name_with_a_directory_part_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(RecipeError, match="no directory"):
        load_recipe(_rules_recipe(tmp_path, name))


def test_empty_rules_name_is_refused_even_as_the_only_rules_key(tmp_path: Path) -> None:
    with pytest.raises(RecipeError, match="file name beside the recipe"):
        load_recipe(_rules_recipe(tmp_path, ""))


def test_missing_rules_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RecipeError, match=r"x\.md.*not found"):
        load_recipe(_rules_recipe(tmp_path, "x.md"))


def test_unreadable_rules_file_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "x.md").write_text("rules", encoding="utf-8")
    real = Path.read_text

    def fail(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "x.md":
            raise PermissionError("denied")
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", fail)
    with pytest.raises(RecipeError, match=r"x\.md.*unreadable"):
        load_recipe(_rules_recipe(tmp_path, "x.md"))


def test_non_utf8_rules_file_is_refused(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_bytes(b"\xff\xfe")
    with pytest.raises(RecipeError, match=r"x\.md.*not UTF-8"):
        load_recipe(_rules_recipe(tmp_path, "x.md"))


def test_empty_rules_file_is_refused(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text("", encoding="utf-8")
    with pytest.raises(RecipeError, match=r"x\.md.*empty"):
        load_recipe(_rules_recipe(tmp_path, "x.md"))


def test_non_utf8_recipe_file_raises_recipe_error(tmp_path: Path) -> None:
    path = tmp_path / "r.yaml"
    path.write_bytes(b"name: r\nreviewers: [\xff\xfe]\n")
    with pytest.raises(RecipeError, match="unreadable"):
        load_recipe(path)


def test_rules_sha256_differs_by_content_and_is_none_without_rules() -> None:
    base = ReviewerOptions(rules="a.md")
    one = base.model_copy(update={"rules_content": "one"})
    two = base.model_copy(update={"rules_content": "two"})
    assert rules_sha256(one) != rules_sha256(two)
    assert rules_sha256(ReviewerOptions()) is None


def test_recipe_hash_changes_with_rules_content_tools_and_filter(tmp_path: Path) -> None:
    base = recipe_hash(load_recipe(_with_rules(tmp_path)))
    (tmp_path / RULES_NAME).write_text("different rules\n", encoding="utf-8")
    assert recipe_hash(load_recipe(_write(tmp_path, WITH_OPTIONS))) != base
    (tmp_path / RULES_NAME).write_text(RULES_TEXT, encoding="utf-8")
    tools_on = WITH_OPTIONS.replace("tools: false", "tools: true")
    assert recipe_hash(load_recipe(_write(tmp_path, tools_on))) != base
    no_filter = WITH_OPTIONS.replace("keep_categories: [correctness, security-hygiene]\n", "")
    assert recipe_hash(load_recipe(_write(tmp_path, no_filter))) != base


def test_recipe_hash_does_not_depend_on_the_directory(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    assert recipe_hash(load_recipe(_with_rules(first))) == recipe_hash(load_recipe(_with_rules(second)))


def test_recipe_constructed_with_reviewers_only_still_type_checks() -> None:
    assert Recipe(reviewers=("a",), name="r").keep_categories is None


def test_recipe_hash_ignores_the_order_of_keep_categories(tmp_path: Path) -> None:
    swapped = WITH_OPTIONS.replace("[correctness, security-hygiene]", "[security-hygiene, correctness]")
    first = recipe_hash(load_recipe(_with_rules(tmp_path)))
    assert recipe_hash(load_recipe(_write(tmp_path, swapped))) == first


def test_recipe_with_reviewer_options_is_hashable_and_equal_recipes_hash_alike(
    tmp_path: Path,
) -> None:
    first = load_recipe(_with_rules(tmp_path))
    second = load_recipe(_write(tmp_path, WITH_OPTIONS))
    assert first == second and hash(first) == hash(second)


def test_call_options_are_none_for_options_that_change_nothing() -> None:
    recipe = Recipe(
        name="r",
        reviewers=("a", "b", "c"),
        reviewer_options={"a": ReviewerOptions(), "b": ReviewerOptions(tools=False)},
    )
    assert recipe.call_options("a") is None
    assert recipe.call_options("b") == ReviewerOptions(tools=False)
    assert recipe.call_options("c") is None
