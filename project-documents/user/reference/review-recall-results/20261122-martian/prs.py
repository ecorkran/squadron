"""Look up base and head commits for the 50 Code Review Bench PRs (public GitHub API, no token). Writes prs.json."""
import json, pathlib, re, sys, time, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
data = json.load(open(sys.argv[1]))  # the harness's offline/results/benchmark_data.json
out = {}
for url, v in data.items():
    owner, repo, num = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", url).groups()
    req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}", headers={"Accept": "application/vnd.github+json", "User-Agent": "bench-client"})
    with urllib.request.urlopen(req, timeout=30) as r: pr = json.load(r)
    out[url] = {"owner": owner, "repo": repo, "number": int(num), "source_repo": v["source_repo"], "title": pr["title"], "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"],
                "base_ref": pr["base"]["ref"], "changed_files": pr["changed_files"], "additions": pr["additions"], "deletions": pr["deletions"], "goldens": len(v["golden_comments"])}
    time.sleep(0.3)
json.dump(out, open(HERE / "prs.json", "w"), indent=1)
print(len(out), "PRs; files changed median", sorted(p["changed_files"] for p in out.values())[len(out) // 2], "max", max(p["changed_files"] for p in out.values()), "; additions median", sorted(p["additions"] for p in out.values())[len(out) // 2])
