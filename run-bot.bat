@echo off
REM OGBot Launcher Script for Windows

echo Starting Kovan's OGBot (Clojure Edition)...

REM Check if Leiningen is installed
where lein >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Leiningen not found!
    echo Please install Leiningen from https://leiningen.org/
    pause
    exit /b 1
)

REM Create necessary directories
if not exist "files\config" mkdir files\config
if not exist "files\botdata" mkdir files\botdata
if not exist "files\log" mkdir files\log
if not exist "debug" mkdir debug

REM Run the bot
if "%1"=="--no-gui" (
    lein run --no-gui
) else if "%1"=="--console" (
    lein run --no-gui
) else (
    lein run
)

pause
