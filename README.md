# 🌾 Proxy Farm 9Router

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Feeds-37%20Sources-purple?style=for-the-badge&logo=github" alt="37 Sources" />
  <img src="https://img.shields.io/badge/Candidate%20Pool-620k%2B-orange?style=for-the-badge" alt="620k+ Candidates" />
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

- 🖱️ **Murni 1-Klik di Desktop (Auto-Run 4 Detik):** Cukup klik ganda shortcut di Desktop. Program langsung otomatis mulai dalam 4 detik (atau tekan `2` untuk quick recheck). Menampilkan progres rapi dan menutup otomatis setelah selesai.
- 🌐 **Koleksi 37 Sumber Global:** Mengambil lebih dari **620.000 kandidat** (338.000+ IP unik) dari repositori terkurasi (monosans, geonode, proxyscrape v2/v4, proxifly, hookzof, murongpig, zevtyardt, b4rc0de, roosterkid, dll).
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
   [1. Fetch 37 Feeds] ── Tarik 620k+ kandidat ➔ Round-robin ➔ Dedup ➔ 15k kandidat fresh
          │
          ▼
   [2. Recheck DB]   ─── Uji proxy custom lama di 9Router dengan HTTPS CONNECT
          │
          ▼
   [3. Grace Reaper] ─── Hapus proxy mati yang sudah mengumpulkan 2 strike
          │               ⛔ Relay Vercel & Cloudflare dijamin tidak tersentuh!
          ▼
   [4. Injeksi Fresh]─── Uji kandidat baru (TCP ➔ HTTPS) ➔ HANYA yang hidup masuk ke DB
          │
          ▼
   [5. Sort & Verify]─── Rapikan urutan (Custom ➔ Vercel ➔ Cloudflare) + SQLite integrity check
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

# Quick recheck & pangkas proxy mati dari DB saja
python3 verify_9router.py

# Rapikan ulang urutan tampilan di dashboard 9Router
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

[scope]
recheck_types = ["http"]     # Hanya tipe http (custom) yang direcheck
prune_types = ["http"]       # Vercel & Cloudflare tidak akan pernah dihapus
only_prune_owned = true      # Hanya menghapus proxy hasil injeksi bot

[order]
groups = ["http", "vercel", "cloudflare"]
```

---

## 📋 Sumber Proxy yang Didukung (26 Feeds)

| ID Feed | Sumber | Protokol |
|---|---|---|
| `monosans` | [monosans/proxy-list](https://github.com/monosans/proxy-list) | HTTP, SOCKS5 (JSON) |
| `geonode` | [geonode API](https://geonode.com/free-proxy-list) | HTTP, SOCKS5 (JSON) |
| `proxyscrape-*` | [proxyscrape v4 API](https://proxyscrape.com) | HTTP, SOCKS5 |
| `proxifly-*` | [proxifly/free-proxy-list](https://github.com/proxifly/free-proxy-list) | HTTP, SOCKS5 |
| `thespeedx-*` | [TheSpeedX/PROXY-List](https://github.com/TheSpeedX/PROXY-List) | HTTP, SOCKS5 |
| `hookzof-socks5` | [hookzof/socks5_list](https://github.com/hookzof/socks5_list) | SOCKS5 |
| `murongpig-*` | [MuRongPIG/Proxy-Master](https://github.com/MuRongPIG/Proxy-Master) | HTTP, SOCKS5 |
| `zevtyardt-*` | [zevtyardt/proxy-list](https://github.com/zevtyardt/proxy-list) | HTTP, SOCKS5 |
| `ercindedeoglu-*` | [ErcinDedeoglu/proxies](https://github.com/ErcinDedeoglu/proxies) | HTTP, HTTPS, SOCKS5 |
| `jetkai-*` | [jetkai/proxy-list](https://github.com/jetkai/proxy-list) | HTTP, HTTPS, SOCKS5 |
| `sunny9577-http` | [sunny9577/proxy-scraper](https://github.com/sunny9577/proxy-scraper) | HTTP |
| `zloi-*` | [zloi-user/hideip.me](https://github.com/zloi-user/hideip.me) | HTTP, SOCKS5 |
| `vakhov-http` | [vakhov/fresh-proxy-list](https://github.com/vakhov/fresh-proxy-list) | HTTP |
| `roosterkid-https`| [roosterkid/openproxylist](https://github.com/roosterkid/openproxylist) | HTTPS |
| `shiftytr-socks5` | [ShiftyTR/Proxy-List](https://github.com/ShiftyTR/Proxy-List) | SOCKS5 |
| `clarketm` | [clarketm/proxy-list](https://github.com/clarketm/proxy-list) | HTTP |

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
internet (26 feed publik), menguji apakah proxy tersebut benar-benar bisa
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
