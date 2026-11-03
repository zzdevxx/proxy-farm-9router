# ============================================================================
#  install-shortcut.ps1 — pasang shortcut START di Desktop
#
#  Jalankan sekali setelah repo di-clone di mesin Windows:
#      pwsh -ExecutionPolicy Bypass -File .\install-shortcut.ps1
#
#  Idempoten: menjalankan ulang hanya menimpa .lnk yang sama.
# ============================================================================

[CmdletBinding()]
param(
    [string]$Name = 'START',
    # 'cmd'  -> START.cmd  (paling kompatibel, default)
    # 'ps1'  -> farm.ps1   (PowerShell, punya mode --logs-follow)
    [ValidateSet('cmd', 'ps1')]
    [string]$Launcher = 'cmd'
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop "$Name.lnk"

if ($Launcher -eq 'cmd') {
    $target = Join-Path $repo 'START.cmd'
    $arguments = ''
} else {
    # powershell.exe ada di setiap Windows 11; tak perlu bergantung pada pwsh 7.
    $target = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'farm.ps1')`""
}

foreach ($p in @($target)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host "  [X] Target tidak ada: $p" -ForegroundColor Red
        exit 2
    }
}

try {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $target
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = $repo
    $lnk.Description = 'Proxy Farm 9Router - klik ganda untuk menjalankan auto-farm'
    $lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,17"   # ikon jaringan
    $lnk.WindowStyle = 1
    $lnk.Save()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
} catch {
    Write-Host "  [X] Gagal membuat shortcut: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (Test-Path -LiteralPath $lnkPath) {
    Write-Host "  [OK] Shortcut terpasang: $lnkPath" -ForegroundColor Green
    Write-Host "       Target  : $target" -ForegroundColor DarkGray
    if ($arguments) { Write-Host "       Argumen : $arguments" -ForegroundColor DarkGray }
    Write-Host "       Kerja   : $repo" -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '  Klik ganda ikon itu di Desktop untuk menjalankan auto-farm.' -ForegroundColor Cyan
    exit 0
}

Write-Host '  [X] Shortcut dilaporkan sukses tapi file tidak ada.' -ForegroundColor Red
exit 1
