@echo off
rem Project RETR0 - run:  client.cmd status | apply | restore | install-fresh | play | ui-text | ui-text-restore | fix-reboot
rem Runs client.ps1 for this one command only (does not change the PC's PowerShell policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0client.ps1" %*
if "%~1"=="" pause
