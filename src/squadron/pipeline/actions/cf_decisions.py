"""The pending-PM-decision check before an implement step (#240).

Squadron does not parse decision status: ``cf validate design`` does, and squadron
only reads what it reports. Missing design sections are cf's other finding and are not
this check's business, so only ``pending`` is read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError


def pending_decisions(cf_client: ContextForgeClient, slice_id: str, cwd: str) -> list[str]:
    """The slice design's pending-pm decisions as ``heading (line N)``, empty when none.

    Raises:
        ContextForgeError: the slice is not in the plan, has no design file, or cf's
            report is not one that says what is pending (an old cf, or an error).
    """
    design = Path(cwd) / _design_file(cf_client, slice_id)
    report = cf_client.run_report(["validate", "design", "--json", str(design)])
    if report.get("error"):
        raise ContextForgeError(f"cf validate design: {report.get('message', report)}")
    files = cast("list[dict[str, Any]]", report.get("files", []))
    if len(files) != 1 or not isinstance(files[0].get("pending"), list):
        raise ContextForgeError(
            f"cf validate design reported no pending-decision list for {design}; "
            "sq requires a cf with the decision gate (0.19.14 or later)"
        )
    pending = cast("list[dict[str, Any]]", files[0]["pending"])
    return [f"{entry['heading']} (line {entry['line']})" for entry in pending]


def _design_file(cf_client: ContextForgeClient, slice_id: str) -> str:
    entry = next((s for s in cf_client.list_slices() if str(s.index) == slice_id), None)
    if entry is None:
        raise ContextForgeError(f"slice {slice_id} is not in the current slice plan")
    if entry.design_file is None:
        raise ContextForgeError(f"slice {slice_id} has no design file")
    return entry.design_file
