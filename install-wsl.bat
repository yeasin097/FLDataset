@echo off
REM ============================================================
REM  FL Dataset Lab - install WSL2 + Ubuntu 24.04 (Windows side)
REM
REM  BEFORE running this:
REM   1. Open "Turn Windows features on or off"
REM   2. Tick  [x] Windows Subsystem for Linux
REM            [x] Virtual Machine Platform
REM   3. Click OK and RESTART your PC.
REM
REM  Then right-click this file -> "Run as administrator".
REM ============================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Please right-click this file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

echo.
echo [1/3] Setting WSL default version to 2...
wsl --set-default-version 2

echo.
echo [2/3] Updating the WSL engine...
wsl --update

echo.
echo [3/3] Installing Ubuntu 24.04 (downloads a few hundred MB)...
wsl --install -d Ubuntu-24.04

echo.
echo ============================================================
echo  Done.
echo  - If this was the first time, RESTART your PC now.
echo  - Then open "Ubuntu 24.04" from the Start menu. It will ask
echo    you to create a username and password (pick any, remember them).
echo  - Continue with STEP 1b in docs\STUDENT.md.
echo ============================================================
echo.
pause
