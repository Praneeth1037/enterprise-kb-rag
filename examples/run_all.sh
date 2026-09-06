#!/usr/bin/env bash
# Runs the four documented test cases, then the full evaluation.
set -e
cd "$(dirname "$0")/.."
for t in 1 2 3 4; do
  case $t in
    3) role=contractor ;;
    *) role=employee ;;
  esac
  python3 run_baseline.py --input "examples/test${t}.txt" --role "$role" \
          --out "outputs/test${t}.json"
  echo
done
python3 run_eval.py
