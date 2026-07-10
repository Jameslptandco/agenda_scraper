@echo off
setlocal EnableExtensions
title Put council_meetings on git
cd /d "%~dp0"

REM --- Make sure git is installed ---
where git >nul 2>&1 || (
  echo.
  echo   Git isn't installed. Get it from https://git-scm.com/download/win
  echo   then run this file again.
  echo.
  pause & exit /b 1
)

REM --- Make sure there's a commit identity (local to this repo; change anytime) ---
git config user.email >nul 2>&1 || git config user.email "james@lptandco.com"
git config user.name  >nul 2>&1 || git config user.name  "James"

REM --- Init if needed ---
if exist ".git" (
  echo   Already a git repo here - committing any changes...
) else (
  echo   Creating a new git repo...
  git init
)
git branch -M main

REM --- Commit ---
git add .
git commit -m "Council agendas + minutes scraper: Cornwall + 9 Prescott-Russell towns (eScribe + CivicWeb)"

echo.
echo   ============================================================
echo   Done - your code is committed locally (secrets excluded).
echo.
echo   To put it on GitHub when you're ready:
echo     1) Make a new EMPTY repo on github.com (no README/.gitignore)
echo     2) Paste these two lines here, with your repo's URL:
echo          git remote add origin https://github.com/YOU/REPO.git
echo          git push -u origin main
echo   ============================================================
echo.
pause
