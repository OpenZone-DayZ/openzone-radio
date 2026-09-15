@echo off
rem Double-click to monitor the DayZ server for 24 hours (see script-profile.ps1).
rem The PowerShell window that opens asks for elevation, then stays up; close it to stop.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0script-profile.ps1" -Hours 24
