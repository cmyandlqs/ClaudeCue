@echo off
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ISCC="
set "ISCC_X86=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
set "ISCC_X64=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if exist "%ISCC_X86%" set "ISCC=%ISCC_X86%"
if not defined ISCC if exist "%ISCC_X64%" set "ISCC=%ISCC_X64%"

if not defined ISCC (
    for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1" /v InstallLocation 2^>nul ^| findstr /I "InstallLocation"') do (
        set "REG_INSTALL=%%B"
    )
    if defined REG_INSTALL if exist "!REG_INSTALL!ISCC.exe" set "ISCC=!REG_INSTALL!ISCC.exe"
)

if not defined ISCC (
    for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1" /v InstallLocation 2^>nul ^| findstr /I "InstallLocation"') do (
        set "REG_INSTALL=%%B"
    )
    if defined REG_INSTALL if exist "!REG_INSTALL!ISCC.exe" set "ISCC=!REG_INSTALL!ISCC.exe"
)

if not defined ISCC (
    for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do (
        set "ISCC=%%~fI"
        goto :found_iscc
    )
)

:found_iscc
if not defined ISCC (
    echo ERROR: ISCC not found at:
    echo   !ISCC_X86!
    echo   !ISCC_X64!
    echo Install Inno Setup 6 first: https://jrsoftware.org/isdl.php
    exit /b 1
)

echo Using ISCC:
echo   !ISCC!

pushd "%SCRIPT_DIR%"
"!ISCC!" "ccCue.iss"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if !EXIT_CODE! NEQ 0 (
    echo Build failed.
    exit /b !EXIT_CODE!
)

echo Build succeeded.
exit /b 0
