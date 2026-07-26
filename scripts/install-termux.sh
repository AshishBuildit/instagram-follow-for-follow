#!/data/data/com.termux/files/usr/bin/bash
# Purana naam. Asli setup ab repo ke root me setup.sh hai.
exec bash "$(cd "$(dirname "$0")/.." && pwd)/setup.sh" "$@"
