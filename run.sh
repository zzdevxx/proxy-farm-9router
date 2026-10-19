#!/usr/bin/env bash
# proxy-farm-9router — Menu 4 Mode
# Klik ganda di Desktop: langsung jalan mode 1 tanpa tanya (hitung mundur 10 detik),
# atau tekan angka 2/3/4 untuk mode lain.
#
# ⛔ Relay vercel & cloudflare tidak pernah disentuh mode apa pun.

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

# socksio dipasang di .pylibs supaya tak menyentuh Python sistem (PEP 668).
export PYTHONPATH="$PWD/.pylibs${PYTHONPATH:+:$PYTHONPATH}"

C_GRN=$'\033[1;32m'; C_YEL=$'\033[1;33m'; C_RED=$'\033[1;31m'
C_CYN=$'\033[1;36m'; C_RST=$'\033[0m'; C_BLD=$'\033[1m'; C_DIM=$'\033[2m'

banner() {
  clear 2>/dev/null || true
  echo "${C_CYN}"
  echo "  ╔════════════════════════════════════════════════════════════════╗"
  echo "  ║             🌾 PROXY FARM 9ROUTER — AUTO SYNC BOT 🚀           ║"
  echo "  ╚════════════════════════════════════════════════════════════════╝"
  echo "${C_RST}"
}

menu() {
  banner
  echo "  ${C_BLD}Pilih mode:${C_RST}"
  echo
  echo "   ${C_GRN}1${C_RST}) ${C_BLD}Auto penuh${C_RST} ${C_DIM}(default)${C_RST}"
  echo "      Cek proxy 9router → buang yang mati → tarik sumber"
  echo "      → uji → suntik yang hidup → rapikan urutan"
  echo
  echo "   ${C_CYN}2${C_RST}) ${C_BLD}Mode Indonesia${C_RST} ${C_DIM}(IP lokal)${C_RST}"
  echo "      Label negara yang belum berlabel → aktifkan HANYA proxy ID"
  echo "      → matikan sisanya (tidak dihapus) → taruh ID di atas"
  echo "      → tarik proxy ID baru kalau persediaan menipis"
  echo
  echo "   ${C_YEL}3${C_RST}) ${C_BLD}Cek & bersihkan${C_RST}"
  echo "      Uji SEMUA proxy custom → hapus yang mati"
  echo "      ${C_DIM}(termasuk sisa lama free-* yang selama ini ditahan)${C_RST}"
  echo
  echo "   ${C_RED}4${C_RST}) ${C_BLD}Clean total${C_RST}"
  echo "      Hapus SEMUA proxy custom (type=http) — perlu ketik HAPUS"
  echo
  echo "   ${C_DIM}q${C_RST}) Keluar"
  echo
  echo "  ────────────────────────────────────────────────────────────────"
  echo "  ${C_DIM}50 relay Cloudflare & Vercel Anda 100% aman (READ-ONLY)${C_RST}"
  echo
}

pilihan=""
# Klik ganda dari Desktop: otomatis pilih 1 setelah 10 detik tanpa sentuhan.
if [ -t 0 ]; then
  read -t 10 -rp "  Pilih [1/2/3/4/q] — otomatis 1 dalam 10 detik: " pilihan || true
else
  pilihan="1"
fi
pilihan="${pilihan:-1}"

case "$pilihan" in
  1) aksi=auto;      judul="AUTO PENUH" ;;
  2) aksi=indonesia; judul="MODE INDONESIA" ;;
  3) aksi=cek;       judul="CEK & BERSIHKAN" ;;
  4) aksi=clean;     judul="CLEAN TOTAL" ;;
  q|Q) echo "  Dibatalkan."; exit 0 ;;
  *) echo "  ${C_RED}Pilihan tak dikenal: $pilihan${C_RST}"; sleep 3; exit 1 ;;
esac

banner
echo "  ${C_BLD}▶ MODE: ${judul}${C_RST}"
echo

if [ "$aksi" = "clean" ]; then
  echo "  ${C_RED}${C_BLD}PERINGATAN:${C_RST} seluruh proxy custom (type=http) akan DIHAPUS."
  echo "  Relay vercel & cloudflare tidak tersentuh."
  echo "  Cadangan DB dibuat otomatis sebelum menghapus."
  echo
  read -rp "  Ketik HAPUS untuk melanjutkan: " konfirmasi
  if [ "$konfirmasi" != "HAPUS" ]; then
    echo "  ${C_GRN}Dibatalkan — tidak ada yang dihapus.${C_RST}"; sleep 3; exit 0
  fi
  echo
  python3 farm.py --action clean --confirm HAPUS
  status=$?
else
  python3 farm.py --action "$aksi"
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
