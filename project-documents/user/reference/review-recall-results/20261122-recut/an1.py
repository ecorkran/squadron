import json, statistics as st, collections
R = json.load(open("reviews.json"))
by = collections.defaultdict(list)
for r in R: by[r["alias"]].append(r)
def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else float("nan")
print(f"{'config':16}{'n':>4}{'recall':>7}{'tools':>6}{'turns':>6}{'prompt_k':>9}{'compl_k':>8}{'reas_k':>7}{'dur_s':>6}{'finds':>6}{'$':>6}")
tab = []
for a, rs in by.items():
    rec = sum(r["nhit"] for r in rs) / sum(r["nflaws"] for r in rs)
    tab.append((rec, a, len(rs), med([r["tool_calls"] for r in rs]), med([r["turns"] for r in rs]), med([r["prompt"] for r in rs]) / 1e3,
                med([r["completion"] for r in rs]) / 1e3, med([r["reasoning"] for r in rs]) / 1e3, med([r["dur"] for r in rs]),
                st.mean(r["nfind"] for r in rs), med([r["cost"] for r in rs])))
for t in sorted(tab, reverse=True):
    print(f"{t[1]:16}{t[2]:>4}{t[0]:>7.0%}{t[3]:>6.0f}{t[4]:>6.0f}{t[5]:>9.0f}{t[6]:>8.1f}{t[7]:>7.1f}{t[8]:>6.0f}{t[9]:>6.1f}{t[10]:>6.2f}")
