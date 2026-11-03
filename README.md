# 🌾 Proxy Farm 9Router

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Feeds-62%20Sources-purple?style=for-the-badge&logo=github" alt="62 Sources" />
  <img src="https://img.shields.io/badge/Candidate%20Pool-499k%2B-orange?style=for-the-badge" alt="499k Candidates" />
  <img src="https://img.shields.io/badge/Protocols-HTTP%20%7C%20HTTPS%20%7C%20SOCKS5-blueviolet?style=for-the-badge" alt="Protocols" />
  <img src="https://img.shields.io/badge/Platforms-Windows%2011%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows11&logoColor=white" alt="Windows 11 and Linux" />
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

- 🖱️ **Murni 1-Klik di Folder Project:** Klik ganda `START.cmd` di folder project ini. Program langsung bekerja, menampilkan progres rapi, dan menutup otomatis setelah selesai. Tidak perlu shortcut Desktop.
- 🌐 **Koleksi 62 Sumber Global (Termasuk Pre-Checked Feeds):** Mengambil **499.549 kandidat** (297.778 unik) dari repositori terkurasi (dinoz0rg, xyzs996, proxyspace, monosans, geonode, databay, hproxy, dpangestuw, zaeem20, mmpx12, hookzof, murongpig, zevtyardt, b4rc0de, roosterkid, dll).
- 🏷️ **Batch GeoIP & Pelabelan Negara Otomatis:** Otomatis mendeteksi dan memberi label kode negara (`[ID]`, `[SG]`, `[US]`, `[VN]`, `[PH]`) pada nama proxy yang masuk ke 9Router via batch endpoint 100 IP/request.
- ⚡ **Sorting Latensi Tercepat (Fastest on Top):** Proxy aktif diurutkan berdasarkan ping/latensi terendah (ms terkecil di paling atas) agar respon AI di 9Router selalu ngebut.
- 🎯 **Smart Early-Exit:** Otomatis berhenti begitu target proxy hidup tercapai (target 50 IP), memangkas waktu eksekusi hingga 50%.
- 🛡️ **Single-Shot Failover & Sanitasi IP Privat:** Membuang IP lokal/privat (127.0.0.1, 10.x, 192.168.x) di awal dan langsung memutus kandidat yang timeout tanpa buang waktu mencoba endpoint cadangan.
- ⚖️ **Fair Round-Robin Sampling:** Sumber masif (100k+) tidak memonopoli slot kandidat; setiap repo mendapat jatah sampling berimbang.
- 🔒 **Verifikasi HTTPS CONNECT Nyata:** Memvalidasi handshake TLS sungguhan dan memverifikasi respon IP menggunakan parser `ipaddress` murni—menolak 100% halaman CAPTCHA dan error HTML Cloudflare.
- 🛡️ **Triple-Layer Relay Guard:** Relay Vercel dan Cloudflare Worker bawaan Anda (`*.unnesdev.workers.dev`) **100% READ-ONLY** dan terlindungi di 3 lapis sistem (*scope allowlist* ➔ *db query filter* ➔ *pre-commit assertion*).
- 📈 **Uptime & Reliability Scoring:** Melacak riwayat keandalan proxy (`successCount`, `failCount`, `successRate` %) dan tanggal uji terakhir. Proxy dengan tingkat keberhasilan tinggi dan stabil otomatis diprioritaskan di baris teratas rotasi 9Router.
- 🎛️ **Filter Protokol Khusus:** Dukungan flag CLI `--protocol {all,http,https,socks5}` untuk menyaring dan menguji hanya protokol yang Anda inginkan (misal hanya HTTP/HTTPS murni).
- 📝 **Sistem Logging Terstruktur & Berotasi:** Log eksekusi otomatis disimpan ke `logs/farm.log` (rotasi 5 MB, simpan 5 cadangan) dengan stempel ISO presisi milidetik, level log bertingkat (DEBUG/INFO/WARN/ERROR), dan penanganan crash otomatis (*uncaught exception hook*). Periksa riwayat log kapan saja via `farm.cmd --logs`, `farm.ps1 --logs-follow` (Windows), atau `./run.sh --logs` (Linux).
- 🧹 **One-Strike Grace Reaper:** Proxy yang mati langsung dipangkas pada run ini (`grace_strikes = 1`), supaya DB bersih dari proxy zombie.
- 📊 **Sorting Rapi:** Menjaga urutan tampilan dashboard 9Router tetap teratur: `Custom HTTP/SOCKS5` (teratas) ➔ `Vercel` ➔ `Cloudflare`.

---

## 🏗️ Arsitektur & Alur Kerja

```text
[Double-Click Shortcut "START"]
          │
          ▼
   [Windows] farm.cmd ─── chcp 65001 · PYTHONPATH=.pylibs · NO_PROXY=*
   [Linux]   run.sh   ─── export PYTHONPATH=.pylibs
          │
          ▼
   [0. Auto-Backup]  ─── Salin data.sqlite ke backups/pre-run-* (auto-rotate 10)
          │
          ▼
   [1. Fetch 62 Feeds] ── Tarik ~500k kandidat ➔ Round-robin ➔ Dedup ➔ 15k kandidat fresh
          │
          ▼
   [2. Recheck DB]   ─── Uji proxy custom lama di 9Router dengan HTTPS CONNECT
          │
          ▼
   [3. Grace Reaper] ─── Hapus proxy mati yang gagal pada run ini (grace_strikes = 1)
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

### Dua mesin, satu repo

| | Windows 11 (Acer Swift 3) — utama | Linux Mint (ASUS X407MA) — cadangan |
|---|---|---|
| Launcher | `START.cmd` / `farm.cmd` / `farm.ps1` (di dalam folder project) | `run.sh` |
| Python | 3.14.7 di `C:\Program Files\Python314` | `python3` sistem |
| DB 9Router | `%APPDATA%\9router\db\data.sqlite` | `~/.9router/db/data.sqlite` |
| Shell | PowerShell 5.1+ / cmd | bash |
| Log | `farm.ps1 --logs-follow` | `./run.sh --logs-follow` |

`config.toml` dan `sources.json` identik di kedua mesin — resolusi path DB
otomatis. Tidak ada berkas yang perlu disunting saat berpindah mesin.

---

## 📦 Instalasi & Penggunaan

### 1. Kloning Repositori
```bash
git clone https://gitlab.com/zzdevxx/proxy-farm-9router.git
cd proxy-farm-9router
```

### 2. Tidak perlu `pip install`

Seluruh dependensi (`httpx`, `httpcore`, `h11`, `anyio`, `sniffio`, `idna`,
`certifi`, `socksio`) sudah di-vendor ke `.pylibs/` di dalam repo. Launcher
menambahkan folder itu ke `PYTHONPATH`, jadi repo jalan tanpa menyentuh
site-packages Python sistem maupun user-site.

Verifikasi kesiapan mesin kapan saja:
```bash
farm.cmd --selftest        # Windows
python farm.py --selftest  # lintas platform
```

**Persyaratan:** **Python 3.11 atau lebih baru** (batas bawah dari `tomllib`
di pustaka standar) dan **tidak ada** paket yang perlu dipasang. Launcher
Windows mencoba `py -3.14` lalu `py -3` lalu `python` di `PATH`, sehingga
Python 3.11/3.12/3.13 juga jalan. `--selftest` adalah cara tercepat untuk tahu
versi mana yang terpakai.

> Satu catatan Windows: `py -3` di mesin ini menunjuk build *free-threaded*
> (`python3.14t`), yang belum layak untuk beban jaringan ini. Karena itu
> launcher memprobe `py -3.14` lebih dulu, bukan langsung `py -3`.

### 3. Jalankan

**Windows 11 (Acer) — 1 klik dari dalam folder project:**

Klik ganda `START.cmd` di folder project ini (`D:\ANDREAS\proxy-farm-9router`). Jendela menampilkan progres dan menutup sendiri dalam 15 detik. Tidak ada shortcut Desktop.

`START.cmd` adalah satu-satunya titik masuk yang perlu diingat: tanpa argumen
dia menjalankan seluruh alur auto-farm, dan dengan argumen dia meneruskannya
apa adanya ke `farm.cmd`:

```bat
START.cmd                       :: auto-farm penuh (klik ganda juga begini)
START.cmd --selftest            :: cek kesiapan mesin, tidak menyentuh DB
START.cmd --recheck-only        :: pangkas proxy mati saja, ~30 detik
START.cmd --logs                :: 50 baris log terakhir
```

**Windows 11 — lewat terminal:**
```bat
farm.cmd                              :: auto penuh, perilaku default
farm.cmd --selftest                   :: cek kesiapan lingkungan, tidak sentuh DB
farm.cmd --recheck-only               :: ~30 detik, tanpa unduh sumber baru
farm.cmd --dry-run                    :: uji semuanya, DB tidak diubah
farm.cmd --logs                       :: 50 baris log terakhir
farm.cmd --action indonesia           :: fokus IP Indonesia
farm.cmd --action cek                 :: uji semua & hapus yang mati
farm.cmd --action clean --confirm HAPUS
farm.cmd --protocol socks5 --dry-run
```
`farm.ps1` menyediakan hal yang sama plus `--logs-follow` (ikuti log real-time):
```powershell
powershell -ExecutionPolicy Bypass -File .\farm.ps1 --logs-follow
```

**Linux Mint (ASUS, mesin cadangan) — tetap didukung:**
```bash
./run.sh
python3 farm.py --dry-run
```

**Melalui CLI langsung (kedua OS):**
```bash
# Uji kelayakan ketat: TCP -> HTTPS tunnel -> jangkauan API provider AI.
# Memastikan proxy benar-benar bisa menembus openrouter.ai/api/v1/models.
python farm.py --selftest
python verify_9router.py -n 50 --active-only

# Rapikan ulang urutan tampilan di dashboard 9Router (tercepat di atas)
python reorder.py
```

> **Catatan launcher Windows.** `farm.cmd` dan `farm.ps1` melakukan tiga hal
> yang tidak bisa dilakukan `farm.py` sendiri: menyetel konsol ke UTF-8 (tanpa
> itu Code Page 437 merusak emoji dan panah), men-set `PYTHONPATH` ke
> `.pylibs/`, dan menahan jendela 15 detik saat dibuka lewat klik ganda. Kedua
> skrip juga menyetel `NO_PROXY=*` — kalau proxy sistem ikut campur, uji
> exit-IP akan menilai proxy kita "hidup" padahal yang keluar proxy
> perusahaan/ISP, dan pemeriksaan anti-leak jadi tidak bermakna.

### Catatan mode Indonesia

Mode Indonesia menargetkan **IP lokal Indonesia**, biasanya untuk layanan yang membatasi
akses berdasarkan wilayah. Tiga hal yang perlu diketahui:

1. **Label negara dilengkapi lebih dulu.** Baris lama warisan v1 belum punya
   field `country`; tanpa pelabelan, ratusan baris itu akan dianggap bukan
   Indonesia dan ikut dimatikan — padahal sebagiannya justru proxy ID.
2. **Hanya protokol `http`/`https` yang diaktifkan.** Proxy `socks5` dimatikan
   di mode ini. Jumlah proxy ID yang hidup biasanya 20–40 dari ~200 kandidat.
3. **Tidak ada yang dihapus.** Baris non-ID hanya dimatikan (`isActive=0`), jadi
   bisa dinyalakan kembali dengan menjalankan mode auto.

> **Catatan mode uji.** `--dry-run` tidak menulis apa pun ke DB. `--mode tcp` melewati
> tahap uji exit-IP sepenuhnya: kandidat yang lolos TCP langsung disuntik tanpa bukti
> tunnel HTTPS, jadi pakai hanya untuk run cepat. `deep_test_top_n` di `config.toml`
> membatasi berapa kandidat tercepat yang masuk uji mendalam; set `0` untuk menguji semua.

---

## ⚙️ Konfigurasi (`config.toml`)

```toml
[database]
# Default Windows 11. resolve_db_path() memakai ini bila ada, lalu jatuh ke
# %APPDATA%\9router\db\data.sqlite, lalu ~/.9router/db/data.sqlite.
# Satu file ini dipakai di kedua mesin.
path = "%APPDATA%/9router/db/data.sqlite"
backup_dir = "backups"
keep_backups = 3

[logging]
enabled = true
level = "INFO"               # DEBUG, INFO, WARNING, ERROR
dir = "logs"
file = "farm.log"
max_bytes = 5242880          # 5 MB per file
backup_count = 5             # Simpan 5 file cadangan berotasi

[farm]
max_candidates = 15000       # Kandidat per putaran (setelah dedup + sampling)
concurrency = 250            # Koneksi paralel
connect_timeout = 4.0        # Batas waktu TCP connect
exit_ip_endpoints = ["https://api.ipify.org", "https://icanhazip.com"]
deep_test_top_n = 1000       # Batas kandidat yang masuk uji exit-IP (0 = semua)
deep_test_timeout = 5.0      # Batas waktu handshake HTTPS CONNECT
grace_strikes = 1            # Kegagalan sebelum proxy dipangkas dari DB
target_fresh_alive = 50      # Early-exit begitu target proxy hidup baru tercapai (0 = tanpa batas)

[opencode]
validate = true              # Validasi nyata ke model OpenCode
model = "oc/deepseek-v4.1-flash-free"
timeout = 5.0
max_verified = 20            # Berhenti setelah 20 proxy lolos

[test]
mode = "deep"                # deep = TCP + exit-IP, tcp = TCP saja

[scope]
recheck_types = ["http"]     # Hanya tipe http (custom) yang direcheck
prune_types = ["http"]       # Vercel & Cloudflare tidak akan pernah dihapus
only_prune_owned = false     # false = baris v1 warisan (free-*) yang mati ikut dipangkas

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
3. **Backup Otomatis:** Setiap run yang menulis ke DB memicu snapshot SQLite konsisten (SQLite Online Backup API) ke `backups/pre-run-<stempel>/data.sqlite`, dengan retensi `keep_backups = 3`. Prosedur pulih ada di `RESTORE.md`. Run `--dry-run` tidak membuat backup.

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

Proyek ini dilisensikan di bawah [MIT License](LICENSE) © 2026 Andreas ([@zzdevxx](https://github.com/zzdevxx)).
