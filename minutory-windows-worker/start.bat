@echo off
setlocal
set "WORKER_ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%WORKER_ROOT%start.ps1"
if errorlevel 1 (
  echo Minutory Worker could not start. Review the message above.
  pause
  exit /b 1
)
endlocal
