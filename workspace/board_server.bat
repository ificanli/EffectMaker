@echo off
rem Beads 本地网页看板启动脚本（Windows）
rem 用法：board_server.bat [--port 8611] [--no-browser]
cd /d "%~dp0.."
python -m workspace.tools.board_server %*
if errorlevel 1 pause
