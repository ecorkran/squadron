"""Provider-agnostic review execution.

Routes reviews through the SDK path (existing run_review()) or through
any configured provider profile using the OpenAI-compatible API.
"""

from __future__ import annotations

import logging
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
    )


async def _run_non_sdk_review(
    template: ReviewTemplate,
    inputs: dict[str, str],
    *,
    profile: str,
    rules_content: str | None = None,
    model: str | None = None,
) -> ReviewResult:
    """Execute a review via the OpenAI-compatible API path."""
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
_SKIP_KEYS = {"cwd"}


def _inject_file_contents(prompt: str, inputs: dict[str, str]) -> str:
    """Inject file contents into the prompt for non-SDK reviews.

    Iterates input values, checks if each is a real file path via
    Path.is_file(), and appends file contents as fenced code blocks.
    Skips keys in _SKIP_KEYS (e.g. cwd) and non-file values.
    """
    injections: list[str] = []
    total_size = 0

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

        file_size = len(content)
        if file_size > _MAX_FILE_SIZE:
            content = content[:_MAX_FILE_SIZE]
            content += (
                f"\n\n[truncated at {_MAX_FILE_SIZE // 1000}KB"
                " — file too large for API review]"
            )
            _logger.warning("Truncated %s (%d bytes)", path, file_size)
            file_size = len(content)

        if total_size + file_size > _MAX_TOTAL_INJECTION:
            _logger.warning(
                "Total injection limit reached (%dKB), skipping %s",
                _MAX_TOTAL_INJECTION // 1000,
                path,
            )
            break

        total_size += file_size
        injections.append(f"### {key}: {path.name}\n\n```\n{content}\n```")

    if not injections:
        return prompt

    file_section = "\n\n## File Contents\n\n" + "\n\n".join(injections)
    return prompt + file_section


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
