#!/bin/bash

line() {
    echo "===================================================="
}

echo "BEGINNING....."
if [[ "$1" == "initialize" ]]; then
    echo "Sating all containers.."
    bash init.sh no-cache
fi

echo "Running all Files Concurrently..."

# Check whether Python is available
if command -v python >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "ERROR: No Python interpreter found."
    exit 1
fi

echo "Using Python: $PYTHON"
echo "Python version: $($PYTHON --version)"

line

$PYTHON send.py all &
line

$PYTHON send.py python &
line

$PYTHON send.py --action slow python &
line

$PYTHON send.py --action timeout python &
line

$PYTHON load.py &
line

bash t.sh &
line

bash t.sh cache &
line

$PYTHON chaos.py --workers 30 &
line

wait

echo "All experiments completed."
