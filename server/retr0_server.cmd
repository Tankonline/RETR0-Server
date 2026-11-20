@echo off
rem Project RETR0 - double-click or run:  retr0_server.cmd start | stop | status | restart [-WithSync]
rem Runs retr0_server.ps1 for this one command only (does not change the PC's PowerShell policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0retr0_server.ps1" %*
if "%~1"=="" pause
