@echo off
setlocal
pushd "%~dp0.."
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
python -m unittest discover -s tests -v
set "CHECK_RESULT=%ERRORLEVEL%"
popd
exit /b %CHECK_RESULT%
