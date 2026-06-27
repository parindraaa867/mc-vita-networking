#!/usr/bin/env bash
set -e
export VITASDK=/usr/local/vitasdk
export PATH="$VITASDK/bin:/usr/bin:/bin"
cd "$(dirname "$0")"
rm -rf build
cmake -S . -B build
cmake --build build
echo "=== build output ==="
ls -la build/*.suprx
