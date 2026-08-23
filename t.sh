#!/bin/bash


ROUTE=${1:-all-notes}

if [[ "$ROUTE" != "all-notes" ]]; then
  for each in {1..20}; do
    echo "Running $each"
    python /home/codest/Public/sre_lab/send.py --action slow security
  done
else
  for each in {1..20}; do
    echo "Running $each"
    echo "Running /${ROUTE}"
    curl -v http://localhost:5000/all_notes
  done
fi
