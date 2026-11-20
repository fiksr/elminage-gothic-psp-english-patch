@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Drag and drop your clean Japanese ISO onto this script:
    echo   Elminage Gothic - Ulm Zakir to Yami no Gishiki ^(Japan^).iso
    echo.
    echo Or run:
    echo   apply_patch.bat "path\to\Elminage Gothic (Japan).iso"
    pause
    exit /b 1
)

set "SRC=%~1"
set "OUT=%~dpn1 [EN].iso"
set "PATCH=%~dp0Elminage_Gothic_PSP_EN.xdelta"
set "XDELTA=%~dp0xdelta3.exe"

if not exist "%XDELTA%" (
    echo ERROR: xdelta3.exe not found next to this script.
    pause
    exit /b 1
)
if not exist "%PATCH%" (
    echo ERROR: Elminage_Gothic_PSP_EN.xdelta not found next to this script.
    pause
    exit /b 1
)

echo Patching "%SRC%" -^> "%OUT%" ...
"%XDELTA%" -d -f -s "%SRC%" "%PATCH%" "%OUT%"
if errorlevel 1 (
    echo.
    echo ERROR: Patching failed. Make sure your source ISO is the unmodified Japanese UMD dump ^(ULJM06091^).
    pause
    exit /b 1
)

echo.
echo Done! Created: "%OUT%"
echo Note: In PPSSPP, keep Data Install set to NO ^(optional INSDIR files are PGD-encrypted^).
pause
