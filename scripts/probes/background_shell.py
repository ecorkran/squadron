"""Live probe: can a pipeline session end up with a background shell? (slice 947 D10)

Opens a real pipeline session (the D12 state frames and the #199 deny hook are
both active), asks the agent to try one way of backgrounding a shell, then keeps
reading the stream and prints every frame as one JSON line. Answers come from
the log, not from reasoning:

  1. the ``task_type`` the CLI emits for a background shell
  2. whether a shell can be backgrounded despite the deny hook, and how
  3. whether a shell's end makes the CLI inject a continuation turn
  4. whether a running shell emits task_progress frames
  5. whether the CLI reports session state ``running`` while a shell is live

Not collected by pytest. Spends real tokens; run it by hand:

    .venv/bin/python scripts/probes/background_shell.py direct --model <model-id>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from claude_agent_sdk import ResultMessage

from squadron.pipeline.sdk_session import open_pipeline_session
from squadron.pipeline.sdk_turns import is_session_state_frame

# Each experiment is one way of trying to get a shell running past its turn.
EXPERIMENTS: dict[str, str] = {
    "direct": (
        "Call the Bash tool once with run_in_background set to true and the command "
        "`sleep 25 && echo SHELL_DONE`. Then end your turn at once. Do not wait for it."
    ),
    "timeout": (
        "Call the Bash tool once in the foreground with the timeout parameter set to 5000 "
        "(milliseconds) and the command `sleep 40 && echo LONG_DONE`. Then say exactly what "
        "the tool returned."
    ),
    "longcmd": (
        "Call the Bash tool once in the foreground with the timeout parameter set to 5000 "
        "(milliseconds) and the command "
        "`python3 -c \"import time; time.sleep(40); print('LONG_DONE')\"`. "
        "Then say exactly what the tool returned."
    ),
    "monitor": (
        "Call the Monitor tool once with an until-loop that runs for about 25 seconds, "
        "for example `i=0; until [ $i -ge 12 ]; do sleep 2; i=$((i+1)); done; echo MONITOR_DONE`. "
        "Then end your turn at once. Do not wait for it."
    ),
    "ampersand": (
        "Call the Bash tool once in the foreground with the command "
        "`(sleep 25 && echo AMP_DONE) &`. Then end your turn at once. Do not wait for it."
    ),
}

_FIELDS = ("subtype", "task_id", "task_type", "status", "description", "is_error", "num_turns")


def frame_record(msg: object, started: float) -> dict[str, Any]:
    """One log line: the frame's class, its identifying fields, and elapsed seconds."""
    record: dict[str, Any] = {"t": round(time.monotonic() - started, 1), "type": type(msg).__name__}
    for name in _FIELDS:
        value = getattr(msg, name, None)
        if value is not None:
            record[name] = value
    if is_session_state_frame(msg):
        record["state"] = msg.data["state"]  # type: ignore[attr-defined]
    origin = getattr(msg, "origin", None)
    if origin is not None:
        record["origin"] = origin
    if hasattr(msg, "content"):
        record["content"] = str(msg.content)[:300]  # type: ignore[attr-defined]
    return record


async def observe(experiment: str, model: str, observe_s: float) -> None:
    session = await open_pipeline_session()
    try:
        await session.set_model(model)
        started = time.monotonic()
        await session.client.query(EXPERIMENTS[experiment])
        while True:
            ended_on_result = False
            try:
                async with asyncio.timeout(observe_s):
                    async for msg in session.client.receive_response():
                        print(json.dumps(frame_record(msg, started), default=str), flush=True)
                        if isinstance(msg, ResultMessage):
                            ended_on_result = True
                            break
            except TimeoutError:
                print(json.dumps({"event": "silent", "for_s": observe_s}), flush=True)
                return
            if not ended_on_result:
                print(json.dumps({"event": "stream_ended"}), flush=True)
                return
    finally:
        await session.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--model", required=True, help="model id for the session")
    parser.add_argument(
        "--observe-s", type=float, required=True, help="silence, in seconds, that ends observation"
    )
    args = parser.parse_args()
    asyncio.run(observe(args.experiment, args.model, args.observe_s))


if __name__ == "__main__":
    main()
