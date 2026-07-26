@echo off
REM Windows par bot chalane ke liye. Double click karo ya Task Scheduler me daalo.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m ff_bot
) else (
    python -m ff_bot
)
pause
