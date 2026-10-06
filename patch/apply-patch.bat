@echo off
setlocal
if "%~1"=="" (
  echo Drag the original Japanese ISO onto this file.
  pause
  exit /b 1
)
where xdelta3 >nul 2>nul
if errorlevel 1 (
  if not exist "%~dp0xdelta3.exe" (
    echo xdelta3.exe was not found. Download it from
    echo https://github.com/jmacd/xdelta-gpl/releases and put it next to this file.
    pause
    exit /b 1
  )
  set "XD=%~dp0xdelta3.exe"
) else (
  set "XD=xdelta3"
)
"%XD%" -d -s "%~1" "%~dp0Kamigami-no-Asobi-EN-v1.0.xdelta" "%~dp1Kamigami no Asobi - English v1.0.iso"
if errorlevel 1 (
  echo Patching failed. Check that the ISO is the original Japanese image.
) else (
  echo Done: %~dp1Kamigami no Asobi - English v1.0.iso
)
pause
