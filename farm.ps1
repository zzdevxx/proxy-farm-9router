# -------------------------------------------------------------------------------
#  proxy-farm-9router - launcher PowerShell 7+ (padanan run.sh untuk Windows 11)
#
#  Klik ganda shortcut "Proxy Farm 9Router" di Desktop, atau langsung:
#      pwsh -File .\farm.ps1
#      pwsh -File .\farm.ps1 --recheck-only
#      pwsh -File .\farm.ps1 --logs
#      pwsh -File .\farm.ps1 --logs-follow      # tunggu real-time (Ctrl+C keluar)
#      pwsh -File .\farm.ps1 --action indonesia
#      pwsh -File .\farm.ps1 --dry-run
#
#  Skrip ini SENGAJA tipis: seluruh logika ada di farm.py. Yang dikerjakan di
#  sini hanya hal yang memang milik shell - console encoding, env, resolusi
#  interpreter, dan jendela yang tidak langsung menutup saat klik ganda.
# -------------------------------------------------------------------------------

[CmdletBinding()]
param(
    # JANGAN pakai $Args: itu variabel otomatis PowerShell dan ditolak parser.
    # `--` di depan mencegah PowerShell menelan --help/--dry-run sebagai
    # parameter umum skrip; semuanya harus sampai utuh ke farm.py.
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Rest = @()
)

$ErrorActionPreference = 'Continue'
$repo = $PSScriptRoot

# -- Console UTF-8: tanpa ini, U+2192 dan emoji jadi '?' di Code Page 437. -----
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    Write-Warning "Tidak bisa menyetel console ke UTF-8: $($_.Exception.Message)"
}

# -- Lingkungan uji proxy harus bersih ----------------------------------------
# Proxy sistem akan membuat uji exit-IP menilai proxy kita sebagai "hidup"
# padahal yang keluar adalah proxy perusahaan/ISP. Anti-leak jadi tak bermakna.
$env:NO_PROXY = '*'
$env:no_proxy = '*'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (Join-Path $repo '.pylibs') + [IO.Path]::PathSeparator + $env:PYTHONPATH

# -- Resolusi interpreter: py launcher dulu, lalu python di PATH --------------
# Mengembalikan array argumen siap-splat: @('py','-3.14') atau @('python').
# Versinya DIPROBE, bukan diasumsikan: `py -3.14` disukai karena `py -3` di
# mesin ini menunjuk build free-threaded python3.14t, tetapi mesin tujuan bisa
# saja hanya punya 3.12/3.13 -- memaksa 3.14 di sana langsung gagal.
function Resolve-Python {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($ver in @('-3.14', '-3')) {
            & $py.Source $ver -c 'import sys' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return ,@($py.Source, $ver) }
        }
    }
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p) { return ,@($p.Source) }
    return $null
}

$python = Resolve-Python
if ($null -eq $python) {
    Write-Host ''
    Write-Host '  [X] Python tidak ditemukan.' -ForegroundColor Red
    Write-Host '     Pasang lewat:  winget install Python.Python.3.12' -ForegroundColor Yellow
    Write-Host ''
    if ($Host.Name -eq 'ConsoleHost') {
        Write-Host '  Tekan Enter untuk menutup...' -ForegroundColor DarkGray
        [void](Read-Host)
    }
    exit 2
}

$entry = Join-Path $repo 'farm.py'
if (-not (Test-Path -LiteralPath $entry)) {
    Write-Host "  [X] farm.py tidak ada di $repo" -ForegroundColor Red
    exit 2
}

# -- Keluaran: konsol tidak boleh diam soal error -----------------------------
# $ErrorActionPreference 'Continue' berarti galat non-terminating hanya
# tercetak dan skrip lanjut dengan $LASTEXITCODE yang menyesatkan. Semua
# panggilan di bawah menyetel $LASTEXITCODE sendiri lewat exit code farm.py,
# jadi yang perlu dijaga hanyalah pesan galat tidak hilang.

$logPath = Join-Path $repo 'logs\farm.log'

$first = if ($Rest.Count -gt 0) { $Rest[0] } else { '' }

# -- Mode tail log ditangani DI SINI, bukan diteruskan ke farm.py --------------
# farm.py hanya mengenal --logs. --logs-follow tidak ada di argparse-nya, jadi
# meneruskannya apa adanya menghasilkan usage error + traceback sebelum tail
# dimulai. run.sh menyelesaikan ini dengan exit lebih awal; di sini sama.
$isLogsTail = $first -in @('--logs', '-l')
$isLogsFollow = $first -in @('--logs-follow', '-f')

if ($isLogsTail) {
    if (-not (Test-Path -LiteralPath $logPath)) {
        Write-Host "  Belum ada file log di $logPath" -ForegroundColor Yellow
        exit 0
    }
    Write-Host "  50 baris log terakhir ($logPath):" -ForegroundColor Cyan
    Write-Host ('-' * 66) -ForegroundColor DarkGray
    Get-Content -LiteralPath $logPath -Tail 50 -Encoding utf8
    Write-Host ('-' * 66) -ForegroundColor DarkGray
    exit 0
}

if ($isLogsFollow) {
    if (-not (Test-Path -LiteralPath $logPath)) {
        Write-Host "  Belum ada file log di $logPath" -ForegroundColor Yellow
        exit 0
    }
    Write-Host ''
    Write-Host "  >> Mengikuti live log ($logPath) - Ctrl+C untuk keluar" -ForegroundColor Cyan
    Write-Host ('-' * 66) -ForegroundColor DarkGray
    Get-Content -LiteralPath $logPath -Wait -Tail 20 -Encoding utf8
    Write-Host ''
    Write-Host '  Keluar dari mode follow.' -ForegroundColor DarkGray
    exit 0
}

# Header - hanya untuk run sungguhan.
# Hanya ASCII: PowerShell 5.1 membaca .ps1 tanpa BOM sebagai ANSI (CP1252),
# sehingga kotak/emoji non-ASCII rusak jadi mojibake. Output farm.py sendiri
# tetap bebas memakai emoji karena itu jalur UTF-8 terpisah.
# Clear-Host melempar "handle is invalid" saat keluaran dialihkan ke pipe/file.
$isRealConsole = -not [Console]::IsOutputRedirected -and $Host.Name -eq 'ConsoleHost'
if ($isRealConsole) { Clear-Host }
Write-Host '  ================================================================' -ForegroundColor Cyan
Write-Host '              PROXY FARM 9ROUTER -- AUTO FARM (WINDOWS)' -ForegroundColor Cyan
Write-Host '  ================================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '     - Recheck & pangkas proxy mati / diblokir dari DB 9Router' -ForegroundColor DarkGray
Write-Host '     - Tarik proxy fresh dari 62 sumber global' -ForegroundColor DarkGray
Write-Host '     - Uji tunnel HTTPS CONNECT nyata (TLS handshake & anti-leak)' -ForegroundColor DarkGray
Write-Host '     - Validasi OpenCode DeepSeek (proxy error/403 langsung dibuang)' -ForegroundColor DarkGray
Write-Host '     - Deteksi negara GeoIP batch & urutkan latensi tercepat' -ForegroundColor DarkGray
Write-Host '     - 50 relay Cloudflare & Vercel 100% aman (READ-ONLY)' -ForegroundColor DarkGray
Write-Host ('  ' + ('-' * 64)) -ForegroundColor DarkGray
Write-Host ''

# Tanpa argumen farm.py menjalankan auto-farm PENUH, yang menulis ke DB 9Router.
# PowerShell menelan bendera umumnya sendiri: `-Verbose` dan `-Debug` masuk ke
# $PSBoundParameters, bukan ke $Rest, sehingga $Rest kosong dan skrip akan
# menjalankan run penuh tanpa peringatan. Itu salah ketik yang mengubah DB
# orang. Tolak kalau ada parameter terikat selain $Rest.
$strayParams = @($PSBoundParameters.Keys | Where-Object { $_ -ne 'Rest' })
if ($strayParams.Count -gt 0) {
    Write-Host '  [X] Bendera PowerShell tidak dikenali: ' -ForegroundColor Red -NoNewline
    Write-Host ($strayParams -join ' ') -ForegroundColor Yellow
    Write-Host '      Itu parameter umum PowerShell, bukan opsi farm.py.' -ForegroundColor DarkGray
    Write-Host "      Untuk daftar opsi: powershell -File farm.ps1 --help" -ForegroundColor DarkGray
    exit 2
}

$verb = if ($python.Count -gt 1) { $python[1] } else { $null }
if ($verb) {
    & $python[0] $verb $entry @Rest
} else {
    & $python[0] $entry @Rest
}
# farm.py selalu keluar dengan kode; kalau proses gagal dijalankan sama sekali,
# $LASTEXITCODE bisa masih null dari perintah sebelumnya. Normalisasi ke 1.
$rc = if ($null -eq $LASTEXITCODE) { 1 } else { $LASTEXITCODE }

Write-Host ''
if ($rc -eq 0) {
    Write-Host '  [OK] SEMUA BERES! Proxy di 9Router sudah segar & siap dipakai.' -ForegroundColor Green
} else {
    Write-Host "  [X] Selesai dengan catatan (kode $rc). Lihat log di atas." -ForegroundColor Red
}

# Tahan jendela hanya kalau jendela ini memang dibuat untuk run ini lalu akan
# hilang. Induk 'explorer' = shortcut klik ganda. Induk powershell/pwsh/cmd
# TIDAK dihitung: itu berarti pengguna masih duduk di terminalnya sendiri, dan
# menahan prompt 15 detik di situ hanya mengganggu.
$holdWindow = $false
try {
    $parent = (Get-CimInstance Win32_Process -Filter "ProcessId = $PID").ParentProcessId
    if ($parent) {
        $pname = (Get-Process -Id $parent -ErrorAction SilentlyContinue).ProcessName
        $holdWindow = $pname -eq 'explorer'
    }
} catch { }

if ($holdWindow -and -not [Console]::IsInputRedirected) {
    Write-Host ''
    Write-Host '  -- Jendela menutup otomatis dalam 15 detik / tekan tombol apa saja --' -ForegroundColor DarkGray
    $waited = $false
    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Milliseconds 100
        # KeyAvailable melempar InvalidOperationException saat stdin dialihkan
        # atau tidak ada konsol; IsInputRedirected sudah disaring di atas.
        try {
            if ([Console]::KeyAvailable) {
                [void][Console]::ReadKey($true)
                $waited = $true
                break
            }
        } catch {
            break
        }
    }
    if ($waited) { Write-Host '  Ditutup oleh pengguna.' -ForegroundColor DarkGray }
}

exit $rc
