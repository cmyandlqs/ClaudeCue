@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "BUNDLED_PY=%PROJECT_ROOT%\runtime\python\python.exe"
set "LOCAL_VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if exist "%BUNDLED_PY%" (
    set "PYTHON_EXE=%BUNDLED_PY%"
) else if exist "%LOCAL_VENV_PY%" (
    set "PYTHON_EXE=%LOCAL_VENV_PY%"
) else (
    set "PYTHON_EXE=python"
)

pushd "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m cli.main %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%

