#!/bin/sh
set -eu

zero_oid() {
  case "$1" in
    *[!0]*) return 1 ;;
    *) return 0 ;;
  esac
}

develop_ref=${MINDBRIDGE_DEVELOP_REF:-refs/remotes/origin/develop}
has_develop=false
if git rev-parse --verify --quiet "$develop_ref" >/dev/null; then
  has_develop=true
else
  echo "warning: $develop_ref is unavailable; run 'git fetch origin develop' for complete checks" >&2
fi

if [ "${1:-}" = "--current" ]; then
  branch=$(git symbolic-ref --quiet --short HEAD || true)
  [ -n "$branch" ] || exit 0
  [ "$branch" != "develop" ] || exit 0
  [ "$has_develop" = true ] || exit 0

  head=$(git rev-parse HEAD)
  old_commit=$(git log --format='%h' --until='3 days ago' --max-count=1 "$develop_ref..$head")
  if [ -n "$old_commit" ]; then
    echo "Commit rejected: branch $branch has unmerged work older than three days. Rebase and finish or replace the branch." >&2
    exit 1
  fi

  cherry=$(git cherry "$develop_ref" "$head")
  if printf '%s\n' "$cherry" | grep -q '^-'; then
    echo "Commit rejected: branch $branch contains changes already applied to $develop_ref. Rebase it first." >&2
    exit 1
  fi

  if git rev-parse --verify --quiet '@{upstream}' >/dev/null \
    && git merge-base --is-ancestor "$head" "$develop_ref"; then
    echo "Commit rejected: tracked branch $branch is already contained in $develop_ref. Start a new branch." >&2
    exit 1
  fi
  exit 0
fi

while read -r local_ref local_oid remote_ref remote_oid; do
  [ -n "${local_ref:-}" ] || continue

  case "$remote_ref" in
    refs/heads/main|refs/heads/master)
      echo "Push rejected: push a feature branch and open a pull request instead of updating ${remote_ref#refs/heads/}." >&2
      exit 1
      ;;
  esac

  zero_oid "$local_oid" && continue

  if zero_oid "$remote_oid"; then
    if [ "$has_develop" = true ]; then
      base=$(git merge-base "$local_oid" "$develop_ref")
      range="$base..$local_oid"
    else
      base=$(git rev-list --max-parents=0 "$local_oid")
      range="$base..$local_oid"
    fi
  else
    range="$remote_oid..$local_oid"
  fi

  if [ -n "$(git rev-list --merges "$range")" ]; then
    echo "Push rejected: outgoing merge commits found. Rebase onto develop instead of merging." >&2
    exit 1
  fi

  case "$remote_ref" in
    refs/heads/develop) continue ;;
  esac

  if [ "$has_develop" = true ]; then
    if git merge-base --is-ancestor "$local_oid" "$develop_ref"; then
      echo "Push rejected: this branch is already contained in $develop_ref." >&2
      exit 1
    fi

    cherry=$(git cherry "$develop_ref" "$local_oid")
    if printf '%s\n' "$cherry" | grep -q '^-'; then
      echo "Push rejected: this branch contains changes already applied to $develop_ref. Rebase it first." >&2
      exit 1
    fi

    old_commit=$(git log --format='%h' --until='3 days ago' --max-count=1 "$develop_ref..$local_oid")
    if [ -n "$old_commit" ]; then
      echo "Push rejected: this branch has unmerged work older than three days. Rebase and finish or replace the branch." >&2
      exit 1
    fi
  fi
done
