#!/bin/bash


for each in {1..20}; do
  echo "Running $each"
  python /home/codest/Public/sre_lab/send.py --action slow security
done
