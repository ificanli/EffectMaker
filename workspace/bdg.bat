@echo off
rem Beads guarded work-record entry point for Windows.
rem Usage: bdg.bat create "title" --description ... | close id --reason ... | guard-check
cd /d "%~dp0.."
python -m workspace.tools.bd_guard %*
if errorlevel 1 exit /b %errorlevel%
