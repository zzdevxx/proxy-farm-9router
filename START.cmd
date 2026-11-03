@echo off
REM ===========================================================================
REM  START.cmd - tombol start proxy-farm-9router
REM
REM  Ini SATU-SATUNYA titik masuk yang perlu diingat. Tanpa argumen dia
REM  menjalankan SELURUH alur auto-farm dalam satu klik.
REM
REM  Menjalankan farm.cmd dengan argumen apa pun tetap bisa:
REM      START.cmd --selftest        cek kesiapan mesin, tidak sentuh DB
REM      START.cmd --recheck-only    pangkas proxy mati saja (~30 detik)
REM      START.cmd --dry-run         uji semuanya, DB tidak diubah
REM      START.cmd --logs            lihat 50 baris log terakhir
REM      START.cmd --help            daftar semua opsi
REM
REM  TIDAK meneruskan NO_PROXY/PYTHONPATH sendiri: farm.cmd yang mengurus itu,
REM  dan menyalinnya di sini hanya menciptakan dua sumber kebenaran.
REM ===========================================================================

setlocal
set "HERE=%~dp0"

if not exist "%HERE%farm.cmd" (
    echo.
    echo   [X] farm.cmd tidak ada di %HERE%
    echo       START.cmd harus berada di folder yang sama.
    echo.
    pause
    endlocal & exit /b 2
)

REM call (bukan langsung) supaya START.cmd bisa mengembalikan exit code farm.cmd
call "%HERE%farm.cmd" %*
set "RC=%ERRORLEVEL%"

endlocal & exit /b %RC%
