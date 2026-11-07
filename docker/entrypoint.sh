#!/bin/sh
# Runs one HODE analysis and proves it is reproducible:
#   1. hode run <config>        -> results/results.csv + results/manifest.json
#   2. hode verify <manifest>   -> reruns from the manifest and compares hashes
# Exit code is non-zero if either step fails, so CI and Kubernetes see the failure.
set -eu
CONFIG="${1:-configs/synthetic.toml}"
echo "== hode $(hode --version | cut -d' ' -f2) | config: ${CONFIG}"
hode run "${CONFIG}"
hode verify results/manifest.json
