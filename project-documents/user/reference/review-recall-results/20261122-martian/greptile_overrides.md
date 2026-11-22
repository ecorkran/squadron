---
docType: reference
project: squadron
dateCreated: 20261122
dateUpdated: 20261122
status: draft
---

# Greptile benchmark: hand corrections to `e5.py` for haiku-xhigh

`e5.py` pairs each of Greptile's 50 bugs with the closest golden comment on the same PR and reads the judge's verdict for that comment. Seven Greptile bugs have no golden comment that states them, and three pairings were wrong. Read by one reader against haiku-xhigh's finding titles, 2026-11-22.

| Greptile row | Bug | e5.py | Corrected | Why |
|---|---|---|---|---|
| sentry 9 | Invalid queue.ShutDown exception handling | caught | missed | paired with a docstring comment; no haiku finding names the exception |
| discourse 6 | String mutation with `<<` | caught | missed | paired with the missing `?` suffix comment; no haiku finding names the mutation |
| grafana 6 | Incorrect metrics recording methods | missed | caught | the matching golden comment is the `recordLegacyDuration` one, which haiku hit |
| grafana 4 | Double interpolation risk | missed | caught | no golden comment states it; haiku raised "Template variables and ad-hoc filters are applied twice on the split paths" |
| cal.com 7 | Timing attack via direct string comparison | caught | caught | paired with the wrong comment, but haiku raised "Webhook compares the secret with `!==`" |

No golden comment and no haiku finding: cal.com 2 (backup codes not invalidated), cal.com 4 (SQL injection), grafana 3 (undefined endpoint constants), grafana 8 (deadlock in annotation deletion).

Corrected total for haiku-xhigh: 30 of 50. Greptile's page gives Greptile 41, Bugbot 29, Copilot 26, CodeRabbit 22, Graphite 3, scored by its own rule (a line-level comment naming the faulty code), not by this judge.
