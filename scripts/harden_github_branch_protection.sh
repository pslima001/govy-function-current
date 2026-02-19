#!/usr/bin/env bash
# Hardens branch protection on main. Run MANUALLY after team agreement.
# Requires: gh CLI authenticated with admin permissions.
#
# Changes:
#   - Require PR before merging (no direct pushes)
#   - Enforce admins (admins cannot bypass)
#   - Required status checks: lint-and-test (strict)
#   - Required conversation resolution
#   - Block force pushes and branch deletion
#   - Required reviews: 0 (solo dev can self-merge after CI)

set -euo pipefail

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
BRANCH="main"

echo "=== Branch Protection Hardening ==="
echo "Repo:   $REPO"
echo "Branch: $BRANCH"
echo ""

# Show current state
echo "--- BEFORE ---"
gh api "repos/${REPO}/branches/${BRANCH}/protection" \
  --jq '{
    enforce_admins: .enforce_admins.enabled,
    required_reviews: .required_pull_request_reviews.required_approving_review_count,
    required_checks: .required_status_checks.contexts,
    strict: .required_status_checks.strict,
    force_pushes: .allow_force_pushes.enabled,
    deletions: .allow_deletions.enabled,
    conversation_resolution: .required_conversation_resolution.enabled
  }' 2>/dev/null || echo "(no protection currently set)"

echo ""
echo "Applying hardened protection..."

gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint-and-test"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo ""
echo "--- AFTER ---"
gh api "repos/${REPO}/branches/${BRANCH}/protection" \
  --jq '{
    enforce_admins: .enforce_admins.enabled,
    required_reviews: .required_pull_request_reviews.required_approving_review_count,
    required_checks: .required_status_checks.contexts,
    strict: .required_status_checks.strict,
    force_pushes: .allow_force_pushes.enabled,
    deletions: .allow_deletions.enabled,
    conversation_resolution: .required_conversation_resolution.enabled
  }'

echo ""
echo "Branch protection hardened on ${BRANCH}."
echo "WARNING: Direct pushes to main are now BLOCKED for ALL users including admins."
echo "All changes must go through PR + CI (lint-and-test)."
