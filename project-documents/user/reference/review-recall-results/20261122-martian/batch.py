"""Run one reviewer alias over every built benchmark case: batch.py ALIAS JOBS [STOP_REGEX].

A case whose output exists is skipped. With STOP_REGEX, the first review that leaves no output and whose log
matches it (an out-of-credits message) stops the batch; cases not yet started are listed for the fallback alias.
"""
import concurrent.futures, json, pathlib, re, subprocess, sys, threading
HERE = pathlib.Path(__file__).resolve().parent
import os
alias, jobs = sys.argv[1], int(sys.argv[2])
label, run = os.environ.get("REVIEW_LABEL", alias), os.environ.get("RUN", "1")  # see run_review.sh for the variant settings
stop_re = re.compile(sys.argv[3], re.I) if len(sys.argv) > 3 else None
stop = threading.Event()
names = [case["name"] for case in json.load(open(HERE / "cases.json")).values()]
def one(name: str) -> str:
    if stop.is_set():
        return f"skipped {name}"
    line = subprocess.run([str(HERE / "run_review.sh"), name, alias, run], capture_output=True, text=True).stdout.strip()
    log = HERE / "logs" / f"{name}-{label}-{run}.log"
    if stop_re and line.startswith("NO OUTPUT") and log.exists() and stop_re.search(log.read_text(errors="replace")):
        stop.set()
        return f"STOP {line}"
    if line:
        return line
    made = (HERE / "out" / f"{name}-{label}-{run}.json").exists()
    return f"had output {name}" if made else f"NO OUTPUT {name} {label} {run}: the runner printed nothing"
with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
    for line in pool.map(one, names):
        print(line, flush=True)
done = [n for n in names if (HERE / "out" / f"{n}-{label}-{run}.json").exists()]
print(f"{label} run {run}: {len(done)} of {len(names)} have output; stopped early: {stop.is_set()}")
