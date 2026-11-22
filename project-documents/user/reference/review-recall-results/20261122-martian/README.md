---
docType: reference
project: squadron
dateCreated: 20261122
dateUpdated: 20261122
status: draft
---

# Squadron code review on Martian's Code Review Bench (2026-11-22)

Squadron's code reviewers run on the 50 public PRs of [Code Review Bench](https://github.com/withmartian/code-review-benchmark) and scored by that harness against its 173 golden comments, beside the 21 tools it already holds.

## Files

- `prs.py`, `prs.json`: base and head commit of each PR, from the GitHub API.
- `setup.py`, `cases.json`: one two-commit sandbox per PR (merge base, then PR head), no history. Sandboxes are scratch and are rebuilt by `setup.py WORK_DIR`; `cases.json` holds their paths.
- `run.sh`, `batch.py`: one `sq review code --diff <base>` per case and reviewer. Outputs in `out/`, logs in `logs/`.
- `comb.py`: the code comb of `../20261113-comb/comb.yaml`, one call per review. Decisions in `comb/<comb>/`; `comb/luna-r+opus-high/` is opus-high over what luna-r kept.
- `convert.py`: adds one squadron entry to the harness's `benchmark_data.json`. `judge.sh` runs the harness's extract, dedup and judge steps for that entry with a judge model on OpenRouter.
- `harness-results/`: the harness's result files for the squadron entries, copied from the harness checkout.

## Notes

- Reviewers: haiku-xhigh (50 reviews), sol-r (50), sol on the Codex plan (43; stopped to keep the plan's 5-hour window).
- The harness has a model split each tool's comments into separate issues before judging. Squadron findings with full text were split about three ways, so each entry is scored with titles only (`-t`) and, for some, with full text.
- `sq` reads provider keys from the `.env` of its working directory; `run.sh` loads squadron's.
