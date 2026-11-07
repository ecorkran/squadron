"""Which credential files each provider profile needs carried into a sandbox home.

One table keyed by ``ProfileName`` (slice 421 D8). Paths are relative to the
home directory. API-key profiles carry no file: their credential is a variable.
"""

from __future__ import annotations

from squadron.providers.base import ProfileName

AUTH_CARRYOVER_FILES: dict[ProfileName, tuple[str, ...]] = {
    ProfileName.OPENAI: (),
    ProfileName.OPENROUTER: (),
    ProfileName.LOCAL: (),
    ProfileName.GEMINI: (),
    ProfileName.SDK: (".claude/.credentials.json",),
    ProfileName.OPENAI_OAUTH: (".codex/auth.json",),
}
