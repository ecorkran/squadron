import json,glob,re,collections,sys
BUGS={
 "921-B1":("921",r"minute_sessions|minute\.py",r"PARTIAL.*(no bar|empty|did not trade|not trade|refetch|re-fetch|retry|RETRY_EXHAUSTED|indefinite|converge)|(no bar|empty session).*PARTIAL"),
 "921-B2":("921",r"minute\.py|minute_coverage",r"trailing_floor|7-day|seven-day|older than (7|seven)|_build_truncated_index"),
 "921-B3":("921",r"cutover_common",r"fire_unit_until|blocks|blocking|never (act|stop)|cannot stop"),
 "225-B1":("225",r"status_reads|tick_coverage",r"raw|shape|product|instrument"),
 "175-B1":("175",r"sdk_turns|agent\.py|usage\.py|usage_capture",r"total_cost_usd|running total|cumulative|delta|session total|session-total"),
 "188-B1":("188",r"windows|serve_timeseries|kalshi_timeseries",r"inclusive|half-open|end_period_ts|boundary|last candle|window"),
 "227-B1":("227",r"b2_lifecycle",r"2>&1|stderr|rclone|jq"),
 "a122-B1":("a122",r"launch|params|dispatch",r"-p slice|positional|slice=|argv|build_argv"),
 "a122-B2":("a122",r"tenant",r"COMPLETE|spin|idle|busy|tight|work"),
 "u103-B1":("u103",r"use-chart-provider",r"range|setVisibleRange|seriesCount|dependenc|deps"),
 "932-B1":("932",r"sdk_session|sdk_turns",r"ledger|idle|background|own_result|early|returns"),
 "197-B1":("197",r"sources|item_resume",r"merged|cf status|open_in_plan|_open_dependencies|_select_item|git|complete"),
 "307-B1":("307",r"cutover_304_checks|purchase_verdicts|first_purchase",r"phases|KeyError|nested|payload"),
 "307-B2":("307",r"cutover_304_checks|purchase_verdicts|first_purchase",r"estimate_only|allowed"),
 "a122-C1":("a122",r"observe",r"issued_at|malformed"),
 "a122-C2":("a122",r"faults|tenant|escalat",r"non-human|blocked on|escalat"),
 "u103-C1":("u103",r"use-chart-provider",r"container|late|re-?mount|ref"),
}
def runs():
    for f in sorted(glob.glob("out/*.json")):
        base=f[4:-5]; case=base.split("-",1)[0]; rest=base.split("-",1)[1]; alias,n=rest.rsplit("-",1)
        yield f,case,alias,n
cands=[]
for f,case,alias,n in runs():
    d=json.load(open(f))
    for x in d["findings"]:
        if x.get("severity") not in ("CONCERN","FAIL"): continue
        loc=str(x.get("location","")); txt=" ".join(str(v) for v in x.values())
        for b,(c,lp,tp) in BUGS.items():
            if c==case and re.search(lp,loc) and re.search(tp,txt,re.I):
                cands.append((b,case,alias,n,loc[:60],str(x.get("title") or x.get("summary"))[:90],f))
json.dump(cands,open("cands.json","w"))
print(len(cands),"candidate (run,finding) pairs;", len({(c[0],c[2],c[3]) for c in cands}),"distinct run-bug pairs")
