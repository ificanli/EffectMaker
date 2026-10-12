#!/usr/bin/env bash
# 启用 bd 守卫（macOS / Linux / Git Bash）：把 workspace/bin 前置到 PATH。
# 只对当前 shell 生效；要持久化请把它加进 ~/.bashrc / ~/.zshrc。
# 用法：source workspace/enable_bd_guard.sh
BDGUARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/bin" && pwd)"
export PATH="$BDGUARD_DIR:$PATH"
echo "[bd-guard] 已启用：$BDGUARD_DIR 已前置到 PATH"
echo "[bd-guard] 现在 bd create/close/update 等写操作会被拦截并引导到 bdg"
echo "[bd-guard] 验证：bd list (应正常)  /  bd create test (应被拦截)"
