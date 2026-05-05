@echo off
:: Stop Ralph gracefully via HUMAN.md pause action

cd /d D:\Projects\qtown

:: Set pause action in HUMAN.md frontmatter
powershell -Command "(Get-Content HUMAN.md) -replace 'action:\s*\w+', 'action: pause' | Set-Content HUMAN.md"

echo [%date% %time%] Ralph stop requested via HUMAN.md >> ralph.log
echo Ralph will stop after finishing the current story.
echo To resume later, run ralph-start.bat and set HUMAN.md action to 'none'.
