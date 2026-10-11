# task_gate fixtures

Verbatim excerpts of real task files, used by `tests/review/test_task_gate.py`. The suite never
reads the source repos. Each file's first line names its source file and line range.

| Fixture | Source | Expected hit lines (excerpt / source) |
|---------|--------|---------------------------------------|
| `p1.md` | trading-data `184-tasks.polish-gaps-endpoint.md` | 4, 13 / 211, 220 |
| `p2.md` | trading-data `185-tasks.staleness-surface-for-api-clients.md` | 7, 12 / 410, 415 |
| `p3.md` | trading-data `908-tasks.pypi-distribution-and-production-cutover.md` | 4, 5 / 146, 147 |
| `p4.md` | trading-data `909-tasks.mt-update-self-update-command.md` | 7, 8 / 237, 238 |
| `p5.md` | trading-ui `124-tasks.chart-data-binding.md` | 7 / 496 |
| `p6.md` | trading-ui `125-tasks.late-container-mount-fix.md` | 7 / 325 |
| `squadron_negatives.md` | squadron task files (per-line source comments) | none |

The expected lines are also the constants in the test file; keep the two in step.
