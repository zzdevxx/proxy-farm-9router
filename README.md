# 🌾 Proxy Farm 9Router

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Feeds-62%20Sources-purple?style=for-the-badge&logo=github" alt="62 Sources" />
  <img src="https://img.shields.io/badge/Candidate%20Pool-750k%2B-orange?style=for-the-badge" alt="750k+ Candidates" />
  <img src="https://img.shields.io/badge/Protocols-HTTP%20%7C%20HTTPS%20%7C%20SOCKS5-blueviolet?style=for-the-badge" alt="Protocols" />
  <img src="https://img.shields.io/badge/Integration-9Router%20Compatible-red?style=for-the-badge" alt="9Router Compatible" />
</p>

<p align="center">
  <b>Automated Public Proxy Harvester, HTTPS CONNECT Verifier, and Zero-Downtime SQLite Injector for <a href="https://github.com/ninerouter/9router">9Router</a>.</b>
</p>

---

## ⚡ Kenapa Proxy Farm 9Router?

9Router menggunakan agen proxy untuk koneksi **outbound** ke upstream AI provider (Google Gemini, OpenAI, OpenRouter, Anthropic, KiloCode). Karena semua endpoint AI berjalan di atas HTTPS, proxy **wajib** mampu melakukan **HTTPS CONNECT tunneling** tanpa merusak enkripsi TLS.

Kebanyakan proxy scraper publik memasukkan ribuan proxy mati atau proxy palsu yang mengembalikan halaman blokir Cloudflare (`error code: 1003`). **Proxy Farm 9Router** memfilter tumpukan tersebut dengan pengujian handshake TLS asli dan langsung menyuntikkan proxy yang lolos ke database SQLite 9Router dalam sekali klik.

---

## 🚀 Fitur Utama

- 🖱️ **Murni 1-Klik di Desktop:** Cukup klik ganda shortcut di Desktop. Program langsung otomatis bekerja detik itu juga, menampilkan progres rapi, dan menutup otomatis setelah selesai.
- 🌐 **Koleksi 62 Sumber Global (Termasuk Pre-Checked Feeds):** Mengambil lebih dari **750.000 kandidat** (350.000+ IP unik) dari repositori terkurasi (dinoz0rg, xyzs996, proxyspace, monosans, geonode, databay, hproxy, dpangestuw, zaeem20, mmpx12, hookzof, murongpig, zevtyardt, b4rc0de, roosterkid, dll).
- 🏷️ **Batch GeoIP & Pelabelan Negara Otomatis:** Otomatis mendeteksi dan memberi label kode negara (`[ID]`, `[SG]`, `[US]`, `[VN]`, `[PH]`) pada nama proxy yang masuk ke 9Router via batch endpoint 100 IP/request.
- ⚡ **Sorting Latensi Tercepat (Fastest on Top):** Proxy aktif diurutkan berdasarkan ping/latensi terendah (ms terkecil di paling atas) agar respon AI di 9Router selalu ngebut.
- 🎯 **Smart Early-Exit:** Otomatis berhenti begitu target proxy hidup tercapai (misal 800 IP), memangkas waktu eksekusi hingga 50%.
- 🛡️ **Single-Shot Failover & Sanitasi IP Privat:** Membuang IP lokal/privat (127.0.0.1, 10.x, 192.168.x) di awal dan langsung memutus kandidat yang timeout tanpa buang waktu mencoba endpoint cadangan.
- ⚖️ **Fair Round-Robin Sampling:** Sumber masif (100k+) tidak memonopoli slot kandidat; setiap repo mendapat jatah sampling berimbang.
- 🔒 **Verifikasi HTTPS CONNECT Nyata:** Memvalidasi handshake TLS sungguhan dan memverifikasi respon IP menggunakan parser `ipaddress` murni—menolak 100% halaman CAPTCHA dan error HTML Cloudflare.
- 🛡️ **Triple-Layer Relay Guard:** Relay Vercel dan Cloudflare Worker bawaan Anda (`*.unnesdev.workers.dev`) **100% READ-ONLY** dan terlindungi di 3 lapis sistem (*scope allowlist* ➔ *db query filter* ➔ *pre-commit assertion*).
- 🧹 **Two-Strike Grace Reaper:** Proxy yang mati diberi kesempatan 2 kali uji berturut-turut sebelum dihapus agar tidak terbuang hanya karena timeout sesaat.
- 📊 **Sorting Rapi:** Menjaga urutan tampilan dashboard 9Router tetap teratur: `Custom HTTP/SOCKS5` (teratas) ➔ `Vercel` ➔ `Cloudflare`.

---

## 🏗️ Arsitektur & Alur Kerja

```text
[Double-Click Shortcut]
          │
          ▼
   [0. Auto-Backup]  ─── Salin data.sqlite ke backups/pre-run-* (auto-rotate 10)
          │
          ▼
   [1. Fetch 62 Feeds] ── Tarik 750k+ kandidat ➔ Round-robin ➔ Dedup ➔ 15k kandidat fresh
          │
          ▼
   [2. Recheck DB]   ─── Uji proxy custom lama di 9Router dengan HTTPS CONNECT
          │
          ▼
   [3. Grace Reaper] ─── Hapus proxy mati yang sudah mengumpulkan 2 strike
          │               ⛔ Relay Vercel & Cloudflare dijamin tidak tersentuh!
          ▼
   [4. Injeksi Fresh]─── Uji kandidat baru (TCP ➔ HTTPS) ➔ HANYA yang hidup masuk ke DB
          │               🎯 Smart Early-Exit begitu target proxy hidup tercapai!
          ▼
   [5. Sort & Verify]─── Rapikan urutan (Fastest on Top ➔ Vercel ➔ Cloudflare) + SQLite integrity check
          │
          ▼
   [6. Finish]       ─── Cetak ringkasan hijau ➔ Terminal auto-close dalam 15 detik
```

---

## 📦 Instalasi & Penggunaan

### 1. Kloning Repositori
```bash
git clone https://gitlab.com/zzdree/proxy-farm-9router.git
cd proxy-farm-9router
```

### 2. Pasang Dependensi
```bash
pip install -r requirements.txt
```
> *Catatan:* Paket `socksio` (untuk dukungan SOCKS5 di `httpx`) sudah disertakan di folder lokal `.pylibs` sehingga tidak merusak environment Python sistem (PEP 668 compliant).

### 3. Jalankan

**Cara Termudah (1 Klik di Desktop Linux/XFCE):**
Klik ganda ikon **Proxy Farm 9Router** di Desktop Anda!

**Melalui Terminal:**
```bash
# Menjalankan auto-sync penuh (recheck, pangkas, ambil baru, inject, rapikan)
./run.sh

# Uji coba tanpa mengubah isi database (Dry Run)
python3 farm.py --dry-run

# Quick recheck & pangkas proxy mati dari DB saja (super cepat ~30 detik)
python3 farm.py --recheck-only

# Rapikan ulang urutan tampilan di dashboard 9Router (tercepat di atas)
python3 reorder.py
```

---

## ⚙️ Konfigurasi (`config.toml`)

```toml
[database]
path = "/home/zzdree/.9router/db/data.sqlite"
backup_dir = "backups"
keep_backups = 10

[farm]
max_candidates = 15000       # Jumlah kandidat yang diambil per putaran
concurrency = 250            # Koneksi paralel untuk kecepatan maksimal
connect_timeout = 4.0        # Batas waktu TCP connect
deep_test_timeout = 5.0      # Batas waktu handshake HTTPS CONNECT
grace_strikes = 2            # Jumlah kegagalan sebelum proxy dihapus
target_fresh_alive = 800     # Smart Early-Exit: stop begitu 800 proxy hidup tercapai (0 = tanpa batas)

[scope]
recheck_types = ["http"]     # Hanya tipe http (custom) yang direcheck
prune_types = ["http"]       # Vercel & Cloudflare tidak akan pernah dihapus
only_prune_owned = true      # Hanya menghapus proxy hasil injeksi bot

[order]
groups = ["http", "vercel", "cloudflare"]
```

---

## 📋 Sumber Proxy yang Didukung (62 Feeds Terkurasi)

| Kategori Sumber | Daftar Feed | Karakteristik |
|---|---|---|
| **⚡ Pre-Checked Hourly Feeds** | `dinoz0rg` (HTTP/SOCKS5), `xyzs996` (HTTP/HTTPS), `elliott` (SOCKS5), `proxyspace` (HTTPS/HTTP/SOCKS5), `zloi-connect` | Diuji berkala per 10–60 menit via CI/CD, hit rate tinggi (>40%) |
| **🌐 High-Frequency Scrapers** | `zaeem20` (HTTP/HTTPS/SOCKS5), `mmpx12` (HTTP/HTTPS/SOCKS5), `sunny9577` (HTTP/All) | Diperbarui setiap 10–60 menit |
| **🏢 Verified Repositories** | `databay-labs` (HTTP/SOCKS5), `hproxy` (HTTP/HTTPS/SOCKS5), `dpangestuw` (SOCKS5), `iplocate` (SOCKS5), `proxy-free` (SOCKS5) | Kurasi multi-protokol terverifikasi |
| **📦 Core Massive Pools** | `monosans` (JSON + raw), `geonode` (API JSON), `proxyscrape` (v2 & v4 API), `proxifly` (HTTP/SOCKS5), `thespeedx` (HTTP/SOCKS5), `hookzof` (SOCKS5), `murongpig` (HTTP/SOCKS5), `zevtyardt` (HTTP/SOCKS5), `ercindedeoglu` (HTTP/HTTPS/SOCKS5), `jetkai` (HTTP/HTTPS/SOCKS5), `b4rc0de` (HTTP/SOCKS5), `hendrikbgr`, `almroot`, `shiftytr`, `vakhov`, `roosterkid`, `clarketm`, `stormsia`, `tuanminpay` | Pasokan ribuan kandidat massal dari berbagai benua |

*Menambah atau menonaktifkan sumber cukup mengubah file `sources.json` tanpa perlu mengubah kode.*

---

## 🔒 Keamanan & Kebijakan Privasi

1. **Pemeriksaan Kebocoran IP (Anti-Leak):** Bot mendeteksi IP publik lokal secara dinamis. Jika ada proxy yang membocorkan IP lokal Anda, proxy tersebut langsung ditolak.
2. **Kerahasiaan Prompt & Kredensial:** Proses pengujian hanya mengontak endpoint status netral (`api.ipify.org` / `icanhazip.com`). Tidak ada token, API key, atau prompt pengguna yang pernah dikirim melalui proxy publik selama pengujian.
3. **Backup Otomatis:** Setiap eksekusi selalu memicu snapshot SQLite ke direktori `backups/`, menjamin database Anda dapat dipulihkan kapan saja.

---

## ⚠️ Disclaimer & Batasan Penggunaan

**Baca sebelum memakai.**

### Untuk apa repo ini

Alat ini mengumpulkan daftar proxy publik yang **sudah tersedia terbuka** di
internet (62 feed publik), menguji apakah proxy tersebut benar-benar bisa
melakukan HTTPS CONNECT, lalu menyuntikkan yang lolos ke database 9Router
milik Anda sendiri. Tidak ada server pihak ketiga yang dipindai, diuji
beban, atau diserang.

### Batasan yang harus dipatuhi

1. **Proxy publik tidak aman untuk data sensitif.** Operator proxy bisa
   melihat metadata koneksi Anda. Jangan pernah mengirim kredensial, token,
   prompt, atau data pribadi melalui proxy publik.

2. **Menggunakan proxy untuk melewati batas layanan (rate limit, kuota,
   geo-restriction) penyedia AI dapat melanggar Terms of Service mereka.**
   Repo ini menyediakan mekanismenya, bukan izinnya. Tanggung jawab mematuhi
   ToS setiap penyedia sepenuhnya ada pada Anda.

3. **Gunakan hanya untuk layanan yang Anda miliki atau yang mengizinkannya.**
   Jangan memakai proxy untuk mengakses sistem tanpa izin.

4. **Tidak ada jaminan kualitas.** Proxy gratis sering mati, lambat, atau
   berbahaya. Alat ini memfilter yang tidak berfungsi, tetapi tidak bisa
   menjamin keamanan operatornya.

### Sikap proyek ini

Repo ini dipublikasikan untuk **pembelajaran** tentang jaringan, TLS, dan
manajemen koneksi — bukan sebagai alat untuk melanggar ketentuan layanan
pihak lain. Penulis tidak bertanggung jawab atas penyalahgunaan.

Kalau Anda tidak yakin apakah penggunaan Anda melanggar ToS suatu layanan,
**jangan pakai alat ini untuk layanan tersebut.**


---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE) © 2026 Andreas ([@zzdree](https://github.com/zzdree)).
