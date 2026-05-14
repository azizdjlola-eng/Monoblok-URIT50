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
cd /d "%REPO_PATH%"
git fetch origin main >nul 2>&1
set "LAST_LOCAL=(yoq)"
set "LAST_REMOTE=(yoq)"
for /f "usebackq delims=" %%a in (`git log -1 --pretty^=format:"%%s" 2^>nul`) do set "LAST_LOCAL=%%a"
for /f "usebackq delims=" %%a in (`git log -1 origin/main --pretty^=format:"%%s" 2^>nul`) do set "LAST_REMOTE=%%a"

set "LOCAL_HASH="
set "REMOTE_HASH="
for /f "usebackq delims=" %%a in (`git rev-parse HEAD 2^>nul`) do set "LOCAL_HASH=%%a"
for /f "usebackq delims=" %%a in (`git rev-parse origin/main 2^>nul`) do set "REMOTE_HASH=%%a"

set "STATUS=??"
if "%LOCAL_HASH%"=="%REMOTE_HASH%" set "STATUS=BIR XIL (sinxron)"
if not "%LOCAL_HASH%"=="%REMOTE_HASH%" set "STATUS=FARQ BOR"

cls
echo.
echo ==========================================
echo    %REPO_NAME% - GitHub Sync
echo ==========================================
echo.
echo   Bu kompyuter (LOCAL) : %LAST_LOCAL%
echo   GitHub (REMOTE)      : %LAST_REMOTE%
echo   Holat                : %STATUS%
echo ==========================================
echo.
echo   1.  YUBORISH (oddiy)         - Kompyuter ^=^=^> GitHub
echo   2.  QABUL QILISH             - GitHub ^=^=^> Kompyuter
echo   3.  FORCE YUBORISH           - GitHub ni o'chirib local kodni yuborish
echo   4.  Farqni ko'rish (DIFF)    - Local va Remote farqi
echo   5.  Loyiha almashtirish
echo   0.  Chiqish
echo.
set /p T="Tanlang (1 / 2 / 3 / 4 / 5 / 0): "

if "%T%"=="1" goto PUSH
if "%T%"=="2" goto PULL
if "%T%"=="3" goto FORCEPUSH
if "%T%"=="4" goto DIFF
if "%T%"=="5" goto REPO_MENU
if "%T%"=="0" exit
goto MENU

:PUSH
cd /d "%REPO_PATH%"
echo.
set /p MSG="Sarlavha yozing: "
if "%MSG%"=="" goto PUSH_EMPTY
echo.
echo === Local o'zgarishlarni saqlash ===
git add .
git commit -m "%MSG%"
echo.
echo === Push qilish (pull QILMAYDI) ===
git push origin main
if errorlevel 1 goto PUSH_REJECTED
echo.
echo   OK - Yuborildi!
pause
goto MENU

:PUSH_EMPTY
echo Sarlavha bosh!
pause
goto MENU

:PUSH_REJECTED
echo.
echo ==========================================
echo   XATO: GitHub sizning local'dan oldinda
echo ==========================================
echo.
echo   Sabab: GitHub'da yangiroq commit bor (boshqa kompyuterdan).
echo.
echo   Tanlovingiz:
echo   ------------------------------------
echo   1.  GitHub kodini olib, keyin push (xavfsiz - merge bo'ladi)
echo   2.  FORCE PUSH (GitHub'ni o'chirib mening kodimni yuboraman)
echo   0.  Bekor qilish
echo.
set /p X="Tanlang (1 / 2 / 0): "
if "%X%"=="1" goto PUSH_PULL_THEN_PUSH
if "%X%"=="2" goto FORCEPUSH_DO
goto MENU

:PUSH_PULL_THEN_PUSH
echo.
echo === GitHub'dan olish (merge) ===
git pull origin main --no-rebase
if errorlevel 1 goto MERGE_CONFLICT
git push origin main
if errorlevel 1 goto PUSH_FAIL_AGAIN
echo.
echo   OK - Yuborildi!
pause
goto MENU

:MERGE_CONFLICT
echo.
echo   *** MERGE KONFLIKTI ***
echo   Qo'lda hal qilish kerak. Quyidagilarni bajaring:
echo     1) git status   - konflikt fayllarini ko'ring
echo     2) Fayllarni qo'lda tahrirlang
echo     3) git add .
echo     4) git commit
echo     5) git push origin main
echo.
pause
goto MENU

:PUSH_FAIL_AGAIN
echo   XATO! Yana push amalga oshmadi.
pause
goto MENU

:FORCEPUSH
cd /d "%REPO_PATH%"
echo.
echo ==========================================
echo   FORCE PUSH - DIQQAT!
echo ==========================================
echo   Bu GitHub'dagi yangi kodni O'CHIRIB
echo   sizning kompyuteringizdagi kodni yuboradi.
echo.
echo   Boshqa kompyuterda hali push qilinmagan
echo   o'zgarishlar bo'lsa - YO'QOLADI!
echo ==========================================
echo.
set /p MSG="Sarlavha yozing (yoki bosh - faqat push): "
echo.
git add .
if not "%MSG%"=="" git diff --cached --quiet || git commit -m "%MSG%"
:FORCEPUSH_DO
echo === FORCE PUSH bajarilmoqda ===
git push origin main --force-with-lease
if errorlevel 1 goto FORCE_FAIL
echo.
echo   OK - Force push muvaffaqiyatli!
pause
goto MENU

:FORCE_FAIL
echo   XATO! Force push amalga oshmadi.
pause
goto MENU

:DIFF
cd /d "%REPO_PATH%"
echo.
echo === LOCAL va REMOTE farqi (qaysi fayllar farq qiladi) ===
git fetch origin main >nul 2>&1
git diff --stat HEAD origin/main
echo.
echo === Local'da bor, GitHub'da yo'q commit'lar ===
git log origin/main..HEAD --oneline
echo.
echo === GitHub'da bor, Local'da yo'q commit'lar ===
git log HEAD..origin/main --oneline
echo.
pause
goto MENU

:PULL
cd /d "%REPO_PATH%"
echo.
echo === Local holatni tekshirish ===
git status --short
echo.
set /p CONFIRM="Davom etamizmi? (h/y): "
if /i not "%CONFIRM%"=="h" goto MENU
git pull origin main --no-rebase
echo.
if %errorlevel%==0 ( echo   OK - Qabul qilindi! ) else ( echo   XATO! )
pause
goto MENU
