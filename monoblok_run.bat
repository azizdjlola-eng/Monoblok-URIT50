@echo off
rem ─────────────────────────────────────────────────────────────────────────
rem  Natija (Monoblok) dasturini ishga tushirish.
rem
rem  QOIDA (2026-08-15): Python yo'li QATTIQ YOZILMAYDI. Ilgari bu yerda
rem  "C:\Users\1111111111\...\python.exe" turardi — o'sha nomdagi foydalanuvchi
rem  yo'q kompyuterda bu fayl JIMGINA hech narsa qilmasdi. Endi Python o'zi
rem  topiladi: avval `py` (Windows Python launcher), keyin PATH dagi `python`,
rem  oxirida shu kompyuterning standart o'rnatish papkasi.
rem ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not defined PYEXE (
    echo Python topilmadi. Python o'rnatilganini tekshiring.
    pause
    exit /b 1
)

start "" /min %PYEXE% "%~dp0monoblok_dastur.py"
