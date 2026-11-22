## Reporting rules for this review

- Read every changed hunk line by line before opening other files. For each line check: the variable used is the one intended; a function returns the value it just built; each called method, property, route, option or CSS property exists and is spelled as its definition spells it; conditions are not inverted; names in tests match the code they exercise.
- Report only behavior defects in code this change added or changed: wrong results, crashes, data loss, races, security holes, broken contracts, silent failures.
- Do not report missing tests, test quality, code structure, duplication, naming, documentation, or performance with no stated failure. A separate review covers those.
- One defect per finding. The title is one sentence naming what the code does and what goes wrong. Two defects are two findings.
- The description is evidence for that one defect: the lines involved and the path from input to wrong result. Do not raise a second defect in it.
