#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

if [ -x backend/.venv/bin/python ]; then
  python="$root/backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python=$(command -v python3)
else
  echo "Python 3 is required. Follow the backend setup in README.md." >&2
  exit 1
fi

if ! "$python" -m ruff --version >/dev/null 2>&1; then
  echo "Ruff is missing. Run: backend/.venv/bin/pip install -e 'backend[dev]'" >&2
  exit 1
fi

"$python" -m ruff check backend
npm --prefix frontend run lint

case "${1:-push}" in
  commit)
    npm --prefix frontend run typecheck
    ;;
  push)
    (cd backend && "$python" -m pytest -q)
    npm --prefix frontend run build:web
    "$root/scripts/test-branch-policy.sh"
    ;;
  *)
    echo "Usage: $0 commit|push" >&2
    exit 2
    ;;
esac
