@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."

echo ========================================
echo ccCue Installer (CLI Wrapper)
echo ========================================
echo.

pushd "%PROJECT_ROOT%"
python -m cli.main install --source "%PROJECT_ROOT%" --target "%PROJECT_ROOT%"
set "EXIT_CODE=%ERRORLEVEL%"
popd
if %EXIT_CODE% NEQ 0 (
    echo.
    echo ERROR: install failed.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo Install completed.
pause
