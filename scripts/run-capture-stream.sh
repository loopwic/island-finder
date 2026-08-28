#!/bin/zsh
set -euo pipefail

AF_PROJECT_ROOT=${0:A:h:h}
AF_SOURCE="$AF_PROJECT_ROOT/scripts/capture-stream.swift"
AF_BUILD_DIR="$AF_PROJECT_ROOT/.build/native-capture"
AF_BINARY="$AF_BUILD_DIR/capture-stream"

if [[ ! -x "$AF_BINARY" || "$AF_SOURCE" -nt "$AF_BINARY" ]]; then
  mkdir -p "$AF_BUILD_DIR"
  swiftc -O "$AF_SOURCE" -o "$AF_BINARY" \
    -framework AVFoundation \
    -framework VideoToolbox
fi

exec "$AF_BINARY" "$@"
