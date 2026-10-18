#!/usr/bin/env bash
# Start the local API and the Grade 5 app. Draft missions are on via frontend/.env.development.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
api="http://127.0.0.1:8000/api/v1/health"
backend_pid=""

cleanup() {
	if [[ -n "$backend_pid" ]]; then
		kill "$backend_pid" 2>/dev/null || true
		wait "$backend_pid" 2>/dev/null || true
	fi
}
trap cleanup EXIT INT TERM

if ! curl -sf -o /dev/null "$api"; then
	python="$root/backend/.venv/bin/python"
	if [[ ! -x "$python" ]]; then
		echo "backend/.venv is missing. Create it in backend/ before npm run dev." >&2
		exit 1
	fi
	(cd "$root/backend" && "$python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
	backend_pid="$!"
	for _ in $(seq 1 50); do
		if curl -sf -o /dev/null "$api"; then
			break
		fi
		sleep 0.2
	done
fi

cd "$root/frontend"
npm run dev
