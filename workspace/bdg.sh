#!/usr/bin/env bash
# bdg — Beads 强制工作记录门禁（macOS / Linux / Git Bash）
# 用法：./bdg.sh create "标题" --description ... | close <id> --reason ... | guard-check
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m workspace.tools.bd_guard "$@"
