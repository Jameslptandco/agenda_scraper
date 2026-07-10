@echo off
setlocal EnableExtensions
title Schedule EO Council Meetings scraper

REM ============================================================================
REM  Sets up the Eastern Ontario council agenda/minutes scraper to run
REM  automatically every 6 hours (Cornwall + the 9 Prescott-Russell towns).
REM  Just double-click this file. If it says access denied, right-click it
REM  and choose "Run as administrator".
REM ============================================================================

REM --- Find a Python launcher (prefer the 'py' launcher, fall back to 'python') ---
set "PYCMD="
where py     >nul 2>&1 && set "PYCMD=py"
if not defined PYCMD ( where python >nul 2>&1 && set "PYCMD=python" )
if not defined PYCMD (
  echo.
  echo   Could not find Python on this PC.
  echo   Install Python 3 from https://www.python.org/downloads/ then run this again.
  echo.
  pause & exit /b 1
)

set "SCRIPT=%~dp0council_meetings.py"

echo.
echo   Creating scheduled task "EO_CouncilMeetings" (runs every 6 hours: 6am, 12pm, 6pm, 12am)...
echo.
schtasks /create /tn "EO_CouncilMeetings" /sc hourly /mo 6 /st 06:00 /f /tr "%PYCMD% %SCRIPT%"

if errorlevel 1 (
  echo.
  echo   *** Could not create the task. Right-click this file and choose
  echo       "Run as administrator", then try again. ***
  echo.
  pause & exit /b 1
)

echo.
echo   Done - it will now run by itself every 6 hours.
echo.
set /p RUNNOW="   Run it once right now to test? First run can take several minutes and download a few hundred MB (Y/N): "
if /i "%RUNNOW%"=="Y" (
  echo.
  echo   Running... (leave this window open until it finishes)
  echo.
  cd /d "%~dp0"
  %PYCMD% "%SCRIPT%"
)

echo.
echo   All set. You can close this window.
pause
