"""Code grid 2: sets vs repeats, vote filter, line dedupe against the graders' issue clusters."""
import json, glob, collections, re, itertools, os, statistics as st
P = "/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261112-grid2/precision/"
loc = {}; issues = []
def L(s):
    m = re.search(r"([^/\s:]+\.\w+):(\d+)(?:\s*-\s*(\d+))?", str(s or "")); return (m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))) if m else None
for f in glob.glob(P + "*-findings.json"):
    case = os.path.basename(f).split("-")[0]
    for x in json.load(open(f)): loc[(case, x["ref"])] = L(x.get("location"))
for f in glob.glob(P + "*-graded.json"):
    d = json.load(open(f))
    for i in d["issues"]:
        i["case"] = d["case"]; i["m"] = [tuple(r.split("/")[:2]) for r in i["members"]]; issues.append(i)
print("issues", len(issues), collections.Counter(i["grade"] for i in issues), "known-bug issues", sum(1 for i in issues if i.get("known")))
print("known field sample:", [i["known"] for i in issues if i.get("known")][:6])
REAL = [i for i in issues if i["grade"] == "REAL"]
def stats(name, members):
    ms = set(members); got = [i for i in issues if ms & set(i["m"])]
    nfind = sum(1 for i in issues for r in i["m"] if r in ms)
    real = [i for i in got if i["grade"] == "REAL"]; known = {(i["case"], str(i["known"])) for i in got if i.get("known")}
    multi = [i for i in got if len(ms & set(i["m"])) >= 2]; mreal = [i for i in multi if i["grade"] == "REAL"]; mknown = {(i["case"], str(i["known"])) for i in multi if i.get("known")}
    print(f"{name:34} findings/case {nfind / 10:5.1f}  distinct issues/case {len(got) / 10:5.1f}  REAL issues {len(real):3} ({len(real) / len(got):.0%})  known {len(known):2} | 2+ votes: {len(multi) / 10:4.1f}/case, REAL {len(mreal):3} ({len(mreal) / max(1, len(multi)):.0%}), known {len(mknown)}")
H = lambda *r: [("haiku-xhigh", str(x)) for x in r]; S = lambda *r: [("sol", str(x)) for x in r]; SH = lambda *r: [("sonnet-high", str(x)) for x in r]; SO = lambda *r: [("sonnet", str(x)) for x in r]
print("total REAL issues", len(REAL), " total known-bug keys", len({(i['case'], str(i['known'])) for i in issues if i.get('known')}))
for name, ms in (("haiku-xhigh x1", H(1)), ("haiku-xhigh x2", H(1, 2)), ("haiku-xhigh x3", H(1, 2, 3)), ("sol x1", S(1)), ("sol x3", S(1, 2, 3)), ("sonnet-high x3", SH(1, 2, 3)),
                 ("haiku + sol", H(1) + S(1)), ("haiku x2 + sol", H(1, 2) + S(1)), ("haiku + sol + sonnet-high", H(1) + S(1) + SH(1)), ("haiku x3 + sol x3", H(1, 2, 3) + S(1, 2, 3)), ("all 4 configs x3", H(1, 2, 3) + S(1, 2, 3) + SH(1, 2, 3) + SO(1, 2, 3))):
    stats(name, ms)
print("\nREAL share by number of distinct configs that raised the issue (all runs):")
for k in (1, 2, 3, 4):
    xs = [i for i in issues if len({m[0] for m in i["m"]}) == k]
    print(f"  {k} configs: {len(xs):3} issues, REAL {sum(1 for i in xs if i['grade'] == 'REAL') / max(1, len(xs)):.0%}")
print("REAL share by number of runs of the same config that raised it:")
for cfg in ("haiku-xhigh", "sol", "sonnet-high"):
    line = f"  {cfg:12}"
    for k in (1, 2, 3):
        xs = [i for i in issues if len({m for m in i["m"] if m[0] == cfg}) == k]
        line += f"  {k} run(s): {len(xs):3} issues, {sum(1 for i in xs if i['grade'] == 'REAL') / max(1, len(xs)):.0%} REAL;"
    print(line)
# line dedupe against grader clusters
for gap in (0, 3, 10):
    same = same_ok = diff = diff_bad = 0
    for case in {i["case"] for i in issues}:
        fs = [(n, ref) for n, i in enumerate(issues) if i["case"] == case for ref in i["members"]]
        for (n1, r1), (n2, r2) in itertools.combinations(fs, 2):
            if r1.split("/")[:2] == r2.split("/")[:2]: continue
            a, b = loc.get((case, r1)), loc.get((case, r2))
            near = bool(a and b and a[0] == b[0] and a[1] <= b[2] + gap and b[1] <= a[2] + gap)
            if n1 == n2: same += 1; same_ok += near
            else: diff += 1; diff_bad += near
    print(f"line dedupe gap {gap}: same-issue pairs merged {same_ok}/{same} ({same_ok / same:.0%}); different-issue pairs wrongly merged {diff_bad}/{diff} ({diff_bad / diff:.1%})")
