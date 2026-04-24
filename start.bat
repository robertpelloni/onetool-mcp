@echo off
setlocal
title OneTool MCP
cd /d "%~dp0"

echo [OneTool MCP] Starting...
python --version >nul 2>nul
if errorlevel 1 (
    echo [OneTool MCP] python not found. Please install it.
    pause
    exit /b 1
)

python -m onetool_mcp

if errorlevel 1 (
    echo [OneTool MCP] Exited with error code %errorlevel%.
    pause
)
endlocal
