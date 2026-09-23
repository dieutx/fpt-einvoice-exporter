#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 YEAR [additional export-year options...]" >&2
  exit 2
fi

year="$1"
shift
exec python3 fpt_einvoice_exporter.py export-year \
  --year "$year" \
  --workers 5 \
  --page-size 5000 \
  --range-days 10 \
  --max-retries 3 \
  --retry-delay 2 \
  --range-retries 3 \
  --no-adaptive-page-size \
  --resume \
  "$@"
