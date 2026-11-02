#!/usr/bin/env bash
# proxy-farm-9router — Murni 1-Klik Auto Bot
# Klik ganda di Desktop -> Langsung jalan penuh tanpa tanya:
#   1. Recheck DB: Uji proxy lama, kalau tak bisa dipakai di OpenCode -> DIBUANG
#   2. Harvest 62 Feeds: Tarik kandidat fresh (pool 750k+)
#   3. Uji Nyata: TCP -> HTTPS CONNECT -> OpenCode deepseek reachability
#   4. Suntik hanya yang lolos & urutkan tercepat di atas
#   5. Vercel & Cloudflare 100% READ-ONLY
#
# ⛔ Relay vercel & cloudflare tidak pernah disentuh mode apa pun.

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

# socksio dipasang di .pylibs supaya tak menyentuh Python sistem (PEP 668).
export PYTHONPATH="$PWD/.pylibs${PYTHONPATH:+:$PYTHONPATH}"

C_GRN=$'\033[1;32m'; C_YEL=$'\033[1;33m'; C_RED=$'\033[1;31m'
C_CYN=$'\033[1;36m'; C_RST=$'\033[0m'; C_BLD=$'\033[1m'; C_DIM=$'\033[2m'

# ── Mode Inspeksi Cepat: Baca Log ────────────────────────────────
if [ "${1:-}" = "--logs" ] || [ "${1:-}" = "-l" ]; then
  LOG_FILE="logs/farm.log"
  if [ ! -f "$LOG_FILE" ]; then
    echo "Belum ada file log di $LOG_FILE."
    exit 0
  fi
  echo "${C_CYN}📄 Menampilkan 50 baris log terakhir ($LOG_FILE):${C_RST}"
  echo "────────────────────────────────────────────────────────────────"
  tail -n 50 "$LOG_FILE"
  echo "────────────────────────────────────────────────────────────────"
  exit 0
fi

if [ "${1:-}" = "--logs-follow" ] || [ "${1:-}" = "-f" ]; then
  LOG_FILE="logs/farm.log"
  if [ ! -f "$LOG_FILE" ]; then
    echo "Belum ada file log di $LOG_FILE."
    exit 0
  fi
  echo "${C_CYN}👀 Mengikuti live log ($LOG_FILE) — Tekan Ctrl+C untuk keluar:${C_RST}"
  tail -f "$LOG_FILE"
  exit 0
fi

clear 2>/dev/null || true
echo "${C_CYN}"
echo "  ╔════════════════════════════════════════════════════════════════╗"
echo "  ║             🌾 PROXY FARM 9ROUTER — 1-KLIK AUTO BOT 🚀         ║"
echo "  ╚════════════════════════════════════════════════════════════════╝"
echo "${C_RST}"
echo "  🚀 Menjalankan Auto-Farm Penuh untuk OpenCode..."
echo "     • Recheck & pangkas proxy mati / diblokir dari DB 9Router"
echo "     • Tarik proxy fresh dari 62 sumber global (pool 750k+)"
echo "     • Uji tunnel HTTPS CONNECT nyata (TLS handshake & anti-leak)"
echo "     • Validasi OpenCode DeepSeek (proxy yang error/403 langsung dibuang)"
echo "     • Deteksi negara batch GeoIP & urutkan latensi tercepat"
echo "     • 50 Relay Cloudflare & Vercel Anda 100% aman (READ-ONLY)"
echo "  ────────────────────────────────────────────────────────────────"
echo

python3 farm.py "$@"
status=$?

echo
echo "  ────────────────────────────────────────────────────────────────"
if [ $status -eq 0 ]; then
  echo "${C_GRN}  ✅ SEMUA BERES! Proxy di 9router sudah segar & siap untuk OpenCode.${C_RST}"
else
  echo "${C_RED}  ❌ Selesai dengan catatan (kode $status). Lihat log di atas.${C_RST}"
fi
echo
# Menutup otomatis dalam 15 detik jika tidak disentuh, atau tekan Enter kapan saja
read -t 15 -rp "  [Jendela menutup otomatis dalam 15 detik / Tekan Enter] " _ || echo
