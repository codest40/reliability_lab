#!/bin/bash
set -u

line() {
    echo "===================================================="
}

echo "BEGINNING....."
INIT=false
EXPERIMENT=false

if [[ $# -eq 0 ]]; then
    EXPERIMENT=true
fi

for arg in "$@"; do
    case "$arg" in
        init|initialize)
            INIT=true
            ;;
        experiment)
            EXPERIMENT=true
            ;;
        *)
            echo "ERROR: Unknown argument: $arg"
            echo
            echo "Usage:"
            echo "  bash start.sh"
            echo "  bash start.sh experiment"
            echo "  bash start.sh init"
            echo "  bash start.sh init experiment"
            exit 1
            ;;
    esac
done


if [[ "$INIT" == true ]]; then
    echo "Starting all containers.."
    bash init.sh no-cache

    INIT_STATUS=$?

    if [[ "$INIT_STATUS" -ne 0 ]]; then
        echo "ERROR: Initialization failed."
        exit "$INIT_STATUS"
    fi

    echo "Initialization completed successfully."
fi


if [[ "$INIT" == true && "$EXPERIMENT" == false ]]; then
    echo
    echo "Initialization complete. No experiments requested."
    exit 0
fi


if [[ "$EXPERIMENT" == true ]]; then

    echo "Preparing concurrent SRE experiments..."

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

    BARRIER_DIR="/tmp/sre-lab-barrier-$$"
    mkdir -p "$BARRIER_DIR"

    READY_FILE="$BARRIER_DIR/ready"
    GO_FILE="$BARRIER_DIR/go"

    touch "$READY_FILE"

    cleanup() {
        rm -rf "$BARRIER_DIR"
    }

    trap cleanup EXIT

    echo "Launching experiments..."

    $PYTHON send.py all &
    PID1=$!

    $PYTHON send.py python &
    PID2=$!

    $PYTHON send.py --action slow python &
    PID3=$!

    $PYTHON send.py --action timeout python &
    PID4=$!

    $PYTHON load.py &
    PID5=$!

    bash t.sh &
    PID6=$!

    bash t.sh cache &
    PID7=$!

    $PYTHON chaos.py --workers 30 &
    PID8=$!

    line

    echo "All experiments launched."
    echo "PIDs:"
    echo "  send.py all              -> $PID1"
    echo "  send.py python           -> $PID2"
    echo "  send.py slow             -> $PID3"
    echo "  send.py timeout          -> $PID4"
    echo "  load.py                  -> $PID5"
    echo "  t.sh                     -> $PID6"
    echo "  t.sh cache               -> $PID7"
    echo "  chaos.py                 -> $PID8"
    echo
    echo "Waiting for experiment barrier..."
    echo "GO" > "$GO_FILE"
    echo
    echo "===================================================="
    echo "ALL EXPERIMENTS RELEASED"
    echo "===================================================="

    FAILURES=0

    for PID in \
        "$PID1" \
        "$PID2" \
        "$PID3" \
        "$PID4" \
        "$PID5" \
        "$PID6" \
        "$PID7" \
        "$PID8"
    do
        if wait "$PID"; then
            echo "PID $PID completed successfully."
        else
            echo "PID $PID FAILED."
            FAILURES=$((FAILURES + 1))
        fi
    done
    if [[ "$FAILURES" -eq 0 ]]; then 
      echo "All experiments completed successfully."
    fi
fi

line
echo "SRE RELIABILITY LAB APPLICATIONS"
line
echo
echo "Receiver A:"
echo "  http://localhost:5000"
echo
echo "Saver B:"
echo "  http://localhost:5001"
echo
echo "Notify:"
echo "  http://localhost:5002"
echo
echo "Prometheus:"
echo "  http://localhost:9090"
echo
echo "Alertmanager:"
echo "  http://localhost:9093"
echo
echo "Grafana:"
echo "  http://localhost:3000"
echo
echo "Loki:"
echo "  http://localhost:3100"
echo
echo "Alloy:"
echo "  http://localhost:12345"
echo
line
