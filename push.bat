@echo off
chcp 65001 >nul
title AzizMedLine - GitHub Sync

:REPO_MENU
cls
echo.
echo ==========================================
echo    GitHub Sync - Loyiha tanlang
echo ==========================================
echo.
echo   1.  AzizMedLine LIMS
echo   2.  Monoblok URIT50
echo   0.  Chiqish
echo.
set /p R="Loyiha tanlang (1 / 2 / 0): "

if "%R%"=="1" ( set "REPO_PATH=D:\AzizMedLine_LIMS" & set "REPO_NAME=AzizMedLine LIMS" & goto MENU )
if "%R%"=="2" ( set "REPO_PATH=G:\DASTUR\URIT 50" & set "REPO_NAME=Monoblok URIT50" & goto MENU )
if "%R%"=="0" exit
goto REPO_MENU

:MENU
cls
echo.
echo ==========================================
echo    %REPO_NAME% - GitHub Sync
echo ==========================================
echo.
echo   1.  YUBORISH      ( Kompyuter -- GitHub )
echo   2.  QABUL QILISH  ( GitHub -- Kompyuter )
echo   3.  Loyiha almashtirish
echo   0.  Chiqish
echo.
set /p T="Tanlang (1 / 2 / 3 / 0): "

if "%T%"=="1" goto PUSH
if "%T%"=="2" goto PULL
if "%T%"=="3" goto REPO_MENU
if "%T%"=="0" exit
goto MENU

:PUSH
cd /d "%REPO_PATH%"
echo.
set /p MSG="Sarlavha yozing: "
if "%MSG%"=="" ( echo Sarlavha bosh! & pause & goto MENU )
git add .
git commit -m "%MSG%"
git pull --rebase origin main
git push origin main
echo.
if %errorlevel%==0 ( echo   OK - Yuborildi! ) else ( echo   XATO! )
pause
goto MENU

:PULL
cd /d "%REPO_PATH%"
echo.
git pull
echo.
if %errorlevel%==0 ( echo   OK - Qabul qilindi! ) else ( echo   XATO! )
pause
goto MENU
