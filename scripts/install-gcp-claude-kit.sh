#!/usr/bin/env bash
set -euo pipefail

echo "RevenueFlow AI - GCP + Claude Code Dev Kit"

for cmd in gcloud claude; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[MISSING] $cmd"
    exit 1
  fi
  echo "[OK] $cmd"
done

gcloud auth login

read -r -p "Configure Application Default Credentials too? (y/N) " adc
if [[ "${adc:-}" =~ ^[Yy]$ ]]; then
  gcloud auth application-default login
fi

read -r -p "GCP PROJECT_ID: " project
if [[ -z "$project" ]]; then
  echo "PROJECT_ID is required"
  exit 1
fi

gcloud config set project "$project"

echo "Account: $(gcloud config get-value account)"
echo "Project: $(gcloud config get-value project)"
echo "No APIs were enabled and no infrastructure was deployed."
