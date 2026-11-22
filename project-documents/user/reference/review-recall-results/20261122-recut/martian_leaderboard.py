import json, sys, statistics as st
d = json.load(open(sys.argv[1]))["models"]; names = list(d); prof = sys.argv[2]
tools = list(d[names[0]]["overall_metrics"])
rows = []
for t in tools:
    ms = [d[n]["overall_metrics"][t][prof] for n in names if t in d[n]["overall_metrics"]]
    rows.append((st.mean(m["recall"] for m in ms), st.mean(m["precision"] for m in ms), st.mean(m["f1"] for m in ms), st.mean((m["tp"] + m["fp"]) / m["num_prs"] for m in ms), t, ms))
print(f"profile {prof}; golden comments in profile: {rows[0][5][0]['tp'] + rows[0][5][0]['fn']}; mean over {len(names)} judges")
print(f"{'tool':20}{'recall':>8}{'precision':>10}{'F1':>6}{'comments/PR':>12}   recall by judge")
for r, p, f, c, t, ms in sorted(rows, reverse=True):
    print(f"{t:20}{r:>7.0f}%{p:>9.0f}%{f:>6.0f}{c:>12.1f}   " + " / ".join(f"{m['recall']:.0f}" for m in ms))
