@echo off
setlocal
cd /d "%~dp0"
python launch_skraft_view.py
if errorlevel 1 pause
