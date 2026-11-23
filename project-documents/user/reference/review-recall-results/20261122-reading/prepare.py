"""Rebuild the 43 mined design-review cases as one-commit trees: prepare.py WORK_DIR.

Same trees as ../20261116-mined/prepare.py (each case's repository at its reviewed commit, no
history, no saved reviews), written under WORK_DIR/wt/<case> so they stay outside this repository.
The case list and the document each is reviewed against come from ../20261116-mined/ unchanged.
"""
import pathlib, shutil, subprocess, sys
MINED = pathlib.Path(__file__).resolve().parent.parent / "20261116-mined"
REPOS = {"squadron": "/Users/manta/source/repos/manta/squadron",
         "context-forge": "/Users/manta/source/repos/manta/context-forge",
         "migratory": "/Users/manta/source/repos/manta/migratory"}
work = pathlib.Path(sys.argv[1]) / "wt"
def run(*cmd: str, cwd: pathlib.Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
against = {row.split("\t")[0]: row.split("\t") for row in (MINED / "against.tsv").read_text().splitlines()}
built, problems = 0, []
for line in (MINED / "cases.tsv").read_text().splitlines():
    cid, repo, rev, _kind, doc, _ = line.split("\t")
    dest = work / cid
    shutil.rmtree(dest, ignore_errors=True); dest.mkdir(parents=True)
    tar = subprocess.Popen(["git", "-C", REPOS[repo], "archive", rev], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=tar.stdout, check=True)
    if tar.wait() != 0 or not (dest / doc).is_file():
        problems.append((cid, "doc missing at reviewed commit")); continue
    reviewed_against = against[cid][3]
    if reviewed_against != "-" and not (dest / reviewed_against).is_file():
        problems.append((cid, f"against document missing: {reviewed_against}")); continue
    shutil.rmtree(dest / "project-documents/user/reviews", ignore_errors=True)
    run("git", "init", "-q", "-b", "main", cwd=dest)
    run("git", "add", "-A", cwd=dest)
    run("git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid", "commit", "-q", "-m", "case tree", cwd=dest)
    built += 1
print(built, "prepared;", "problems:", problems)
