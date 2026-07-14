@echo off
setlocal EnableExtensions
title Save to git (commit + push)
cd /d "%~dp0"

REM ============================================================================
REM  Commits the current state and pushes it to GitHub. Double-click this
REM  whenever you want to save your latest changes. (Run git_setup.bat once
REM  first if this folder isn't a git repo yet.)
REM ============================================================================

where git >nul 2>&1 || ( echo Git isn't installed. Get it from https://git-scm.com/download/win & pause & exit /b 1 )
if not exist ".git" ( echo This folder isn't a git repo yet - run git_setup.bat first. & pause & exit /b 1 )

REM clear any stale lock (e.g. left by an interrupted git operation) so the commit isn't blocked
if exist ".git\index.lock" del /q ".git\index.lock"

echo.
echo   Staging changes...
git add -A

echo   Committing...
git commit -m "Update: 42-town meeting scraper + keyword digest (minutes fix, 150 MB size cap, master index)"
if errorlevel 1 echo   (nothing new to commit - continuing to push in case earlier commits are unpushed)

echo   Pushing to GitHub...
git push
if errorlevel 1 (
  echo.
  echo   *** Push failed. Usually that means no remote is set or you weren't signed in.
  echo       If it's the first push, see the instructions git_setup.bat printed
  echo       (git remote add origin ... then git push -u origin main). ***
  echo.
  pause & exit /b 1
)

echo.
echo   Done - your latest changes are on GitHub.
echo.
pause
