import json, math, collections, statistics as st
R = json.load(open("reviews.json")); F = json.load(open("flaws.json"))
print(collections.Counter(f["needs"][:60] for f in F.values()).most_common(40))
