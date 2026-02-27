#!/usr/bin/env bash
# govy-sync.sh — Sync working tree to wip/local branch for multi-computer access
# Usage: bash scripts/govy-sync.sh [full|push|pull]
#   full  = pull + commit + push (default)
#   push  = commit + push only
#   pull  = pull only

set -euo pipefail

MODE="${1:-full}"
BRANCH="wip/local"
CURRENT_BRANCH=$(git branch --show-current)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
HOSTNAME=$(hostname)

log() { echo "[govy-sync] $*"; }

# Save current branch to restore later
if [ "$CURRENT_BRANCH" = "$BRANCH" ]; then
    ON_WIP=true
else
    ON_WIP=false
fi

cleanup() {
    if [ "$ON_WIP" = false ] && [ "$(git branch --show-current)" = "$BRANCH" ]; then
        git checkout "$CURRENT_BRANCH" --quiet 2>/dev/null || true
    fi
}
trap cleanup EXIT

# --- PULL ---
if [ "$MODE" = "full" ] || [ "$MODE" = "pull" ]; then
    log "Pulling from origin/$BRANCH..."
    git fetch origin "$BRANCH" --quiet 2>/dev/null || true
    if [ "$ON_WIP" = true ]; then
        git pull origin "$BRANCH" --quiet --no-edit 2>/dev/null || true
    else
        # Merge remote wip/local into local wip/local without switching
        git fetch origin "$BRANCH":"$BRANCH" --quiet 2>/dev/null || true
    fi
    log "Pull done."
fi

# --- COMMIT + PUSH ---
if [ "$MODE" = "full" ] || [ "$MODE" = "push" ]; then
    # Switch to wip/local
    if [ "$ON_WIP" = false ]; then
        # Stash any uncommitted/untracked changes on current branch
        STASH_NEEDED=false
        if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
            STASH_NEEDED=true
            git stash push --include-untracked -m "govy-sync-temp" --quiet
        fi

        # Merge current branch state into wip/local (prefer current branch on conflicts)
        git checkout "$BRANCH" --quiet
        git merge "$CURRENT_BRANCH" -X theirs --no-edit --quiet 2>/dev/null || {
            # If merge still fails, accept all theirs
            git checkout --theirs . 2>/dev/null || true
            git add -A
        }
    fi

    # Add all changes and commit
    git add -A
    if git diff --cached --quiet; then
        log "No changes to commit."
    else
        git commit -m "wip: auto-sync from $HOSTNAME at $TIMESTAMP" --quiet
        log "Committed changes."
    fi

    # Push
    git push origin "$BRANCH" --quiet 2>/dev/null
    log "Push done."

    # Switch back
    if [ "$ON_WIP" = false ]; then
        git checkout "$CURRENT_BRANCH" --quiet
        if [ "$STASH_NEEDED" = true ]; then
            git stash pop --quiet 2>/dev/null || true
        fi
    fi
fi

log "Sync complete ($MODE) at $TIMESTAMP"
