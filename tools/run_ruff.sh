#!/bin/bash
set -euo pipefail

fix=0
while getopts "f" opt; do
    case "$opt" in
        f) fix=1 ;;
        *) echo "usage: $0 [-f]" >&2; exit 1 ;;
    esac
done

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root/rhythmic"

RUFF="$repo_root/.venv/bin/ruff"

check_args=(check .)
if [ "$fix" -eq 1 ]; then
    check_args+=(--fix)
fi

"$RUFF" "${check_args[@]}"
"$RUFF" format .