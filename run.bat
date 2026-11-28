@echo off
REM CounselGrid launcher for Windows. Creates a private virtual environment on
REM first run, then starts the app on http://localhost:8501
REM The app binds to this computer only and is not reachable from the network.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist .venv\.counselgrid-installed (
  echo Setting up local environment ^(one time, about a minute^)...
  %PY% -m venv .venv || goto :nopython
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\python -m pip install --quiet -r requirements.txt || goto :installfailed
  type nul > .venv\.counselgrid-installed
)

.venv\Scripts\python -m streamlit run app.py --server.address localhost --browser.serverAddress localhost
goto :eof

:nopython
echo Python 3.10 or newer is required: https://www.python.org/downloads/
pause
goto :eof

:installfailed
echo Installing the required packages failed. Check your internet connection and run this file again.
pause
