@echo off
rem Build the Asura capital headlessly and log the whole run.
set "BL=E:\SteamLibrary\steamapps\common\Blender\blender.exe"
set "SCRIPT=E:\My World\Blender\kingdom\capital.py"
set "LOG=E:\My World\Blender\renders\kingdom\cap_out.log"
"%BL%" -b --factory-startup --python "%SCRIPT%" -- %* > "%LOG%" 2>&1
echo EXITCODE=%ERRORLEVEL%>>"%LOG%"
