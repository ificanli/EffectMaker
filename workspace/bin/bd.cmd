@echo off
rem bd 守卫 wrapper（Windows）
rem 拦截写操作并引导走 bdg（强制工作记录），只读操作透明转发真实 bd。
rem 本文件被 PATH 前置后生效；真实 bd 在 npm 全局 bin 目录（自动探测）。
rem
rem 拦截规则：
rem   create / close / update / note / comment / delete / import / edit / merge  -> 引导 bdg
rem   list / show / ready / query / search / state / children / labels / history / count 等 -> 透明转发
setlocal
set "CMD=%~1"

rem 探测真实 bd（npm 全局 bin 目录优先，避免递归调用本 wrapper）
set "REAL_BD="
for /f "delims=" %%i in ('npm prefix -g 2^>nul') do set "NPM_BIN=%%i"
if defined NPM_BIN if exist "%NPM_BIN%\bd.cmd" set "REAL_BD=%NPM_BIN%\bd.cmd"
if not defined REAL_BD (
  where bd >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%i in ('where bd') do (
      rem 跳过本 wrapper 自身，避免递归
      if not defined REAL_BD if /i not "%%i"=="%~dp0bd.cmd" set "REAL_BD=%%i"
    )
  )
)
if not defined REAL_BD (
  echo [bd-guard] 找不到真实 bd ^(npm prefix -g 无 bd.cmd，PATH 也无^). 1>&2
  exit /b 127
)

rem 拦截的写操作
echo %CMD% | findstr /i /r "^create ^close ^update ^note ^comment ^delete ^import ^edit ^merge ^set-state ^tag ^label ^promote" >nul
if not errorlevel 1 (
  echo [bd-guard] 检测到写操作 'bd %*' 1>&2
  echo [bd-guard] 本仓库强制工作记录：写操作必须走 bdg ^(创建/关闭/备注/评论/认领^). 1>&2
  echo [bd-guard] 正确用法： 1>&2
  echo   python -m workspace.tools.bd_guard create "标题" --description ... --acceptance ... --notes ... 1>&2
  echo   python -m workspace.tools.bd_guard close ^<id^> --reason "完成：..." --require-notes 1>&2
  echo   python -m workspace.tools.bd_guard note ^<id^> "阶段结论/弯路" 1>&2
  echo   python -m workspace.tools.bd_guard claim ^<id^> 1>&2
  echo [bd-guard] 详见 docs/30-操作指南/工作记录强制规范.md 1>&2
  exit /b 3
)

rem 只读/其他操作：透明转发真实 bd
"%REAL_BD%" %*
exit /b %errorlevel%
