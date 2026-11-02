import ipaddress
import re

_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$"
)


def backup_db(db_path, backup_dir, keep, repo_root):
    """Salin DB (+WAL) sebelum operasi tulis. Rotasi: sisakan `keep` terbaru.

    Menyapu 'pre-run-*' maupun 'pre-farm-*' — folder lama dari versi v1
    tidak boleh tumbuh selamanya.
    """
    import datetime
    import os
    import shutil

    if not os.path.exists(db_path):
        return None
    dest_root = os.path.join(repo_root, backup_dir)
    os.makedirs(dest_root, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(dest_root, f"pre-run-{stamp}")
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(db_path, os.path.join(dest, "data.sqlite"))
    for ext in ("-wal", "-shm"):
        p = db_path + ext
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(dest, f"data.sqlite{ext}"))
    old = sorted(
        d for d in os.listdir(dest_root) if d.startswith(("pre-run-", "pre-farm-"))
    )
    while len(old) > keep:
        shutil.rmtree(os.path.join(dest_root, old.pop(0)), ignore_errors=True)
    return dest


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

