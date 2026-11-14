#!/usr/bin/env bash
# Build the easd-llama image from a LOCAL llama-cpp-turboquant checkout (no GitHub clone).
#
#   docker/llama/build.sh [path-to-llama-cpp-turboquant]
#
# Source folder: the argument, else $LLAMA_SRC, else ~/llama-cpp-turboquant.
# The checkout is snapshotted with `git archive` (tracked files, including uncommitted edits to them;
# untracked files, build*/ and models/ are left out) into this folder, which is the Docker build
# context, and removed again afterwards. Works with the classic builder too: no buildx needed.
# Run it alone: on an 8 GB PC a build next to other heavy work can run out of memory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-${LLAMA_SRC:-$HOME/llama-cpp-turboquant}}"

git -C "$SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "not a git checkout: $SRC" >&2; exit 1; }

# `git stash create` makes a commit object of the working tree without touching it (empty if clean).
REF="$(git -C "$SRC" stash create)"
COMMIT="$(git -C "$SRC" rev-parse --short HEAD)"
if [ -n "$REF" ]; then COMMIT="$COMMIT-dirty"; else REF=HEAD; fi

trap 'rm -f "$HERE/llama-src.tar.gz" "$HERE/BUILD_COMMIT"' EXIT
git -C "$SRC" archive --format=tar.gz -o "$HERE/llama-src.tar.gz" "$REF" -- . ':(exclude)models' ':(exclude)media'
echo "$COMMIT" > "$HERE/BUILD_COMMIT"
echo "Building easd-llama from $SRC ($COMMIT, $(du -h "$HERE/llama-src.tar.gz" | cut -f1) source snapshot)"

docker compose -f "$HERE/compose.yml" build
