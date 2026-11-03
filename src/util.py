import ipaddress
import re

_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$"
)


def backup_db(db_path, backup_dir, keep, repo_root):
    """Salin DB sebelum operasi tulis. Rotasi: sisakan `keep` cadangan terakhir.

    Memakai SQLite Online Backup API, BUKAN copy2 tiga berkas. Menyalin
    data.sqlite lalu -wal lalu -shm secara terpisah dari database WAL yang
    sedang dibuka 9router bukan snapshot atomik: kalau 9router commit di
    antara dua copy itu, hasil cadangan adalah gambar lama + WAL baru yang
    salt-nya tidak cocok, dan restore-nya diam-diam membuang transaksi
    (atau gagal `database disk image is malformed`). Backup API meminta
    read lock internal dan menulis SATU berkas konsisten tanpa perlu -wal/-shm.
    """
    import datetime
    import os
    import shutil
    import sqlite3

    if not os.path.exists(db_path):
        return None
    dest_root = os.path.join(repo_root, backup_dir)
    os.makedirs(dest_root, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(dest_root, f"pre-run-{stamp}")
    os.makedirs(dest, exist_ok=True)

    out = os.path.join(dest, "data.sqlite")
    src = sqlite3.connect(db_path, timeout=60)
    try:
        dst = sqlite3.connect(out)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    evict_old_backups(dest_root, keep)
    return dest


def evict_old_backups(dest_root, keep):
    """Buang cadangan tertua hingga tersisa `keep`.

    Diurutkan berdasar waktu modifikasi, bukan nama. Sort leksikografik atas
    nama folder salah saat dua awalan hidup berdampingan: "pre-farm-..." selalu
    terurut sebelum "pre-run-..." apa pun stempelnya, sehingga cadangan dari v1
    (yang paling tua) terbuang duluan sementara cadangan terbaru ikut terbuang
    belakangan -- kebalik dari yang diinginkan.
    """
    import os
    import shutil

    if not os.path.isdir(dest_root):
        return
    cands = [
        d for d in os.listdir(dest_root)
        if d.startswith(("pre-run-", "pre-farm-"))
        and os.path.isdir(os.path.join(dest_root, d))
    ]
    cands.sort(key=lambda d: os.path.getmtime(os.path.join(dest_root, d)))
    while len(cands) > keep:
        shutil.rmtree(os.path.join(dest_root, cands.pop(0)), ignore_errors=True)


def parse_endpoint(token):
    """Terima 'host:port'. Balikkan (host, port) atau None.

    Data proxy publik tidak dipercaya: suatu baris yang lolos regex
    belum tentu host yang sah, jadi IP divalidasi dengan ipaddress
    dan nama host dengan pola DNS standar.
    """
    if not isinstance(token, str):
        return None
    token = token.strip()
    parts = token.split(":")
    if len(parts) < 2:
        return None
    host, port_s = parts[0], parts[1]
    if not port_s.isdigit():
        return None
    port = int(port_s)
    if not 1 <= port <= 65535:
        return None
    if not host:
        return None
    if _IPV4.match(host):
        try:
            ip_obj = ipaddress.IPv4Address(host)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_reserved
                or ip_obj.is_multicast
                or ip_obj.is_link_local
            ):
                return None
        except ValueError:
            return None
        return host, port
    if _HOSTNAME.match(host):
        return host.lower(), port
    return None


def now_iso():
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def human(n):
    return f"{n:,}".replace(",", ".")


def get_local_ip() -> str | None:
    """Deteksi IP publik/keluar mesin secara dinamis tanpa hardcode."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def resolve_db_path(raw_path: str | None = None) -> str:
    """Resolve 9router data.sqlite path across Windows and Linux."""
    import os
    if raw_path:
        expanded = os.path.expandvars(os.path.expanduser(raw_path))
        if os.path.exists(expanded):
            return expanded
    appdata = os.environ.get("APPDATA")
    if appdata:
        win_db = os.path.join(appdata, "9router", "db", "data.sqlite")
        if os.path.exists(win_db):
            return win_db
    home_db = os.path.expanduser("~/.9router/db/data.sqlite")
    if os.path.exists(home_db):
        return home_db
    return raw_path or home_db

