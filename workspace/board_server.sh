#!/usr/bin/env bash
# Beads 本地网页看板启动脚本（macOS / Linux / Git Bash）
# 用法：./board_server.sh [--port 8611] [--no-browser]
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m workspace.tools.board_server "$@"
