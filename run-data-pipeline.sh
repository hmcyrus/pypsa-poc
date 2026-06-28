#!/usr/bin/env bash
#
# Runs the data-building scripts in the required order.
# See src/data-script-execution-order.txt for the canonical ordering.
#
# Order:
#   1. buses + lines        (must run first)
#   2. generators, loads, transformers, links (any order)
#   3. bus supplement       (must run last)

set -euo pipefail

# Run from the repo root regardless of where this is invoked from.
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python}"

run() {
    echo ">>> $*"
    "$PYTHON" "$@"
}

# 1. buses + lines (must be first)
run src/line-bus-processor.py

# 2. generators / loads / transformers / links (any order)
run src/generator_builder.py
run src/load_builder.py
run src/transformer_builder.py
run src/link_builder.py

# 3. augment buses.csv (must be last)
run src/bus_supplement.py

echo ">>> Pipeline complete."
