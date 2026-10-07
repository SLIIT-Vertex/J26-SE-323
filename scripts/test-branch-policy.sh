#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
policy="$root/scripts/branch-policy.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cd "$work"
git init -q -b develop
git config user.name "Hook Test"
git config user.email "hook-test@example.invalid"
printf 'base\n' > file.txt
git add file.txt
git commit -qm base
base=$(git rev-parse HEAD)
git update-ref refs/remotes/origin/develop "$base"
git switch -qc feature/test
printf 'feature\n' >> file.txt
git commit -qam feature
feature=$(git rev-parse HEAD)
zeros=0000000000000000000000000000000000000000

if printf 'refs/heads/feature/test %s refs/heads/main %s\n' "$feature" "$base" | "$policy" >/dev/null 2>&1; then
  echo "branch policy test failed: direct main push was allowed" >&2
  exit 1
fi

printf 'refs/heads/feature/test %s refs/heads/feature/test %s\n' "$feature" "$zeros" | "$policy" >/dev/null

git update-ref refs/remotes/origin/develop "$feature"
if printf 'refs/heads/feature/test %s refs/heads/feature/test %s\n' "$feature" "$zeros" | "$policy" >/dev/null 2>&1; then
  echo "branch policy test failed: an integrated branch was allowed" >&2
  exit 1
fi

git update-ref refs/remotes/origin/develop "$base"
git switch -q develop
printf 'upstream\n' > upstream.txt
git add upstream.txt
git commit -qm upstream
git update-ref refs/remotes/origin/develop HEAD
git switch -q feature/test
git merge -q --no-ff develop -m merge
merged=$(git rev-parse HEAD)
if printf 'refs/heads/feature/test %s refs/heads/feature/test %s\n' "$merged" "$zeros" | "$policy" >/dev/null 2>&1; then
  echo "branch policy test failed: a merge commit was allowed" >&2
  exit 1
fi

git switch -qc feature/old "$base"
printf 'old\n' >> file.txt
git add file.txt
GIT_AUTHOR_DATE='2000-01-01T00:00:00Z' GIT_COMMITTER_DATE='2000-01-01T00:00:00Z' git commit -qm old
old=$(git rev-parse HEAD)
if printf 'refs/heads/feature/old %s refs/heads/feature/old %s\n' "$old" "$zeros" | "$policy" >/dev/null 2>&1; then
  echo "branch policy test failed: a stale branch push was allowed" >&2
  exit 1
fi
if "$policy" --current >/dev/null 2>&1; then
  echo "branch policy test failed: a stale branch commit was allowed" >&2
  exit 1
fi
