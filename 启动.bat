@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo Multi-Agent Office Document Revision Assistant
echo ========================================
echo.

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt was not found.
  echo Please make sure this batch file is in the project root folder.
  echo.
  pause
  exit /b 1
)

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [SETUP] Virtual environment was not found. Creating .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [INFO] python command failed. Trying py -3 ...
    py -3 -m venv .venv
  )
  if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create virtual environment.
    echo Please install Python 3.10 or newer and add it to PATH.
    echo.
    pause
    exit /b 1
  )
)

if not exist "%VENV_PY%" (
  echo.
  echo [ERROR] Virtual environment exists, but %VENV_PY% was not found.
  echo.
  pause
  exit /b 1
)

echo [SETUP] Installing or updating dependencies ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to install dependencies.
  echo Please check your network connection and the pip output above.
  echo.
  pause
  exit /b 1
)

echo.
echo [START] Opening the web app ...
"%VENV_PY%" run_gui.py
if errorlevel 1 (
  echo.
  echo [ERROR] The application failed to run.
  echo Please check the error message above.
  echo.
  pause
  exit /b 1
)

endlocal
