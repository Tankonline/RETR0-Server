@echo off
rem Project RETR0 - build "RETR0 Server.exe" with the C# compiler that ships with Windows (.NET Framework 4.x).
rem Usage: build.cmd [output.exe]     default: "RETR0 Server.exe" two folders up (the server package root,
rem        when this folder is <server>\tools\control_panel\). Rebuild only when RETR0ControlPanel.cs changes;
rem        the Python services and scripts are separate files and need no rebuild.
setlocal
set "HERE=%~dp0"
set "OUT=%~1"
if "%OUT%"=="" set "OUT=%HERE%..\..\RETR0 Server.exe"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" ( echo C# compiler not found: .NET Framework 4.x is part of Windows 10/11 & exit /b 1 )
"%CSC%" /nologo /target:winexe /optimize+ /out:"%OUT%" ^
  /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll ^
  "%HERE%RETR0ControlPanel.cs"
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo built: %OUT%
endlocal
