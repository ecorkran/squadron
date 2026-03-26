"""Provider-agnostic review execution.

Routes reviews through the SDK path (existing run_review()) or through
any configured provider profile using the OpenAI-compatible API.
"""

from __future__ import annotations

import glob as glob_mod
import logging
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI

from squadron.providers.auth import ApiKeyStrategy
from squadron.providers.profiles import ProviderProfile, get_profile
from squadron.review.models import ReviewResult
from squadron.review.parsers import parse_review_output
from squadron.review.runner import run_review
from squadron.review.templates import ReviewTemplate

_logger = logging.getLogger(__name__)


async def run_review_with_profile(
    template: ReviewTemplate,
    inputs: dict[str, str],
    *,
    profile: str,
    rules_content: str | None = None,
    model: str | None = None,
    verbosity: int = 0,
) -> ReviewResult:
    """Execute a review through the specified provider profile.

    If profile is "sdk", delegates to the existing run_review() which
    uses ClaudeSDKClient. Otherwise, creates an AsyncOpenAI client
    from the profile's credentials and base_url.
    """
    if profile == "sdk":
        return await run_review(
            template,
            inputs,
            rules_content=rules_content,
            model=model,
        )

    return await _run_non_sdk_review(
        template,
        inputs,
        profile=profile,
        rules_content=rules_content,
        model=model,
        verbosity=verbosity,
    )


async def _run_non_sdk_review(
    template: ReviewTemplate,
    inputs: dict[str, str],
    *,
    profile: str,
    rules_content: str | None = None,
    model: str | None = None,
    verbosity: int = 0,
) -> ReviewResult:
    """Execute a review via the OpenAI-compatible API path."""
    import sys

    provider_profile = get_profile(profile)
    api_key = await _resolve_api_key(provider_profile)

    # Build prompts and inject file contents for non-SDK path
    prompt = template.build_prompt(inputs)
    prompt = _inject_file_contents(prompt, inputs)
    system_prompt = template.system_prompt
    if rules_content:
        system_prompt += f"\n\n## Additional Review Rules\n\n{rules_content}"

    resolved_model = model if model is not None else template.model
    if resolved_model is None:
        raise ValueError(
            f"No model specified for non-SDK profile '{profile}'. "
            "Use --model or set model in the template."
        )

    # Debug output at -vvv (verbosity >= 3)
    if verbosity >= 3:
        print(f"[DEBUG] System Prompt:\n{system_prompt}", file=sys.stderr)
        print(f"[DEBUG] User Prompt:\n{prompt}", file=sys.stderr)
        if rules_content:
            print(f"[DEBUG] Injected Rules:\n{rules_content}", file=sys.stderr)

    # Create client and call API
    client_kwargs: dict[str, object] = {"api_key": api_key}
    if provider_profile.base_url:
        client_kwargs["base_url"] = provider_profile.base_url
    if provider_profile.default_headers:
        client_kwargs["default_headers"] = provider_profile.default_headers

    client = AsyncOpenAI(**client_kwargs)  # type: ignore[arg-type]

    _logger.info(
        "Review via %s (model=%s, base_url=%s)",
        profile,
        resolved_model,
        provider_profile.base_url or "default",
    )

    response = await client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    raw_output = response.choices[0].message.content or ""

    return parse_review_output(
        raw_output=raw_output,
        template_name=template.name,
        input_files=inputs,
        model=resolved_model,
    )


_MAX_FILE_SIZE = 100_000  # 100KB per file
_MAX_TOTAL_INJECTION = 500_000  # 500KB total
_SKIP_KEYS = {"cwd", "diff", "files"}


def _truncate(content: str, label: str) -> str:
    """Truncate content exceeding _MAX_FILE_SIZE with a message."""
    if len(content) <= _MAX_FILE_SIZE:
        return content
    _logger.warning("Truncated %s (%d bytes)", label, len(content))
    return (
        content[:_MAX_FILE_SIZE] + f"\n\n[truncated at {_MAX_FILE_SIZE // 1000}KB"
        " — file too large for API review]"
    )


def _inject_file_contents(prompt: str, inputs: dict[str, str]) -> str:
    """Inject file contents into the prompt for non-SDK reviews.

    Iterates input values, checks if each is a real file path via
    Path.is_file(), and appends file contents as fenced code blocks.
    Skips keys in _SKIP_KEYS (e.g. cwd, diff, files) and non-file values.
    Also handles special 'diff' and 'files' inputs for code reviews.
    """
    injections: list[str] = []
    total_size = 0

    def _add_injection(label: str, content: str) -> bool:
        """Add content to injections, respecting total limit. Returns False if full."""
        nonlocal total_size
        content = _truncate(content, label)
        file_size = len(content)
        if total_size + file_size > _MAX_TOTAL_INJECTION:
            _logger.warning(
                "Total injection limit reached (%dKB), skipping %s",
                _MAX_TOTAL_INJECTION // 1000,
                label,
            )
            return False
        total_size += file_size
        injections.append(f"### {label}\n\n```\n{content}\n```")
        return True

    # Inject file contents for regular input keys
    for key, value in inputs.items():
        if key in _SKIP_KEYS:
            continue

        path = Path(value)
        if not path.is_file():
            continue

        try:
            content = path.read_text()
        except OSError as exc:
            _logger.warning("Failed to read %s: %s", path, exc)
            continue

        if not _add_injection(f"{key}: {path.name}", content):
            break

    # Handle diff input — run git diff locally
    diff_ref = inputs.get("diff")
    if diff_ref is not None:
        diff_content = _run_git_diff(diff_ref, inputs.get("cwd", "."))
        if diff_content:
            _add_injection("Git Diff", diff_content)

    # Handle files glob input — resolve and inject matching files
    files_glob = inputs.get("files")
    if files_glob is not None:
        cwd = inputs.get("cwd", ".")
        _inject_glob_files(files_glob, cwd, _add_injection)

    if not injections:
        return prompt

    file_section = "\n\n## File Contents\n\n" + "\n\n".join(injections)
    return prompt + file_section


def _run_git_diff(ref: str, cwd: str) -> str | None:
    """Run git diff against a ref and return the output."""
    try:
        result = subprocess.run(
            ["git", "diff", ref],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode != 0:
            _logger.warning("git diff failed: %s", result.stderr.strip())
            return None
        return result.stdout if result.stdout.strip() else None
    except (FileNotFoundError, OSError) as exc:
        _logger.warning("Failed to run git diff: %s", exc)
        return None


def _inject_glob_files(
    pattern: str,
    cwd: str,
    add_fn: Callable[[str, str], bool],
) -> None:
    """Resolve a glob pattern and inject matching file contents."""
    cwd_path = Path(cwd)
    matches = sorted(glob_mod.glob(pattern, root_dir=cwd_path))

    for match in matches:
        full_path = cwd_path / match
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text()
        except OSError as exc:
            _logger.warning("Failed to read %s: %s", full_path, exc)
            continue

        if not add_fn(f"file: {match}", content):
            break


async def _resolve_api_key(profile: ProviderProfile) -> str:
    """Resolve API key for a provider profile.

    Uses the profile's api_key_env to look up the environment variable.
    For localhost profiles, returns a placeholder.
    """
    strategy = ApiKeyStrategy(
        env_var=profile.api_key_env,
        base_url=profile.base_url,
    )
    if not strategy.is_valid():
        env_hint = profile.api_key_env or "OPENAI_API_KEY"
        raise ValueError(
            f"No API key found for profile '{profile.name}'. "
            f"Set {env_hint} environment variable."
        )
    creds = await strategy.get_credentials()
    return creds["api_key"]


_PROMPT_LOG_DIR = Path.home() / ".config" / "squadron" / "logs"


def _write_prompt_log(
    system_prompt: str,
    user_prompt: str,
    rules_content: str | None,
    model: str,
    profile: str,
    template_name: str,
    *,
    log_dir: Path | None = None,
) -> Path:
    """Write the full prompt payload to a timestamped markdown file.

    Returns the path of the written file.
    """
    target_dir = log_dir or _PROMPT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC)
    ts_file = now.strftime("%Y%m%d-%H%M%S")
    ts_iso = now.isoformat()

    filename = f"review-prompt-{ts_file}.md"
    path = target_dir / filename

    rules_section = rules_content if rules_content else "None"
    content = (
        f"---\n"
        f"template: {template_name}\n"
        f"model: {model}\n"
        f"profile: {profile}\n"
        f"timestamp: {ts_iso}\n"
        f"---\n\n"
        f"# Review Prompt Log\n\n"
        f"## System Prompt\n\n{system_prompt}\n\n"
        f"## User Prompt\n\n{user_prompt}\n\n"
        f"## Injected Rules\n\n{rules_section}\n"
    )
    path.write_text(content)
    return path
