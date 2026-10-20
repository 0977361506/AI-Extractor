@echo off
rem Ghep cac phan thanh AI-Extractor-win64-e57774e.zip va kiem tra ma SHA256. Chay: bam dup ghep.bat
setlocal
cd /d "%~dp0"
if exist "AI-Extractor-win64-e57774e.zip" del "AI-Extractor-win64-e57774e.zip"
echo Dang ghep 12 phan thanh AI-Extractor-win64-e57774e.zip ...
copy /b "AI-Extractor-win64-e57774e.zip.001"+"AI-Extractor-win64-e57774e.zip.002"+"AI-Extractor-win64-e57774e.zip.003"+"AI-Extractor-win64-e57774e.zip.004"+"AI-Extractor-win64-e57774e.zip.005"+"AI-Extractor-win64-e57774e.zip.006"+"AI-Extractor-win64-e57774e.zip.007"+"AI-Extractor-win64-e57774e.zip.008"+"AI-Extractor-win64-e57774e.zip.009"+"AI-Extractor-win64-e57774e.zip.010"+"AI-Extractor-win64-e57774e.zip.011"+"AI-Extractor-win64-e57774e.zip.012" "AI-Extractor-win64-e57774e.zip" >nul || goto :fail
echo Dang kiem tra ma SHA256 ...
for /f "delims=" %%h in ('certutil -hashfile "AI-Extractor-win64-e57774e.zip" SHA256 ^| findstr /v ":"') do (set "GOT=%%h" & goto :check)
:check
set "GOT=%GOT: =%"
if /i "%GOT%"=="49b8e1f70c9eab9b7ba8f307743d4c6e4cce48d6bc2588d1fda8a3ff0635dbf3" (
  echo OK - file AI-Extractor-win64-e57774e.zip nguyen ven. Giai nen file nay roi chay run.bat ^(xem README.md^).
  pause
  exit /b 0
)
echo LOI: ma SHA256 khong khop ^(%GOT%^). Tai lai cac phan .0xx roi chay lai ghep.bat.
:fail
pause
exit /b 1
