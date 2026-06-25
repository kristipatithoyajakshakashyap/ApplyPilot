@echo off
echo ApplyPilot — Graphify Watch Mode
echo Watching D:\projects\personal\job-hunt for changes...
echo Graph auto-rebuilds on every file save. Press Ctrl+C to stop.
echo.
"C:\Users\Thoyajaksha Kashyap\AppData\Local\Programs\Python\Python311\python.exe" -m graphify.watch "D:\projects\personal\job-hunt" --debounce 3
pause
