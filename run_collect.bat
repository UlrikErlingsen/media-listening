@echo off
rem Listen Signal collector for Windows Task Scheduler (or a double-click).
rem Fetches the feeds enabled in sources.yaml once, appends to logs\collect.log and exits.
rem The collector itself skips any feed polled less than 30 minutes ago and re-checks robots.txt.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run run_app.bat once first to create Listen Signal's Python environment.
  exit /b 1
)
if not exist "logs" mkdir logs
set PYTHONIOENCODING=utf-8
set HF_HUB_OFFLINE=1
set PYTHONPATH=%~dp0src
echo ===== %date% %time% >> logs\collect.log
".venv\Scripts\python.exe" -m listensignal.collect %* >> logs\collect.log 2>&1
exit /b %errorlevel%
