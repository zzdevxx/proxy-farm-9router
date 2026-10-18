#!/usr/bin/env bash
# proxy-farm-9router — 1-Click Auto Bot
# Klik ganda di Desktop -> langsung auto-farm otomatis (atau tekan 2 untuk recheck saja).

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

# socksio dipasang di .pylibs supaya tak menyentuh Python sistem (PEP 668).
export PYTHONPATH="$PWD/.pylibs${PYTHONPATH:+:$PYTHONPATH}"

C_GRN=$'\033[1;32m'; C_YEL=$'\033[1;33m'; C_RED=$'\033[1;31m'
C_CYN=$'\033[1;36m'; C_RST=$'\033[0m'; C_BLD=$'\033[1m'

clear 2>/dev/null || true
echo "${C_CYN}"
echo "  ╔════════════════════════════════════════════════════════════════╗"
echo "  ║             🌾 PROXY FARM 9ROUTER — AUTO SYNC BOT 🚀           ║"
echo "  ╚════════════════════════════════════════════════════════════════╝"
echo "${C_RST}"

# Jika ada argumen CLI langsung diteruskan (misal ./run.sh --dry-run)
if [ $# -gt 0 ]; then
  python3 farm.py "$@"
  exit $?
fi

echo "  ${C_YEL}⏳ Auto-Farm berjalan otomatis dalam 4 detik...${C_RST}"
echo "     • Tekan ${C_BLD}ENTER${C_RST} / tunggu untuk Farm Penuh (Tarik 37 Sumber + Bersihkan DB)."
echo "     • Tekan ${C_BLD}[2]${C_RST} jika hanya ingin Quick Recheck (Pangkas yang mati saja)."
echo

read -t 4 -n 1 -rp "  Pilihan Anda [1/2]: " choice || choice="1"
echo

if [ "${choice:-1}" = "2" ]; then
  echo "${C_CYN}  ⚡ Menjalankan Quick Recheck DB 9Router...${C_RST}"
  echo "     • Menguji ulang seluruh proxy di database 9Router"
  echo "     • Memangkas proxy yang sudah mati"
  echo "  ────────────────────────────────────────────────────────────────"
  echo
  python3 verify_9router.py
  status=$?
else
  echo "${C_CYN}  🚀 Menjalankan Auto-Farm Penuh...${C_RST}"
  echo "     • Recheck & pangkas proxy mati dari DB 9Router (strike >= 2)"
  echo "     • Tarik proxy fresh dari 44 sumber global (termasuk pre-checked hourly feeds)"
  echo "     • Uji tunnel HTTPS CONNECT nyata (TLS handshake & anti-leak)"
  echo "     • Suntikkan ratusan proxy fresh ke DB & rapikan urutan"
  echo "     • 50 Relay Cloudflare & Vercel Anda 100% aman (READ-ONLY)"
  echo "  ────────────────────────────────────────────────────────────────"
  echo
  python3 farm.py
  status=$?
fi

echo
echo "  ────────────────────────────────────────────────────────────────"
if [ $status -eq 0 ]; then
  echo "${C_GRN}  ✅ SEMUA BERES! Proxy di 9router sudah segar & aktif.${C_RST}"
else
  echo "${C_RED}  ❌ Selesai dengan catatan (kode $status). Lihat log di atas.${C_RST}"
fi
echo
# Menutup otomatis dalam 15 detik jika tidak disentuh, atau tekan Enter kapan saja
read -t 15 -rp "  [Jendela menutup otomatis dalam 15 detik / Tekan Enter] " _ || echo
