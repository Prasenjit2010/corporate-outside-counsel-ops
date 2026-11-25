@echo off
REM CounselGrid launcher for Windows. Creates a private virtual environment on
REM first run, then starts the app on http://localhost:8501
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist .venv (
  echo First run: creating local environment ^(one time, about a minute^)...
  %PY% -m venv .venv || goto :nopython
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\python -m pip install --quiet -r requirements.txt
)

.venv\Scripts\python -m streamlit run app.py
goto :eof

:nopython
echo Python 3.10 or newer is required: https://www.python.org/downloads/
pause
