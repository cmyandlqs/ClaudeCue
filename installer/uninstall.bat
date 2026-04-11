@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "NO_PAUSE=0"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

echo ========================================
echo ccCue Uninstaller (CLI Wrapper)
echo ========================================
echo.

pushd "%PROJECT_ROOT%"
call "%PROJECT_ROOT%\installer\cccue.bat" uninstall
set "EXIT_CODE=%ERRORLEVEL%"
popd

if %EXIT_CODE% NEQ 0 (
    echo.
    echo ERROR: uninstall failed.
    if "%NO_PAUSE%"=="0" pause
    exit /b %EXIT_CODE%
)

echo.
echo Uninstall completed.
if "%NO_PAUSE%"=="0" pause
