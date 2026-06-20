#!/usr/bin/env bash
#
# skill-forge demo — run from the repo root after `pip install -e .`
#
#   bash examples/demo.sh
#
# Everything here is offline and deterministic. No API key required.

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT

bold="\033[1m"; dim="\033[2m"; reset="\033[0m"
step() { printf "\n${bold}== %s ==${reset}\n" "$1"; }

step "1. Forge a skill from a Python project (to stdout)"
skill-forge forge "$here/sample_tool" --stdout

step "2. Forge a skill straight from a doc (this repo's README)"
skill-forge forge "$root/README.md" --name skill-forge-readme -o "$out"

step "3. Lint everything we generated"
skill-forge lint "$out"

step "4. Drift check — regenerate and confirm it is in sync"
skill-forge forge "$here/sample_tool" -o "$out" --force >/dev/null
skill-forge check "$here/sample_tool" --name sample-tool -o "$out"

printf "\n${dim}(generated under %s — cleaned up on exit)${reset}\n" "$out"
