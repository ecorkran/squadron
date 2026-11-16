"""Export each case's tree at its reviewed commit into a one-commit scratch repo (no history,
no saved reviews) and write against.tsv: id, kind, doc, against ('-' for arch)."""
import pathlib, re, shutil, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
REPOS = {"squadron": "/Users/manta/source/repos/manta/squadron",
         "context-forge": "/Users/manta/source/repos/manta/context-forge",
         "migratory": "/Users/manta/source/repos/manta/migratory"}
# Frontmatter keys naming the document reviewed against, tried in order; the first that resolves
# to exactly one file in the exported tree wins. Task files use lld, lldReference, or (older) parent.
FM_KEYS = {"slice": ["parent"], "tasks": ["lld", "lldReference", "parent"]}
def run(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
rows, problems = [], []
for line in (HERE / "cases.tsv").read_text().splitlines():
    cid, repo, rev, kind, doc, _ = line.split("\t")
    dest = HERE / "wt" / cid
    shutil.rmtree(dest, ignore_errors=True); dest.mkdir(parents=True)
    tar = subprocess.Popen(["git", "-C", REPOS[repo], "archive", rev], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=tar.stdout, check=True)
    if tar.wait() != 0 or not (dest / doc).is_file():
        problems.append((cid, "doc missing at reviewed commit")); continue
    shutil.rmtree(dest / "project-documents/user/reviews", ignore_errors=True)
    against = "-"
    if kind in FM_KEYS:
        text = (dest / doc).read_text()
        found = None
        for key in FM_KEYS[kind]:
            m = re.search(rf"^{key}:\s*(\S+)", text, re.M)
            if not m: continue
            hits = [p for p in dest.rglob(pathlib.Path(m.group(1)).name) if ".git" not in p.parts]
            if len(hits) == 1: found = str(hits[0].relative_to(dest)); break
        if not found: problems.append((cid, f"no resolvable {FM_KEYS[kind]} in frontmatter")); continue
        against = found
    run("git", "init", "-q", "-b", "main", cwd=dest)
    run("git", "add", "-A", cwd=dest)
    run("git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid", "commit", "-q", "-m", "case tree", cwd=dest)
    rows.append((cid, kind, doc, against))
(HERE / "against.tsv").write_text("".join("\t".join(r) + "\n" for r in rows))
print(len(rows), "prepared;", "problems:", problems)
