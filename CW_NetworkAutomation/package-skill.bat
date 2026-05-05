@echo off
REM Double-clickable wrapper for package-skill.ps1.
REM Bypasses the default PowerShell execution-policy block so this works
REM without you having to fiddle with policy settings.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0package-skill.ps1"

echo.
pause
