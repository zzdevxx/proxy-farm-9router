"""Penulis DB 9router — dengan rangkap keamanan.

Aturan main (dari config.toml [scope]):
  * vercel & cloudflare  → read-only, tak pernah disentuh
  * type=http            → boleh recheck / update / prune
  * prune hanya milik tool (baris bertanda importedSource)
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import uuid

# Whitelist resmi 9router: nilai di luar daftar ini dilempar server jadi "http".
TYPES = {"http", "vercel", "cloudflare", "deno", "netlify"}

# Baris provisioning milik tool (di luar "source") yang juga melindungi dirinya.
OWNED_MARK = "importedSource"


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60, isolation_level=None)
    con.execute("PRAGMA busy_timeout=60000")
    return con


def row_view(con) -> list[dict]:
    """Ambil baris proxyPools sebagai dict ter-normalisasi."""
    rows = con.execute(
        "SELECT id, isActive, testStatus, data, updatedAt FROM proxyPools"
    ).fetchall()
    out = []
    for pid, active, status, data, updated in rows:
        try:
            d = json.loads(data)
        except Exception:
            continue
        out.append(
            {
                "id": pid,
                "isActive": bool(active),
                "testStatus": status,
                "type": d.get("type"),
                "proxyUrl": d.get("proxyUrl"),
                "name": d.get("name"),
                "owned": bool(d.get(OWNED_MARK)),
                "data": d,
                "updatedAt": updated,
            }
        )
    return out


def bound_connection_ids(con) -> set[str]:
    """Kumpulkan id proxy yang terikat koneksi provider aktif.

    Dipakai sebagai penjaga: 9router akan menolak hapus baris yang sedang
    dipakai (HTTP 409). Kalau ada baris seperti itu, kita skip hapus dan
    cukup tandai error.
    """
    import json as _json

    bound = set()
    for (data,) in con.execute("SELECT data FROM providerConnections WHERE data IS NOT NULL"):
        try:
            d = _json.loads(data)
        except Exception:
            continue
        psd = d.get("providerSpecificData") or {}
        ppid = psd.get("proxyPoolId")
        if ppid:
            bound.add(ppid)
    return bound


def _iso(ts: datetime.datetime) -> str:
    """Stempel milidetik presisi (dipakai sebagai kunci urutan unik)."""
    return f"{ts.strftime('%Y-%m-%dT%H:%M:%S')}.{ts.microsecond // 1000:03d}Z"


def order_rows(con, groups: list[str], top_id: str | None = None) -> int:
    """Susun ulang sesuai urutan blok di `groups`; blok pertama paling atas.

    9router mengurutkan proxyPools berdasarkan updatedAt menurun. Tiap baris
    diberi stempel unik yang mundur 1 ms supaya urutannya deterministik.
    Baseline-nya diambil dari updatedAt teratas yang sudah ada (bukan jam
    dinding — celah zona waktu pernah merusak urutan sekali, jangan diulang).

    `top_id` = kode negara yang bloknya didahulukan di dalam type=http
    (dipakai mode Indonesia supaya proxy ID tampil paling atas).
    """
    rows = row_view(con)
    if not rows:
        return 0

    by_type: dict[str, list[dict]] = {g: [] for g in groups}
    for r in rows:                      # type di luar groups dibiarkan
        by_type.setdefault(r["type"], [])
    for r in rows:
        if r["type"] in by_type:
            by_type[r["type"]].append(r)

    top = con.execute("SELECT MAX(updatedAt) FROM proxyPools").fetchone()[0]
    base = (
        datetime.datetime.fromisoformat(top.replace("Z", "+00:00"))
        if top
        else datetime.datetime.now(datetime.timezone.utc)
    )
    n = 0
    for g in groups:
        # Saat `top_id` diminta (mode Indonesia), negara jadi kunci PERTAMA
        # supaya blok ID tampil solid di atas — bukan diselipi ratusan baris
        # non-ID yang kebetulan aktif. Di dalam blok itu, yang aktif tetap
        # didahulukan, lalu yang tercepat.
        # Tanpa `top_id`, urutannya tetap seperti semula: aktif dulu → latensi.
        def sort_key(x):
            is_inactive = 0 if x.get("testStatus") == "active" else 1
            d = x.get("data") or {}
            lat = d.get("latencyMs")
            lat_val = lat if (lat is not None and lat > 0) else 999999
            if top_id:
                cc_rank = 0 if d.get("country") == top_id else 1
                return (cc_rank, is_inactive, lat_val, x.get("name") or "")
            return (is_inactive, lat_val, x.get("name") or "")

        for r in sorted(by_type[g], key=sort_key):
            ts = (base - datetime.timedelta(milliseconds=n))
            con.execute(
                "UPDATE proxyPools SET updatedAt=? WHERE id=?", (_iso(ts), r["id"])
            )
            n += 1
    return n


def prune_dead(con, scope: dict, local_ip_ok: bool = False) -> dict:
    """Hapus baris http milik tool yang strike-nya cukup.

    scope:
      prune_types   : list type yang boleh dipangkas
      only_prune_owned : hanya hapus baris bertanda importedSource
      grace_strikes : berapa strike sebelum dibuang
    """
    rows = row_view(con)
    bound = bound_connection_ids(con)
    pruned, skipped_bound, skipped_grace = [], [], []

    cur = con.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        for r in rows:
            if r["type"] not in scope["prune_types"]:
                continue
            if scope.get("only_prune_owned") and not r["owned"]:
                continue
            if r["id"] in bound:
                skipped_bound.append(r)
                continue
            d = r["data"]
            strikes = int(d.get("strikes") or 0)
            # mati pada run ini DITANDAI sementara oleh caller (strikes sudah +1)?
            if strikes < scope["grace_strikes"]:
                skipped_grace.append(r)
                continue
            cur.execute("DELETE FROM proxyPools WHERE id=?", (r["id"],))
            pruned.append({"id": r["id"], "name": r["name"], "url": r["proxyUrl"]})
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise

    return {
        "pruned": pruned,
        "skipped_bound": [r["name"] for r in skipped_bound],
        "skipped_grace": len(skipped_grace),
    }


def set_active(con, ids: list[str], active: bool, now: str) -> int:
    """Nyalakan/matikan baris tertentu tanpa menghapusnya.

    9router memilih proxy dari kolam dengan `isActive` saja, jadi mematikan
    satu baris cukup untuk mengeluarkannya dari peredaran — datanya tetap
    utuh dan bisa dinyalakan kembali kapan saja.

    `testStatus` ikut disinkronkan. Kalau tidak, baris bisa ber-`isActive=0`
    tapi `testStatus='active'`, dan pengurutan akan menganggapnya sehat
    sehingga baris mati tetap muncul di urutan teratas.
    """
    if not ids:
        return 0
    cur = con.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        n = 0
        for pid in ids:
            row = cur.execute(
                "SELECT data, testStatus FROM proxyPools WHERE id=?", (pid,)
            ).fetchone()
            if not row:
                continue
            d = json.loads(row[0])
            status_lama = row[1]
            if active:
                d.pop("disabledAt", None)
                d.pop("disabledReason", None)
                status_baru = "active"
            else:
                d["disabledAt"] = now
                d["disabledReason"] = "dimatikan mode"
                # 'error' dipertahankan supaya alasan kegagalannya tidak hilang;
                # selain itu ditandai 'disabled' agar jelas bukan hasil uji.
                status_baru = status_lama if status_lama == "error" else "disabled"
            cur.execute(
                "UPDATE proxyPools SET isActive=?, testStatus=?, data=json(?) WHERE id=?",
                (1 if active else 0, status_baru, json.dumps(d), pid),
            )
            n += 1
        con.execute("COMMIT")
        return n
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise


def set_country(con, mapping: dict[str, dict], now: str) -> int:
    """Simpan hasil GeoIP ke baris yang belum punya negara.

    Dipakai mode Indonesia: tanpa langkah ini, ratusan baris tanpa label akan
    dianggap 'bukan Indonesia' dan ikut dimatikan, padahal sebagiannya justru
    proxy Indonesia.
    """
    if not mapping:
        return 0
    cur = con.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        n = 0
        for pid, geo in mapping.items():
            row = cur.execute(
                "SELECT data FROM proxyPools WHERE id=?", (pid,)
            ).fetchone()
            if not row:
                continue
            d = json.loads(row[0])
            cc = geo.get("country_code")
            if not cc or cc == "??":
                continue
            d["country"] = cc
            if geo.get("country"):
                d["countryName"] = geo["country"]
            if geo.get("isp") and geo["isp"] != "-":
                d["isp"] = geo["isp"]
            # Nama ikut dilabeli [CC] supaya baris lama yang belum pernah
            # lewat jalur inject tetap terbaca negaranya di dashboard.
            nm = d.get("name") or ""
            if nm and not nm.startswith("["):
                d["name"] = f"[{cc}] {nm}"
            d["geoLabeledAt"] = now
            cur.execute(
                "UPDATE proxyPools SET data=json(?) WHERE id=?", (json.dumps(d), pid)
            )
            n += 1
        con.execute("COMMIT")
        return n
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise


def prune_ids(con, ids: list[str]) -> dict:
    """Hapus baris berdasarkan id, apa pun pemilik dan statusnya.

    Dipakai mode 3: baris sudah diuji dan ditandai mati oleh pemanggil, jadi
    di sini tidak perlu menebak lagi. Baris yang terikat koneksi provider
    tetap ditahan — 9router akan menolak menghapusnya.
    """
    if not ids:
        return {"pruned": [], "skipped_bound": [], "skipped_grace": 0}
    want = set(ids)
    rows = [r for r in row_view(con) if r["id"] in want]
    bound = bound_connection_ids(con)
    pruned, skipped_bound = [], []
    cur = con.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        for r in rows:
            if r["id"] in bound:
                skipped_bound.append(r)
                continue
            cur.execute("DELETE FROM proxyPools WHERE id=?", (r["id"],))
            pruned.append({"id": r["id"], "name": r["name"], "url": r["proxyUrl"]})
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return {
        "pruned": pruned,
        "skipped_bound": [r["name"] for r in skipped_bound],
        "skipped_grace": 0,
    }


def prune_dead_any_owner(con, prune_types: list[str], now: str) -> dict:
    """Hapus baris mati TANPA memandang pemiliknya (mode 3 & 4).

    Berbeda dari prune_dead: penjaga `only_prune_owned` sengaja dilepas supaya
    baris warisan v1 (free-*) yang sudah mati ikut bersih. Baris yang masih
    `active` tidak pernah disentuh.
    """
    rows = row_view(con)
    bound = bound_connection_ids(con)
    pruned, skipped_bound = [], []
    cur = con.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        for r in rows:
            if r["type"] not in prune_types:
                continue
            if r["testStatus"] == "active":
                continue
            if r["id"] in bound:
                skipped_bound.append(r)
                continue
            cur.execute("DELETE FROM proxyPools WHERE id=?", (r["id"],))
            pruned.append({"id": r["id"], "name": r["name"], "url": r["proxyUrl"]})
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return {
        "pruned": pruned,
        "skipped_bound": [r["name"] for r in skipped_bound],
        "skipped_grace": 0,
    }


def delete_all_of_types(con, types: list[str]) -> dict:
    """Hapus SEMUA baris bertipe tertentu (mode 4: bersih total).

    Relay vercel/cloudflare tidak pernah masuk daftar ini — penjaga di
    pemanggil memverifikasi jumlahnya sebelum dan sesudah.
    """
    placeholders = ",".join("?" for _ in types)
    cur = con.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        victims = cur.execute(
            f"SELECT id, data FROM proxyPools WHERE json_extract(data,'$.type')"
            f" IN ({placeholders})",
            types,
        ).fetchall()
        for pid, _d in victims:
            cur.execute("DELETE FROM proxyPools WHERE id=?", (pid,))
        con.execute("COMMIT")
        return {"deleted": len(victims)}
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise


def relay_snapshot(con) -> dict[str, tuple]:
    """Tangkap keadaan baris vercel & cloudflare: (id -> (isActive, type)).

    Stempel `updatedAt` sengaja TIDAK ikut dibandingkan. Mengurutkan ulang
    memang menulis stempel baru ke setiap baris termasuk relay — itu mekanisme
    urutannya, bukan pelanggaran. Yang benar-benar tidak boleh terjadi adalah
    relay ikut terhapus atau termatikan.
    """
    out: dict[str, tuple] = {}
    for r in row_view(con):
        if r["type"] in ("vercel", "cloudflare"):
            out[r["id"]] = (r["isActive"], r["type"])
    return out


def assert_relays_untouched(before: dict[str, tuple], after: dict[str, tuple]) -> None:
    """Gagal keras kalau ada relay yang hilang, bertambah, atau dimatikan."""
    hilang = [i for i in before if i not in after]
    mati = [i for i, st in after.items() if i in before and st[0] != before[i][0]]
    if hilang or mati:
        raise RuntimeError(
            f"RANGKAP MELANGAR: {len(hilang)} relay hilang, "
            f"{len(mati)} relay berubah status aktif — operasi dibatalkan"
        )


def mark_result(con, pid: str, verdict, *, is_new_row: bool, now: str) -> dict:
    """Tulis hasil uji ke baris: testStatus, lastError, lastTestedAt, strikes."""
    d = json.loads(con.execute("SELECT data FROM proxyPools WHERE id=?", (pid,)).fetchone()[0])
    d["lastTestedAt"] = now
    if verdict.alive:
        d.pop("lastError", None)
        d["strikes"] = 0
        if verdict.latency_ms is not None:
            d["latencyMs"] = verdict.latency_ms
        if verdict.exit_ip:
            d["exitIp"] = verdict.exit_ip
        status = "active"
        active = 1
    else:
        d["strikes"] = int(d.get("strikes") or 0) + 1
        d["lastError"] = verdict.reason or "farm: gagal uji"
        status = "error"
        active = 0
    con.execute(
        "UPDATE proxyPools SET isActive=?, testStatus=?, data=json(?) WHERE id=?",
        (active, status, json.dumps(d), pid),
    )
    return {"strikes": d["strikes"], "status": status}


def insert_new(con, cand, verdict, now: str) -> None:
    """Masukkan proxy baru yang lolos uji (dengan label negara bila terdeteksi)."""
    cc = getattr(verdict, "country_code", None)
    c_name = getattr(verdict, "country", None)
    isp = getattr(verdict, "isp", None)

    prefix = f"[{cc}] " if cc and cc != "??" else ""
    payload = {
        "name": f"{prefix}farm-{cand.protocol}-{cand.host}:{cand.port}",
        "proxyUrl": cand.proxy_url,
        "noProxy": "",
        "type": "http",
        "strictProxy": False,
        "importedSource": cand.source,
        "importedProto": cand.protocol,
        "importedAt": now,
        "lastTestedAt": now,
        "strikes": 0,
    }
    if cc and cc != "??":
        payload["country"] = cc
    if c_name and c_name != "Unknown":
        payload["countryName"] = c_name
    if isp and isp != "-":
        payload["isp"] = isp
    if verdict.latency_ms is not None:
        payload["latencyMs"] = verdict.latency_ms
    con.execute(
        "INSERT INTO proxyPools(id, isActive, testStatus, data, createdAt, updatedAt)"
        " VALUES(?,?,?,?,?,?)",
        (
            str(uuid.uuid4()),
            1,
            "active",
            json.dumps(payload),
            now,
            now,
        ),
    )
