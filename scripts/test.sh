#!/usr/bin/env bash
# Runs the test suite in an image aligned on HA 2026.8.2.
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -q -f Dockerfile.test -t home-stock-test . > /dev/null
exec docker run --rm --entrypoint python -v "$PWD:/src" -w /src home-stock-test -m pytest "$@"
