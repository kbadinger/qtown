@echo off
:: Install Ralph as a Windows Scheduled Task
:: Starts on user login, restarts on crash (up to 3 times)
:: Run this once as Administrator

echo Installing Ralph scheduled task...

:: Delete existing task if present
schtasks /Delete /TN "Ralph" /F 2>NUL

:: Create task that runs on login
schtasks /Create /TN "Ralph" /TR "D:\Projects\qtown\ralph-start.bat" /SC ONLOGON /RL HIGHEST /F

:: Configure restart-on-failure via XML (schtasks /Create doesn't support all options)
:: Export, modify, reimport
schtasks /Query /TN "Ralph" /XML > "%TEMP%\ralph-task.xml"

powershell -Command ^
  "$xml = [xml](Get-Content '%TEMP%\ralph-task.xml');" ^
  "$ns = New-Object Xml.XmlNamespaceManager($xml.NameTable);" ^
  "$ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task');" ^
  "$settings = $xml.SelectSingleNode('//t:Settings', $ns);" ^
  "$restart = $xml.CreateElement('RestartOnFailure', 'http://schemas.microsoft.com/windows/2004/02/mit/task');" ^
  "$interval = $xml.CreateElement('Interval', 'http://schemas.microsoft.com/windows/2004/02/mit/task');" ^
  "$interval.InnerText = 'PT1M';" ^
  "$count = $xml.CreateElement('Count', 'http://schemas.microsoft.com/windows/2004/02/mit/task');" ^
  "$count.InnerText = '3';" ^
  "$restart.AppendChild($interval) | Out-Null;" ^
  "$restart.AppendChild($count) | Out-Null;" ^
  "$settings.AppendChild($restart) | Out-Null;" ^
  "$xml.Save('%TEMP%\ralph-task.xml')"

schtasks /Delete /TN "Ralph" /F 2>NUL
schtasks /Create /TN "Ralph" /XML "%TEMP%\ralph-task.xml" /F

echo.
echo Done! Ralph will:
echo   - Start automatically on login
echo   - Restart up to 3 times if it crashes (1 min delay)
echo.
echo Commands:
echo   ralph-start.bat   — start Ralph now
echo   ralph-stop.bat    — graceful stop (finishes current story)
echo   ralph-status.bat  — check if running + recent logs
echo.
echo To remove: schtasks /Delete /TN "Ralph" /F
