@echo off
if "%1"=="" goto end
cd dist
set FILENAME=kovans-ogbot-windows_%1.rar
echo "Filename will be: %FILENAME%"
del *.rar
rar a -r -s -m5 %FILENAME% *
python ..\googlecode-upload.py -s "Kovan's OGBot for Windows %1" -p kovans-ogbot -u jsceballos -l "Featured, Type-Archive, OpSys-Windows" %FILENAME%
:end
