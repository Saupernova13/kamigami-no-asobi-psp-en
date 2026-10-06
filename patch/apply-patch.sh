#!/bin/sh
# Apply the English patch: sh apply-patch.sh /path/to/original.iso
set -e
if [ -z "$1" ]; then
  echo "usage: sh apply-patch.sh /path/to/original.iso" >&2
  exit 1
fi
here=$(cd "$(dirname "$0")" && pwd)
out="$(cd "$(dirname "$1")" && pwd)/Kamigami no Asobi - English v1.0.iso"
if ! command -v xdelta3 >/dev/null 2>&1; then
  echo "xdelta3 not found: install it (apt install xdelta3, brew install xdelta)" >&2
  exit 1
fi
xdelta3 -d -s "$1" "$here/Kamigami-no-Asobi-EN-v1.0.xdelta" "$out"
echo "Done: $out"
