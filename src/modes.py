"""Mode operasi proxy-farm-9router.

Empat mode dipilih dari menu `run.sh` (atau lewat flag CLI):

  1. auto      — perilaku lama: recheck → pangkas → tarik sumber → inject.
  2. indonesia — fokus IP lokal: label negara yang belum berlabel, matikan
                 yang bukan ID, aktifkan yang ID, lalu tarik proxy ID baru.
  3. cek       — uji semua proxy custom, hapus yang mati (termasuk warisan v1).
  4. clean     — hapus SEMUA proxy custom (type=http) supaya kolam bersih.

Batas yang berlaku di SEMUA mode: baris vercel & cloudflare adalah relay
milik pengguna dan tidak boleh tersentuh. Setiap fungsi di sini menegakkannya
lewat `dbmod.assert_relays_untouched`, bukan hanya mengandalkan filter query.
"""

from __future__ import annotations

import asyncio
import json

from . import db as dbmod
from . import geo as geomod
from . import testers
from .util import now_iso

# Protokol yang boleh diaktifkan di mode Indonesia.
#
# socks5 sengaja TIDAK diikutkan. 74 koneksi antigravity di DB ini membawa
# access token OAuth; proxy publik bisa membaca lalu lintas yang melewatinya.
# Untuk HTTP forwarding, header Authorization terlihat oleh operator proxy —
# jadi memilih http di atas socks5 BUKAN alasan keamanan (keduanya sama-sama
# bisa dibaca operatornya), melainkan karena http adalah protokol yang sudah
# terbukti paling banyak hidup di kolam ID dan paling sedikit masalahnya.
SAFE_PROTOCOLS = {"http", "https"}


def _proto(proxy_url: str) -> str:
    return (proxy_url or "").split("://", 1)[0].lower()


async def _probe_rows(rows, sem, tcp_to: float, deep_to: float, limit: int | None = None):
    """Uji sekumpulan baris DB, kembalikan [(row, verdict)]."""
    async def probe(r):
        async with sem:
            try:
                host, _, port_s = (r["proxyUrl"] or "").rpartition("://")[2].rpartition(":")
                port = int(port_s)
            except (ValueError, AttributeError):
                return r, testers.Verdict(False, reason="url_tak_terbaca")
            tcp = await testers.tcp_probe(host, port, tcp_to)
            if not tcp.alive:
                return r, tcp
            return r, await testers.live_probe(r["proxyUrl"], None, deep_to, None)

    targets = rows[:limit] if limit else rows
    return await asyncio.gather(*[probe(r) for r in targets], return_exceptions=False)


async def mode_indonesia(con, cfg, log=print) -> dict:
    """Mode 2 — siapkan kolam berisi proxy Indonesia saja.

    Urutannya penting: label negara dulu, baru matikan. Tanpa langkah label,
    baris lama yang belum punya field `country` (warisan v1 `free-*`) akan
    dianggap bukan Indonesia dan ikut dimatikan — padahal sebagiannya proxy ID.
    """
    farm_cfg = cfg["farm"]
    before_relay = dbmod.relay_snapshot(con)
    sem = asyncio.Semaphore(farm_cfg.get("concurrency", 250))
    tcp_to = farm_cfg.get("connect_timeout", 4.0)
    deep_to = farm_cfg.get("deep_test_timeout", 5.0)

    rows = [r for r in dbmod.row_view(con) if r["type"] == "http"]
    if not rows:
        return {"mode": "indonesia", "aborted": "tak ada proxy custom di DB"}

    # ── a) lengkapi label negara yang belum ada ──────────────────────────
    belum = [r for r in rows if not (r["data"] or {}).get("country")]
    if belum:
        log(f"  [a] {len(belum)} baris belum berlabel negara → deteksi GeoIP...")
        hosts = [r["proxyUrl"].rpartition("://")[2].rpartition(":")[0] for r in belum]
        geo_map = geomod.batch_lookup_geoip(hosts, timeout=10.0)
        mapping = {}
        for r, host in zip(belum, hosts):
            g = geo_map.get(host)
            if g:
                mapping[r["id"]] = g
        n = dbmod.set_country(con, mapping, now_iso())
        log(f"      {n} baris dilabeli; {len(belum) - n} tetap tanpa negara")
        rows = [r for r in dbmod.row_view(con) if r["type"] == "http"]
    else:
        log("  [a] semua baris sudah berlabel negara")

    id_rows = [r for r in rows if (r["data"] or {}).get("country") == "ID"]
    non_id = [r for r in rows if (r["data"] or {}).get("country") != "ID"]
    log(f"      kolam: {len(id_rows)} baris ID · {len(non_id)} baris non-ID")

    # ── b) uji proxy ID, matikan yang mati ───────────────────────────────
    log(f"  [b] menguji {len(id_rows)} proxy ID...")
    hasil = await _probe_rows(id_rows, sem, tcp_to, deep_to)
    hidup_proto: dict[str, int] = {}
    hidup_dipakai, hidup_proto_lain, mati = [], [], []
    for r, v in hasil:
        p = _proto(r["proxyUrl"])
        if not v.alive:
            mati.append(r)
            continue
        hidup_proto[p] = hidup_proto.get(p, 0) + 1
        (hidup_dipakai if p in SAFE_PROTOCOLS else hidup_proto_lain).append(r)
    log(f"      hidup: {sum(hidup_proto.values())} {hidup_proto}")
    log(f"      → dipakai (protokol {sorted(SAFE_PROTOCOLS)}): {len(hidup_dipakai)}"
        + (f" · dimatikan karena protokol tidak dipakai mode ini: {len(hidup_proto_lain)}"
           if hidup_proto_lain else ""))

    # ── c) nyalakan ID yang lolos, matikan sisanya ───────────────────────
    n_on = dbmod.set_active(con, [r["id"] for r in hidup_dipakai], True, now_iso())
    n_off_id = dbmod.set_active(
        con, [r["id"] for r in mati + hidup_proto_lain], False, now_iso()
    )
    n_off_non = dbmod.set_active(con, [r["id"] for r in non_id], False, now_iso())
    log(f"  [c] diaktifkan: {n_on} · dimatikan: {n_off_id + n_off_non} "
        f"({n_off_id} ID sisanya + {n_off_non} non-ID) — tidak ada yang dihapus")

    # ── d) susun ulang: proxy ID di atas ─────────────────────────────────
    con.execute("BEGIN IMMEDIATE")
    try:
        n_order = dbmod.order_rows(con, cfg["order"]["groups"], top_id="ID")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log(f"  [d] {n_order} baris disusun (ID di atas)")

    dbmod.assert_relays_untouched(before_relay, dbmod.relay_snapshot(con))
    return {
        "mode": "indonesia",
        "dilabeli_baris": len(belum),
        "id_total": len(id_rows),
        "id_hidup": sum(hidup_proto.values()),
        "id_aktif": len(hidup_dipakai),
        "id_mati": len(mati),
        "id_proto_lain": len(hidup_proto_lain),
        "non_id_dimatikan": n_off_non,
        "disusun": n_order,
        "relay_aman": True,
    }


async def mode_cek_bersihkan(con, cfg, log=print) -> dict:
    """Mode 3 — uji semua proxy custom, hapus yang mati.

    Berbeda dari recheck rutin, mode ini melepas penjaga `only_prune_owned`
    supaya baris warisan v1 (`free-*`) yang sudah mati ikut terbersihkan.
    """
    farm_cfg = cfg["farm"]
    before_relay = dbmod.relay_snapshot(con)
    sem = asyncio.Semaphore(farm_cfg.get("concurrency", 250))
    tcp_to = farm_cfg.get("connect_timeout", 4.0)
    deep_to = farm_cfg.get("deep_test_timeout", 5.0)

    rows = [r for r in dbmod.row_view(con) if r["type"] == "http"]
    if not rows:
        return {"mode": "cek", "aborted": "tak ada proxy custom di DB"}
    log(f"  [a] menguji {len(rows)} proxy custom (TCP → HTTPS)...")

    hasil = await _probe_rows(rows, sem, tcp_to, deep_to)
    hidup = [r for r, v in hasil if v.alive]
    mati = [r for r, v in hasil if not v.alive]
    log(f"      hidup: {len(hidup)} · mati: {len(mati)}")

    # Baris yang mati HARUS ditandai lebih dulu. Kalau tidak, status lamanya
    # (mis. "active" dari run sebelumnya) tetap menempel dan pemangkasan akan
    # menganggapnya sehat — itu sebabnya baris mati sempat lolos.
    now = now_iso()
    con.execute("BEGIN IMMEDIATE")
    try:
        for r, v in hasil:
            dbmod.mark_result(con, r["id"], v, is_new_row=False, now=now)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    log(f"  [b] memangkas {len(mati)} baris mati (termasuk warisan v1)...")
    stats = dbmod.prune_ids(con, [r["id"] for r in mati])
    log(f"      dihapus: {len(stats['pruned'])} · ditahan (terikat koneksi): "
        f"{len(stats['skipped_bound'])}")

    con.execute("BEGIN IMMEDIATE")
    try:
        n_order = dbmod.order_rows(con, cfg["order"]["groups"])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    dbmod.assert_relays_untouched(before_relay, dbmod.relay_snapshot(con))
    sisa = [r for r in dbmod.row_view(con) if r["type"] == "http"]
    return {
        "mode": "cek",
        "diuji": len(rows),
        "hidup": len(hidup),
        "dihapus": len(stats["pruned"]),
        "terikat": len(stats["skipped_bound"]),
        "sisa_custom": len(sisa),
        "disusun": n_order,
        "relay_aman": True,
    }


def mode_clean(con, cfg, log=print) -> dict:
    """Mode 4 — hapus SEMUA proxy custom. Relay tidak pernah ikut.

    Fungsi ini TIDAK meminta konfirmasi sendiri: pemanggil (run.sh / farm.py)
    yang wajib meminta pengguna mengetik HAPUS lebih dulu.
    """
    before_relay = dbmod.relay_snapshot(con)
    rows = dbmod.row_view(con)
    akan = [r for r in rows if r["type"] == "http"]
    log(f"  [a] {len(akan)} baris custom (type=http) akan dihapus")

    hasil = dbmod.delete_all_of_types(con, ["http"])

    after_relay = dbmod.relay_snapshot(con)
    dbmod.assert_relays_untouched(before_relay, after_relay)

    sisa = [r for r in dbmod.row_view(con)]
    log(f"  [b] {hasil['deleted']} baris terhapus · tersisa: "
        f"vercel={sum(1 for r in sisa if r['type']=='vercel')} "
        f"cloudflare={sum(1 for r in sisa if r['type']=='cloudflare')}")
    return {
        "mode": "clean",
        "dihapus": hasil["deleted"],
        "vercel": sum(1 for r in sisa if r["type"] == "vercel"),
        "cloudflare": sum(1 for r in sisa if r["type"] == "cloudflare"),
        "relay_aman": True,
    }


# Ambang kapan mode Indonesia dianggap perlu menarik kandidat baru.
ID_RENDAH = 20


def filter_id_candidates(cands, log=print):
    """Saring kandidat hasil fetch: hanya yang berlokasi Indonesia.

    Dicocokkan lewat exit-IP (kalau tersedia) atau host kandidat. Tanpa
    penyaringan ini, mode Indonesia akan mengisi ulang kolam dengan proxy
    luar negeri yang baru saja dimatikan.
    """
    if not cands:
        return []
    hosts = [c.host for c in cands]
    geo_map = geomod.batch_lookup_geoip(hosts, timeout=10.0)
    out = []
    for c in cands:
        g = geo_map.get(c.host) or {}
        if g.get("country_code") == "ID":
            out.append((c, g))
    log(f"  [e] {len(out)} dari {len(cands)} kandidat baru berlokasi Indonesia")
    return out


async def tarik_proxy_id(con, cfg, sources, farm_mod, log=print) -> dict:
    """Tarik kandidat baru, saring yang ID, uji, lalu suntik ke DB.

    Hanya protokol aman yang ikut disuntik, dan hanya kandidat yang benar-benar
    hidup yang masuk. Tujuannya menambah pilihan proxy ID, bukan membanjiri
    kolam — jumlah sumber yang menyasar Indonesia memang sedikit.
    """
    farm_cfg = cfg["farm"]
    before_relay = dbmod.relay_snapshot(con)
    sem = asyncio.Semaphore(farm_cfg.get("concurrency", 250))
    tcp_to = farm_cfg.get("connect_timeout", 4.0)
    deep_to = farm_cfg.get("deep_test_timeout", 5.0)

    cands = await farm_mod.gather(
        sources, farm_cfg.get("max_candidates", 15000),
        farm_cfg.get("concurrency", 250),
    )
    if not cands:
        log("      tidak ada kandidat (semua sumber mati?)")
        return {"kandidat_baru": 0, "id_disuntik": 0}

    dikenal = {r["proxyUrl"] for r in dbmod.row_view(con) if r["proxyUrl"]}
    segar = [c for c in cands
             if c.proxy_url not in dikenal and _proto(c.proxy_url) in SAFE_PROTOCOLS]
    log(f"      {len(segar):,} kandidat baru ber-protokol aman (dari {len(cands):,} total)")
    if not segar:
        return {"kandidat_baru": 0, "id_disuntik": 0}

    id_cands = filter_id_candidates(segar, log=log)
    if not id_cands:
        return {"kandidat_baru": len(segar), "id_disuntik": 0}

    log(f"      menguji {len(id_cands)} kandidat ID...")
    sem2 = asyncio.Semaphore(farm_cfg.get("concurrency", 250))

    async def uji(c):
        async with sem2:
            tcp = await testers.tcp_probe(c.host, c.port, tcp_to)
            if not tcp.alive:
                return c, tcp
            return c, await testers.live_probe(c.proxy_url, None, deep_to, None)

    hasil = await asyncio.gather(*[uji(c) for c, _g in id_cands])
    hidup = []
    for (c, g), (_c2, v) in zip(id_cands, hasil):
        if not v.alive:
            continue
        # stempel negara supaya proxy baru langsung berlabel [ID] di dashboard
        v.country_code = g.get("country_code")
        v.country = g.get("country")
        v.isp = g.get("isp")
        hidup.append((c, v))
    log(f"      {len(hidup)} dari {len(id_cands)} kandidat ID hidup → disuntik")

    if hidup:
        now = now_iso()
        con.execute("BEGIN IMMEDIATE")
        try:
            for c, v in hidup:
                dbmod.insert_new(con, c, v, now)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        con.execute("BEGIN IMMEDIATE")
        try:
            dbmod.order_rows(con, cfg["order"]["groups"], top_id="ID")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    dbmod.assert_relays_untouched(before_relay, dbmod.relay_snapshot(con))
    return {"kandidat_baru": len(segar), "kandidat_id": len(id_cands),
            "id_disuntik": len(hidup)}
