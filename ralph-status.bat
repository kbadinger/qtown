@echo off
:: Check if Ralph is running and show recent activity

echo === Ralph Status ===
echo.

:: Check if process is running
tasklist /FI "WINDOWTITLE eq Ralph*" 2>NUL | find /I "python" >NUL
if %errorlevel%==0 (
    echo STATUS: Running
) else (
    :: Check via process name with command line
    wmic process where "commandline like '%%ralph.ralph%%'" get processid 2>NUL | find /V "ProcessId" | find /V "" >NUL
    if %errorlevel%==0 (
        echo STATUS: Running
    ) else (
        echo STATUS: Not running
    )
)

echo.
echo === HUMAN.md Action ===
powershell -Command "Select-String -Path HUMAN.md -Pattern 'action:' | ForEach-Object { $_.Line.Trim() }"

echo.
echo === Last 10 log lines ===
if exist ralph.log (
    powershell -Command "Get-Content ralph.log -Tail 10"
) else (
    echo No log file yet
)

echo.
echo === Recent Alerts ===
if exist alerts.log (
    powershell -Command "Get-Content alerts.log -Tail 5"
) else (
    echo No alerts
)
