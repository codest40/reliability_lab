#!/bin/bash

echo "STARTING...."


usage() {
    echo "USAGE: $0 cache|no-cache|clean" && exit 1
}

start() {
  a=$1
  if [[ -z "$a" ]]; then
    usage
  fi

  local arg="${1:-cache}"

  if [[ "$arg" == "no-cache" ]]; then
    echo "Building without Cache"
        docker compose build --no-cache
        docker compose up -d
  elif [[ "$arg" == "clean" ]]; then
    echo "Cleaning unused build cache..."
    docker builder prune -af
  elif [[ "$arg" == "cache" ]]; then
    echo "Cache Build"
    docker compose up -d --build
  else
    echo "$arg is NOT recognixed"
    usage
  fi
}

start "$1"
