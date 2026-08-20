#!/bin/bash

echo "STARTING...."


start() {
  local arg="${1:-cache}"

  if [[ "$arg" == "no-cache" ]]; then
    echo "Building without Cache"
        docker compose build --no-cache
        docker compose up
  elif [[ "$arg" == "clean" ]]; then
    echo "Cleaning unused build cache..."
    docker builder prune -af
  else
    echo "Cache Build"
    docker compose up --build
  fi
}

start "$1"
