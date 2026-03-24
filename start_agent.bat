@echo off
setlocal

cd /d "%~dp0"

if not exist "logs" mkdir "logs"

echo [%date% %time%] Launching agent...>> "logs\agent-launch.log"

if exist "venv\Scripts\python.exe" (
    echo Using venv Python>> "logs\agent-launch.log"
    call "venv\Scripts\python.exe" agent.py
    goto finish
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Using py launcher>> "logs\agent-launch.log"
    call py -3 agent.py
    goto finish
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Using system python>> "logs\agent-launch.log"
    call python agent.py
    goto finish
)

echo Python was not found. Install Python or create venv\Scripts\python.exe.
echo [%date% %time%] Python not found>> "logs\agent-launch.log"
pause
exit /b 1

:finish
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] Agent stopped with code %EXIT_CODE%>> "logs\agent-launch.log"
if not "%EXIT_CODE%"=="0" (
    echo Agent exited with code %EXIT_CODE%.
    echo Check logs\agent.log and logs\agent-launch.log for details.
    pause
)

exit /b %EXIT_CODE%
