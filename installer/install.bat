@echo off
setlocal EnableDelayedExpansion

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CLAUDE_CONFIG=%USERPROFILE%\.claude"
set "SETTINGS_FILE=%CLAUDE_CONFIG%\settings.json"
set "HOOK_SCRIPT=%PROJECT_ROOT%\hooks\notify_hook.py"

echo ========================================
echo ccCue Hook Config Generator
echo ========================================
echo.

if not exist "%CLAUDE_CONFIG%" (
    mkdir "%CLAUDE_CONFIG%"
)

if exist "%SETTINGS_FILE%" (
    for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "BACKUP_TS=%%I"
    if "%BACKUP_TS%"=="" set "BACKUP_TS=backup"
    set "BACKUP_FILE=%CLAUDE_CONFIG%\settings.json.%BACKUP_TS%.backup"
    echo Backing up existing settings.json to:
    echo   !BACKUP_FILE!
    copy /Y "%SETTINGS_FILE%" "!BACKUP_FILE!" >nul
)

echo Writing hook config to:
echo   %SETTINGS_FILE%
echo.

powershell -NoProfile -Command ^
    "$hook = 'python \"' + $env:HOOK_SCRIPT + '\"'; " ^
    "$settings = @{ hooks = @{ " ^
    "Notification = @(@{ hooks = @(@{ type = 'command'; command = $hook }) }); " ^
    "Stop = @(@{ hooks = @(@{ type = 'command'; command = $hook }) }); " ^
    "PermissionRequest = @(@{ hooks = @(@{ type = 'command'; command = $hook }) }) " ^
    "} }; " ^
    "$settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $env:SETTINGS_FILE -Encoding UTF8"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to write settings.json
    pause
    exit /b 1
)

echo Done.
echo Hook script:
echo   %HOOK_SCRIPT%
echo.
echo Note: This script only writes hook config. It does NOT install Python or dependencies.
echo.
pause
