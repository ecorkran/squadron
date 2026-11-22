"""Build one history-free two-commit sandbox per Code Review Bench PR: commit 1 is the merge base, commit 2 the PR head.

Usage: setup.py WORK_DIR   (reads prs.json beside this file; writes cases.json there; safe to rerun)
Merge bases come from commit-only (tree:0) clones; file trees come from codeload tarballs, so no history reaches a sandbox.
"""
import json, pathlib, shutil, subprocess, sys, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
WORK = pathlib.Path(sys.argv[1]).resolve()
def run(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
def graph_repo(owner, repo):
    path = WORK / "graph" / f"{owner}__{repo}.git"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".cloning")  # renamed only when whole, so a killed clone is redone
        shutil.rmtree(partial, ignore_errors=True)
        run("git", "clone", "-q", "--bare", "--filter=tree:0", f"https://github.com/{owner}/{repo}.git", str(partial))
        partial.rename(path)
    return path
def tarball(owner, repo, sha):
    path = WORK / "tar" / f"{owner}__{repo}__{sha}.tar.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(f"https://codeload.github.com/{owner}/{repo}/tar.gz/{sha}", tmp)
        tmp.rename(path)
    return path
def commit_tree(box, tar_path, message):
    for child in box.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    run("tar", "-xzf", str(tar_path), "--strip-components=1", "-C", str(box))
    run("git", "add", "-A", "-f", cwd=box)
    run("git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid", "commit", "-q", "--allow-empty", "-m", message, cwd=box)
    return run("git", "rev-parse", "HEAD", cwd=box).stdout.strip()
prs = json.load(open(HERE / "prs.json")); cases_path = HERE / "cases.json"
cases = json.load(open(cases_path)) if cases_path.exists() else {}
for url, pr in prs.items():
    name = f"{pr['source_repo']}-{pr['owner'].split('-')[0][:2]}{pr['number']}"
    if url in cases and pathlib.Path(cases[url]["sandbox"]).is_dir():
        continue
    try:
        graph = graph_repo(pr["owner"], pr["repo"])
        run("git", "fetch", "-q", "origin", f"+refs/pull/{pr['number']}/head:refs/bench/pr{pr['number']}", cwd=graph)
        if run("git", "cat-file", "-e", f"{pr['base_sha']}^{{commit}}", cwd=graph, check=False).returncode:
            run("git", "fetch", "-q", "origin", pr["base_sha"], cwd=graph)
        merge_base = run("git", "merge-base", pr["base_sha"], pr["head_sha"], cwd=graph).stdout.strip()
        box = WORK / "sandbox" / name
        shutil.rmtree(box, ignore_errors=True); box.mkdir(parents=True)
        run("git", "init", "-q", "-b", "main", cwd=box)
        base_local = commit_tree(box, tarball(pr["owner"], pr["repo"], merge_base), "base")
        commit_tree(box, tarball(pr["owner"], pr["repo"], pr["head_sha"]), "change under review")
        stat = run("git", "diff", "--shortstat", base_local, "HEAD", cwd=box).stdout.strip()
        cases[url] = {"name": name, "sandbox": str(box), "base_local": base_local, "merge_base": merge_base, "head_sha": pr["head_sha"], "diffstat": stat}
        print("ok", name, stat, flush=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        print("FAIL", name, url, getattr(exc, "stderr", "") or exc, flush=True)
    json.dump(cases, open(cases_path, "w"), indent=1)
print("built", len(cases), "of", len(prs))
