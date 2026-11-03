@echo off
REM ===========================================================================
REM  proxy-farm-9router - launcher Windows 11 (pengganti run.sh)
REM
REM  Klik ganda file ini, atau pakai shortcut "Proxy Farm 9Router" di Desktop.
REM  Tanpa argumen  -> mode auto penuh, sama seperti dulu di Linux.
REM  Dengan argumen -> diteruskan apa adanya ke farm.py, mis:
REM      farm.cmd --recheck-only
REM      farm.cmd --dry-run
REM      farm.cmd --logs
REM      farm.cmd --selftest
REM      farm.cmd --action indonesia
REM ===========================================================================

setlocal EnableExtensions EnableDelayedExpansion

REM RC diinisialisasi di awal. Tanpa ini, jalur keluar dini (Python tidak ada)
REM melompat ke :hold dengan RC kosong, dan `exit /b %RC%` jadi `exit /b` telanjang
REM yang mewarisi ERRORLEVEL 0 -> launcher melaporkan SUKSES setelah gagal.
set "RC=1"

REM Konsol UTF-8 supaya emoji/aksen dari farm.py tidak jadi mojibake.
chcp 65001 >nul 2>&1

REM Jangan biarkan proxy sistem ikut campur: uji exit-IP harus jujur.
set "NO_PROXY=*"
set "no_proxy=*"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

REM httpx + socksio vendored di .pylibs.
set "HERE=%~dp0"
set "PYTHONPATH=%HERE%.pylibs;%PYTHONPATH%"

REM -- Pilih interpreter ------------------------------------------------------
REM `py -3.14` dipin spesifik, bukan `py -3`: di mesin ini `py -3` menunjuk ke
REM build free-threaded python3.14t. Tetapi memilih 3.14 buta juga salah kalau
REM mesin tujuan hanya punya 3.12/3.13 -- py akan keluar 103 dan farm tak jalan.
REM Jadi versinya DIPROBE dulu: pakai yang tersedia paling spesifik.
set "PYRUN="
if not defined PYRUN (
    py -3.14 -c "import sys" >nul 2>&1 && set "PYRUN=py -3.14"
)
if not defined PYRUN (
    py -3 -c "import sys" >nul 2>&1 && set "PYRUN=py -3"
)
if not defined PYRUN (
    where python >nul 2>&1 && set "PYRUN=python"
)

if not defined PYRUN (
    echo.
    echo   [X] Python 3.11+ tidak ditemukan.
    echo       Pasang lewat:  winget install Python.Python.3.12
    echo.
    set "RC=3"
    goto :hold
)

if not exist "%HERE%farm.py" (
    echo   [X] farm.py tidak ada di %HERE%
    set "RC=2"
    goto :hold
)

REM Titik masuk. %* menjaga semua argumen utuh.
!PYRUN! "%HERE%farm.py" %*
set "RC=!ERRORLEVEL!"

echo.
if "!RC!"=="0" (
    echo   [OK] SEMUA BERES! Proxy di 9Router sudah segar dan siap dipakai.
) else (
    echo   [X] Selesai dengan catatan ^(kode !RC!^). Lihat log di atas.
)

:hold
echo.
echo   -- Jendela menutup otomatis dalam 15 detik --
echo   Tekan tombol apa saja untuk menutup sekarang.
timeout /t 15 >nul 2>&1

endlocal & exit /b %RC%
