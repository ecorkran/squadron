## This review is a line-by-line read of the diff only

Read every changed hunk line by line and report only slips visible in the changed lines themselves:

- a variable, field or argument that is not the one the surrounding code intends;
- a function that builds or modifies a value and returns a different one;
- a called method, property, route, HTTP verb, option, schema construct or CSS property that does not exist or is misspelled;
- an inverted or always-true or always-false condition;
- a test whose names, verbs or fixtures do not match the code it exercises;
- a command or syntax that only works on one platform.

One defect per finding; the title is one sentence naming the slip. Do not report design, structure, missing tests, documentation or style.
