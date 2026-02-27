#!/usr/bin/env bash
# govy-sync.sh — Auto-sync WIP branch between machines
# Usage: bash scripts/govy-sync.sh [pull|push|full]
# Default: full (pull + commit-if-changed + push)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

BRANCH="wip/local"
MODE="${1:-full}"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
HOSTNAME="$(hostname)"

log() { echo "[govy-sync] $*"; }

# Ensure we're on the right branch
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    log "ERROR: Not on $BRANCH (currently on $CURRENT_BRANCH). Aborting."
    exit 1
fi

do_pull() {
    log "Pulling from origin/$BRANCH..."
    git fetch origin "$BRANCH" 2>/dev/null || {
        log "Remote branch not found yet — skip pull."
        return 0
    }
    # Rebase only if clean
    if git diff --quiet && git diff --cached --quiet; then
        git rebase "origin/$BRANCH" 2>/dev/null || {
            log "Rebase conflict — aborting rebase, will merge instead."
            git rebase --abort
            git merge "origin/$BRANCH" --no-edit || {
                log "ERROR: Merge conflict. Resolve manually."
                exit 1
            }
        }
    else
        log "Working tree dirty — stash + pull + unstash."
        git stash push -m "govy-sync-auto-stash"
        git rebase "origin/$BRANCH" 2>/dev/null || {
            git rebase --abort
            git merge "origin/$BRANCH" --no-edit || {
                git stash pop
                log "ERROR: Merge conflict. Resolve manually."
                exit 1
            }
        }
        git stash pop || log "WARN: stash pop had conflicts — check files."
    fi
    log "Pull done."
}

do_push() {
    # Check if there are changes to commit
    if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        log "No changes to commit."
    else
        git add -A
        git commit -m "$(cat <<EOF
wip: auto-sync from $HOSTNAME at $TIMESTAMP

Co-Authored-By: govy-sync <noreply@govy.dev>
EOF
)"
        log "Committed WIP."
    fi

    # Push
    git push -u origin "$BRANCH" 2>/dev/null || {
        log "Push failed — trying with force-with-lease..."
        git push --force-with-lease origin "$BRANCH"
    }
    log "Push done."
}

case "$MODE" in
    pull)  do_pull ;;
    push)  do_push ;;
    full)  do_pull; do_push ;;
    *)     log "Usage: govy-sync.sh [pull|push|full]"; exit 1 ;;
esac

log "Sync complete ($MODE) at $TIMESTAMP."
