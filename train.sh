#!/usr/bin/env bash
# Relaunch wrapper: keeps the manager alive until a terminal state exists.
# Usage: ./train.sh <skill-name> <tag> [agent-cli]   (default agent: claude)
set -euo pipefail

SKILL="${1:?usage: ./train.sh <skill-name> <tag> [agent-cli] [model]}"
TAG="${2:?usage: ./train.sh <skill-name> <tag> [agent-cli] [model]}"
AGENT="${3:-claude}"
MODEL="${4:-}"                     # explicit model for the manager
ROLLOUT_MODEL="${5:-$MODEL}"       # rollout model (defaults to manager's)
EFFORT="${6:-}"                    # reasoning effort (copilot/codex backends)
export SKILL_TRAINER_MODEL="$ROLLOUT_MODEL"  # run_task.py backends read these
export SKILL_TRAINER_EFFORT="$EFFORT"
cd "$(dirname "$0")"
mkdir -p "runs/$TAG"

PROMPT="You are the manager of skill-training run tag=$TAG skill=$SKILL.
Follow PROGRAM.md exactly, starting with its Resume ritual (§0).

$(cat PROGRAM.md)"

while [ ! -f "runs/$TAG/TERMINAL" ]; do
  echo "[train.sh] $(date '+%F %T') launching manager ($AGENT) for run $TAG"
  # caffeinate: an unattended run must survive the night, so block system sleep
  case "$AGENT" in
    claude)  caffeinate -dims claude -p "$PROMPT" --dangerously-skip-permissions ${MODEL:+--model "$MODEL"} || true ;;
    codex)   caffeinate -dims codex exec --sandbox workspace-write \
               ${MODEL:+--model "$MODEL"} \
               ${EFFORT:+-c "model_reasoning_effort=$EFFORT"} -- "$PROMPT" || true ;;
    copilot) caffeinate -dims copilot -p "$PROMPT" --allow-all-tools --no-color \
               ${MODEL:+--model "$MODEL"} ${EFFORT:+--effort "$EFFORT"} || true ;;
    # cursor model ids bake in reasoning effort (…-high), so no effort flag
    cursor|cursor-agent) caffeinate -dims cursor-agent -p --force --trust \
               ${MODEL:+--model "$MODEL"} -- "$PROMPT" || true ;;
    *)       "$AGENT" -p "$PROMPT" || true ;;
  esac
  [ -f "runs/$TAG/TERMINAL" ] || sleep 30
done

echo "[train.sh] terminal state: $(cat "runs/$TAG/TERMINAL")"
