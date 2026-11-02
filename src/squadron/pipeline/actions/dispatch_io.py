"""File and reply handling for dispatch steps (slice 949).

Holds the logic behind a dispatch step's ``prompt_files``, ``reply_from``, ``reply_format``,
``reply_file`` and ``delivered_prompt_file`` keys, so ``actions/dispatch.py`` gains only call
sites: prompt assembly (D2), reply hand-off between steps (D3), JSON extraction (D4) and the
output files (D5). The key names and ``ReplyFormat`` live in ``pipeline/dispatch_keys.py``.
"""

from __future__ import annotations
