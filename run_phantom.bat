@echo off
setlocal
cd /d "%~dp0"
title PHANTOM - Financial Fraud Intelligence DBMS
where py >nul 2>nul
if not errorlevel 1 goto use_launcher
where python >nul 2>nul
if not errorlevel 1 goto use_python
goto no_python

:use_launcher
py -3 app.py
goto finished

:use_python
python app.py
goto finished

:no_python
echo.
echo Python 3 was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
echo During installation, enable "Add Python to PATH".
echo Then double-click this file again.
pause
exit /b 1

:finished
if errorlevel 1 (
  echo.
  echo PHANTOM closed with an error. Review the message above.
  pause
)
endlocal
