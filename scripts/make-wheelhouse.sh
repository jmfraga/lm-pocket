#!/usr/bin/env bash
# Build an offline wheelhouse for LM-Pocket, one folder per OS/CPU, for one Python version.
#
#   scripts/make-wheelhouse.sh <dest> [python-version]     e.g. /Volumes/USB/app/wheelhouse 3.12
#
# Needs internet on the machine that runs it, and uv. See docs/offline.md.
set -euo pipefail

DEST="${1:?usage: make-wheelhouse.sh <dest> [python-version]}"
PY="${2:-3.12}"
CP="cp${PY/./}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$DEST"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
uv build --wheel --out-dir "$BUILD" "$ROOT" >/dev/null
WHEEL="$(ls "$BUILD"/lm_pocket-*.whl)"

# Plain functions instead of associative arrays: macOS ships bash 3.2.
# pip download --platform evaluates environment markers against the HOST
# (so a Windows wheelhouse built on a Mac would miss pywin32/colorama).
# uv pip compile --python-platform resolves for the TARGET; pip only downloads.
triple_for() {
  case "$1" in
    macos-arm64)   echo "aarch64-apple-darwin" ;;
    macos-x86_64)  echo "x86_64-apple-darwin" ;;
    linux-x86_64)  echo "x86_64-manylinux_2_28" ;;
    linux-aarch64) echo "aarch64-manylinux_2_28" ;;
    windows-amd64) echo "x86_64-pc-windows-msvc" ;;
  esac
}

tags_for() {
  case "$1" in
    macos-arm64)   echo "macosx_11_0_arm64 macosx_10_9_universal2 macosx_10_13_universal2 macosx_10_15_universal2" ;;
    macos-x86_64)  echo "macosx_10_9_x86_64 macosx_10_13_x86_64 macosx_10_15_x86_64 macosx_10_9_universal2" ;;
    linux-x86_64)  echo "manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64" ;;
    linux-aarch64) echo "manylinux_2_28_aarch64 manylinux_2_17_aarch64 manylinux2014_aarch64" ;;
    windows-amd64) echo "win_amd64" ;;
  esac
}

for name in macos-arm64 macos-x86_64 linux-x86_64 linux-aarch64 windows-amd64; do
  out="$DEST/$name-$CP"
  mkdir -p "$out"
  flags=""
  for p in $(tags_for "$name"); do flags="$flags --platform $p"; done
  echo "== $name ($CP)"
  req="$BUILD/req-$name.txt"
  uv pip compile --quiet --no-header --only-binary :all: --python-version "$PY" --python-platform "$(triple_for "$name")" \
      "$ROOT/pyproject.toml" -o "$req"
  # shellcheck disable=SC2086
  uvx --quiet --from pip pip download --quiet --no-deps --dest "$out" --only-binary=:all: \
      --python-version "$PY" --implementation cp $flags -r "$req" "$WHEEL"
  echo "   $(ls "$out" | wc -l | tr -d ' ') wheels"
done
echo "Wheelhouse ready in $DEST"
