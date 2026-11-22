#!/usr/bin/env bash
# Run the Code Review Bench harness (extract, dedup, judge) for one tool entry with one judge model on OpenRouter.
# judge.sh <harness-offline-dir> <tool-name> <openrouter-model-id>
set -euo pipefail
harness=$1 tool=$2 model=$3
here=$(cd "$(dirname "$0")" && pwd)
# The OpenRouter key comes from squadron's .env; the base URL is set so the key never goes to the harness's default endpoint.
set -a; . "$here/../../../../../.env"; set +a
export MARTIAN_API_KEY="$OPENROUTER_API_KEY" MARTIAN_BASE_URL="https://openrouter.ai/api/v1" MARTIAN_MODEL="$model"
cd "$harness" || exit 1
for step in step2_extract_comments step2_5_dedup_candidates step3_judge_comments; do
  uv run --no-project --with openai --with tqdm python "code_review_benchmark/$step.py" --tool "$tool" 2>&1 | tail -6
done
