@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Listen Signal needs Python 3.10 or newer.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating Listen Signal's private Python environment...
  py -3 -m venv .venv
)
".venv\Scripts\python.exe" -c "import streamlit, feedparser, sklearn, yaml" >nul 2>&1
if errorlevel 1 (
  echo Installing Listen Signal's open-source packages...
  ".venv\Scripts\python.exe" -m pip --disable-pip-version-check install --prefer-binary -r requirements.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
if "%LISTENSIGNAL_PORT%"=="" set LISTENSIGNAL_PORT=8595
set ARROW_DEFAULT_MEMORY_POOL=system
echo Starting Listen Signal at http://127.0.0.1:%LISTENSIGNAL_PORT% ...
echo The fictional demo is loaded; no network is needed to explore it.
if not "%LISTENSIGNAL_NO_BROWSER%"=="1" start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:%LISTENSIGNAL_PORT%"
if "%LISTENSIGNAL_MAX_UPLOAD_MB%"=="" set LISTENSIGNAL_MAX_UPLOAD_MB=10000
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=%LISTENSIGNAL_PORT% --server.maxUploadSize=%LISTENSIGNAL_MAX_UPLOAD_MB% --server.fileWatcherType=none --browser.gatherUsageStats=false
if errorlevel 1 pause
