"""Print, per case and model, the findings that mention a known flaw's keywords. Read-only."""
import json, re, sys
from pathlib import Path
OUT = Path(__file__).parent / "out"
MODELS = ("sonnet-high", "haiku-xhigh", "opus-high", "sol")
FLAWS = {
 "420-design": {"A except-branch stamp": r"except|stamp_effort|not in scope|out of scope", "B five-field identity": r"five|tool_use|max_output_tokens"},
 "421-design": {"A env merge": r"os\.environ|merge|inherit|process_runner|ProcessRunner"},
 "422-design": {"A is_test_side tree": r"is_test_side", "B TraceVerdict": r"TraceVerdict|FairnessVerdict", "C reused": r"reused|reuse"},
 "423-design": {"A dispatch prompt": r"_resolve_prompt|CF_OP|cf_op|stdout|build_context|DispatchAction", "B IssueSource": r"IssueSource", "C io-dir": r"io-dir|io_dir"},
 "425-design": {"A measure_snapshot": r"measure_snapshot|exported|take_snapshot", "B 16 KB": r"16 ?KB|16 ?kB|record size|unbounded", "C row key": r"five|tool_use|max_output_tokens|alias, model", "D rules_hash": r"rules_hash|rules hash", "E inject_hidden": r"inject_hidden", "F lockfile": r"lockfile"},
 "426-design": {"A judge_pair": r"judge_pair|summary\.calls", "B plan_file_for": r"plan_file_for", "C sort order": r"sorted by name|suffix|numeric|-10", "D over-size": r"OverSize|over_size|over-size|oversize", "E no edits": r"No edits|no edits|424 or 425"},
 "426-tasks": {"A Task 23 live build": r"Task 23|hours|run time|runtime|600|long-running|wall", "B Task 26 live replay": r"Task 26|producer-only|whole slice"},
 "915-design": {"A four callers": r"caller|653|799|1102|1159", "B loop_step warning": r"_execute_loop_step|loop_step|loop step"},
 "302-design": {"A subcommand": r"slice-vs-arch|subcommand|--template"},
}
only = sys.argv[1:] 
for case, flaws in FLAWS.items():
    if only and case not in only: continue
    print(f"\n===== {case}")
    for model in MODELS:
        p = OUT / f"{case}-{model}-1.json"
        d = json.loads(p.read_text())
        fs = [f for f in d.get("findings", []) if str(f.get("severity", "")).upper() != "PASS"]
        sev = [str(f.get("severity", "")).upper() for f in fs]
        print(f"--- {model}: verdict {d.get('verdict')}, {sev.count('FAIL')}F/{sev.count('CONCERN')}C/{sev.count('NOTE')}N, tools {d.get('tool_calls_made')}, ${d.get('cost_usd') or 0:.2f}, {d.get('duration_seconds') or 0:.0f}s")
        for i, f in enumerate(fs):
            text = " ".join(str(f.get(k) or "") for k in ("title", "description", "location", "file_ref"))
            hits = [name for name, pat in flaws.items() if re.search(pat, text, re.I)]
            if hits:
                desc = re.sub(r"\s+", " ", str(f.get("description") or ""))[:420]
                print(f"  [{'/'.join(h.split()[0] for h in hits)}] {str(f.get('severity')).upper()} {f.get('title')}\n      {desc}")
