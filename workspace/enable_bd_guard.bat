@echo off
rem 启用 bd 守卫（Windows）：把 workspace/bin 前置到 PATH，让裸 bd 走守卫 wrapper。
rem 只对当前会话生效（setx 需要管理员权限，改用户级 PATH 请自行确认）。
rem 用法：call workspace\enable_bd_guard.bat
set "BDGUARD_DIR=%~dp0bin"
set "PATH=%BDGUARD_DIR%;%PATH%"
echo [bd-guard] 已启用：%BDGUARD_DIR% 已前置到 PATH
echo [bd-guard] 现在 bd create/close/update 等写操作会被拦截并引导到 bdg
echo [bd-guard] 验证：bd list ^(应正常^)  /  bd create test ^(应被拦截^)
