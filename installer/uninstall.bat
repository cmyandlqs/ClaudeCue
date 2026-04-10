@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."

echo ========================================
echo ccCue Uninstaller (CLI Wrapper)
echo ========================================
echo.

pushd "%PROJECT_ROOT%"
python -m cli.main uninstall
set "EXIT_CODE=%ERRORLEVEL%"
popd

if %EXIT_CODE% NEQ 0 (
    echo.
    echo ERROR: uninstall failed.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo Uninstall completed.
pause
