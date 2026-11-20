@echo off
rem RETR0: start Real Racing 3 on the test emulator, connected to this server until you close it.
rem Needs the server running (retr0_server.cmd start -WithSync) and the RETR0 client on the emulator
rem (client.ps1 apply, once). No Frida and no project scripts are involved.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0client.ps1" play
