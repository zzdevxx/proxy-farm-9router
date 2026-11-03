#!/usr/bin/env python3
"""proxy-farm-9router — bot: farm proxy publik, recheck yang sudah ada, bersihkan yang
mati, dan suntik yang hidup ke DB 9router. Semua dalam satu klik.

Peringatan: proxy publik berarti operatornya bisa membaca lalu lintas yang
melewatinya. Jangan mengarahkannya ke request yang membawa API key provider
atau isi prompt skripsi.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import sys
import time
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# socksio dibutuhkan untuk uji SOCKS sungguhan (httpx tidak menerima scheme
# socks5 tanpanya). Dilepas di .pylibs supaya tak menyentuh Python sistem.
LOCAL_LIBS = os.path.join(HERE, ".pylibs")
if os.path.isdir(LOCAL_LIBS) and LOCAL_LIBS not in sys.path:
    sys.path.insert(0, LOCAL_LIBS)

import tomllib

from src import db as dbmod
from src import fetch as fetch_mod
from src import geo as geomod
from src import get_logger, setup_logging
from src import report as report_mod
from src import testers
from src import util as utilmod


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def human(n) -> str:
    return f"{n:,}".replace(",", ".")


def local_ip() -> str | None:
    """IP keluar mesin ini — dipakai mendeteksi proxy yang membocorkan IP asli."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def selftest(args) -> int:
    """Cek kesiapan lingkungan sebelum farm sungguhan. Tidak menyentuh DB.

    Yang diperiksa hanyalah hal yang paling sering bikin run gagal di mesin
    baru: interpretter terlalu tua, dependensi vendored tak lengkap, DB tak
    ketemu, 9router mati, dan konsol yang tak bisa mencetak UTF-8.
    """
    ok = True
    print("=" * 66)
    print("  SELFTEST — proxy-farm-9router")
    print("=" * 66)

    # 1. Python
    ver = sys.version_info
    py_ok = ver >= (3, 11)  # tomllib
    print(f"   {'ok ' if py_ok else 'X  '} python           {ver.major}.{ver.minor}.{ver.micro} ({sys.executable})")
    ok &= py_ok

    # 2. Dependensi (dari .pylibs, bukan site-packages mesin)
    for mod_name in ("httpx", "httpcore", "socksio"):
        try:
            mod = __import__(mod_name)
            origin = getattr(mod, "__file__", "?")
            vendored = LOCAL_LIBS and origin.startswith(LOCAL_LIBS)
            tag = "vendored" if vendored else "sistem  "
            print(f"   ok  {mod_name:<15} {getattr(mod, '__version__', '?'):<10} [{tag}]")
        except ImportError as exc:
            print(f"   X   {mod_name:<15} TIDAK ADA ({exc})")
            ok = False

    # 3. Config
    try:
        cfg = load_config(os.path.join(HERE, "config.toml"))
        f = cfg.get("farm", {})
        print(f"   ok  config.toml      target={f.get('target_fresh_alive')} "
              f"deep_top_n={f.get('deep_test_top_n')} strikes={f.get('grace_strikes')}")
    except Exception as exc:
        print(f"   X   config.toml      {type(exc).__name__}: {exc}")
        print("=" * 66)
        return 2

    # 4. Database 9router
    db_path = utilmod.resolve_db_path(cfg["database"]["path"])
    if not os.path.exists(db_path):
        print(f"   X   database         TIDAK ADA: {db_path}")
        print("                       Jalankan 9Router sekali dulu agar DB dibuat.")
        ok = False
    else:
        try:
            con = dbmod.connect(db_path)
            rows = dbmod.row_view(con)
            kinds: dict[str, int] = {}
            for r in rows:
                kinds[r["type"]] = kinds.get(r["type"], 0) + 1
            integ = con.execute("PRAGMA integrity_check(1)").fetchone()[0]
            con.close()
            ringkas = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
            print(f"   ok  database         {db_path}")
            print(f"       isi              {ringkas}  (integritas: {integ})")
        except Exception as exc:
            print(f"   X   database         {type(exc).__name__}: {exc}")
            ok = False

    # 5. 9Router gateway
    if testers.is_9router_online():
        key = testers.get_9router_api_key(db_path) if os.path.exists(db_path) else None
        print(f"   ok  9router          online di localhost:20128 (api key: {'ada' if key else 'TIDAK ADA'})")
    else:
        print("   --  9router          OFFLINE di localhost:20128")
        print("                       Farm tetap jalan, tetapi validasi OpenCode dilewati.")

    # 6. Konsol UTF-8
    enc = getattr(sys.stdout, "encoding", "?")
    utf8_ok = str(enc).lower().replace("-", "") in ("utf8", "utf8mb4")
    print(f"   {'ok ' if utf8_ok else '-- '} konsol           stdout={enc}")
    if not utf8_ok:
        print("                       Pakai farm.cmd / farm.ps1 agar UTF-8 disetel.")

    # 7. Tulis akses ke folder kerja
    for sub in ("logs", "reports", "backups", "data"):
        d = os.path.join(HERE, sub)
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".selftest")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("x")
            os.remove(probe)
            print(f"   ok  tulis {sub:<10} {d}")
        except Exception as exc:
            print(f"   X   tulis {sub:<10} {type(exc).__name__}: {exc}")
            ok = False

    print("=" * 66)
    print("  SELFTEST LULUS — siap menjalankan farm." if ok else "  SELFTEST GAGAL — perbaiki item bertanda X dulu.")
    print("=" * 66)
    return 0 if ok else 1


def backup_db(db_path: str, backup_dir: str, keep: int) -> str | None:
    """Salin DB (+WAL) sebelum run. Rotasi: sisakan `keep` cadangan terakhir."""
    return utilmod.backup_db(db_path, backup_dir, keep, HERE)


def parse_endpoint(url: str) -> tuple[str, int]:
    _, _, rest = url.partition("://")
    host, _, port = rest.rpartition(":")
    return host, int(port)


def _progress_enabled() -> bool:
    """Bar progres hanya masuk akal di terminal sungguhan.

    Di Windows, menulis "\\r" ke stdout yang dialihkan (pipe/file/Task
    Scheduler) melempar `OSError: [Errno 22] Invalid argument` dan mematikan
    seluruh run di tengah jalan. Diperiksa sekali, bukan per panggilan.
    """
    try:
        if not sys.stdout.isatty():
            return False
        # PYTHONIOENCODING bisa memaksa codec yang tak bisa menulis blok.
        "█".encode(sys.stdout.encoding or "utf-8")
        return True
    except (OSError, ValueError, LookupError, AttributeError):
        return False


# Dievaluasi sekali saat import; progress() menurunkannya jadi False kalau
# terminal hilang di tengah run.
_PROGRESS_ON = _progress_enabled()


def progress(done: int, total: int, extra: str = "") -> None:
    if total <= 0:
        return
    if not _PROGRESS_ON:
        # Tanpa terminal: cetak tonggak saja, jangan bar yang menimpa diri.
        if done == total or done % 1000 == 0:
            print(f"  {done:,}/{total:,} {extra}".rstrip(), flush=True)
        return
    filled = int(28 * done / total)
    bar = "█" * filled + "░" * (28 - filled)
    try:
        print(f"\r  {bar} {done:,}/{total:,} {extra}", end="", flush=True)
        if done >= total:
            print()
    except OSError:
        # Terminal hilang di tengah run (jendela ditutup). Jangan bunuh farm.
        globals()["_PROGRESS_ON"] = False


async def run(args) -> int:
    global _PROGRESS_ON
    _PROGRESS_ON = _progress_enabled()
    cfg = load_config(os.path.join(HERE, "config.toml"))

    if getattr(args, "logs", False):
        log_dir = cfg.get("logging", {}).get("dir", "logs")
        log_name = getattr(args, "log_file", None) or cfg.get("logging", {}).get("file", "farm.log")
        log_path = os.path.join(HERE, log_dir, log_name)
        if not os.path.exists(log_path):
            print(f"Belum ada file log di: {log_path}")
            return 0
        print(f"📄 Menampilkan 50 baris log terakhir ({log_path}):")
        print("─" * 66)
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-50:]:
                print(line, end="")
        print("─" * 66)
        return 0

    logger = setup_logging(
        cfg=cfg,
        level=getattr(args, "log_level", None),
        log_file=getattr(args, "log_file", None),
        repo_root=HERE,
    )

    db_path = utilmod.resolve_db_path(cfg["database"]["path"])
    if not os.path.exists(db_path):
        logger.error(f"DB tidak ditemukan: {db_path}")
        return 2

    scope = cfg["scope"]
    farm_cfg = cfg["farm"]
    mode = args.mode or cfg.get("test", {}).get("mode", "deep")

    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        sources = json.load(f)["sources"]
    sources = [s for s in sources if s.get("enabled", True)]
    if args.limit_sources:
        keep = set(args.limit_sources.split(","))
        sources = [s for s in sources if s["id"] in keep]

    logger.info("=" * 66)
    logger.info(f"  proxy-farm-9router  |  {len(sources)} sumber  |  mode: {mode}")
    logger.info(f"  aman: {', '.join(scope['recheck_types'])} boleh disentuh; "
                f"vercel/cloudflare READ-ONLY")
    logger.info("=" * 66)

    con = dbmod.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    t_start = time.monotonic()
    lip = local_ip()

    try:
        # ── mode khusus: indonesia / cek / clean ─────────────────────────
        action = getattr(args, "action", None) or "auto"
        if action != "auto":
            if action == "clean" and (getattr(args, "confirm", None) or "") != "HAPUS":
                logger.error("  mode clean butuh konfirmasi: tambahkan --confirm HAPUS")
                return 3
            bkp0 = backup_db(db_path, cfg["database"]["backup_dir"],
                             cfg["database"]["keep_backups"])
            if bkp0:
                logger.info(f"\n  [0] cadangan DB -> {bkp0}")
            from src import modes as modes_mod
            if action == "indonesia":
                hasil = await modes_mod.mode_indonesia(con, cfg, log=logger.info)
                if hasil.get("id_aktif", 0) < modes_mod.ID_RENDAH:
                    logger.info(f"\n  [e] proxy ID aktif cuma {hasil.get('id_aktif')} — "
                                f"menarik kandidat ID baru dari {len(sources)} sumber...")
                    tambah = await modes_mod.tarik_proxy_id(
                        con, cfg, sources, farm_mod=fetch_mod, log=logger.info
                    )
                    hasil.update(tambah)
            elif action == "cek":
                hasil = await modes_mod.mode_cek_bersihkan(con, cfg, log=logger.info)
            else:
                hasil = modes_mod.mode_clean(con, cfg, log=logger.info)
            logger.info("\n" + "=" * 66)
            logger.info(f"  SELESAI — mode {action}")
            logger.info("=" * 66)
            for k, v in hasil.items():
                logger.info(f"   {k:20s} {v}")
            integ = con.execute("PRAGMA integrity_check(1)").fetchone()[0]
            logger.info(f"   {'integrity':20s} {integ}")
            return 0 if integ == "ok" else 1

        # ── 1) backup + snapshot kondisi DB ───────────────────────────────
        bkp = backup_db(db_path, cfg["database"]["backup_dir"], cfg["database"]["keep_backups"])
        if bkp:
            logger.info(f"\n  [0] cadangan DB -> {bkp}")

        before = dbmod.row_view(con)
        by_type_before: dict[str, int] = {}
        for r in before:
            by_type_before[r["type"]] = by_type_before.get(r["type"], 0) + 1
        logger.info("  [0] kondisi DB sekarang: " +
                    ", ".join(f"{k}={v}" for k, v in sorted(by_type_before.items())))

        # ── 2) fetch kandidat baru + dedup ────────────────────────────────
        if args.recheck_only:
            logger.info("\n  [1] --recheck-only: lewati unduhan sumber baru")
            cands = []
            fresh = []
        else:
            cands = await fetch_mod.gather(
                sources, farm_cfg.get("max_candidates", 8000), farm_cfg.get("concurrency", 250)
            )
            if not cands:
                logger.error("tidak ada kandidat — semua sumber mati?")
                return 1

            # kandidat yang belum ada di DB (berdasarkan proxyUrl)
            known_urls = {r["proxyUrl"] for r in before if r["proxyUrl"]}
            fresh = [c for c in cands if c.proxy_url not in known_urls]
            logger.info(f"  [2b] {len(fresh)} kandidat benar-benar baru (sisanya sudah ada di DB)")

        # ── 3) RECHECK baris lama (hanya type dalam scope.recheck_types) ──
        recheck_types = set(scope["recheck_types"])
        old_rows = [r for r in before if r["type"] in recheck_types]

        proto_filter = getattr(args, "protocol", "all")
        if proto_filter and proto_filter != "all":
            proto_val = proto_filter.lower()
            if fresh:
                fresh = [c for c in fresh if c.protocol == proto_val]
                logger.info(f"  [2c] filter protokol '{proto_val}': tersisa {len(fresh)} kandidat baru")
            old_rows = [
                r for r in old_rows
                if (r.get("data") or {}).get("importedProto") == proto_val
                or (r.get("proxyUrl") or "").startswith(f"{proto_val}://")
            ]
            logger.info(f"  [3-proto] filter recheck protokol '{proto_val}': tersisa {len(old_rows)} baris lama")

        logger.info(f"\n  [3] RECHECK {human(len(old_rows))} baris lama "
                    f"(type={sorted(recheck_types)})")

        sem = asyncio.Semaphore(farm_cfg.get("concurrency", 250))
        tcp_to = farm_cfg.get("connect_timeout", 4.0)
        deep_to = farm_cfg.get("deep_test_timeout", 6.0)
        endpoints = farm_cfg.get(
            "exit_ip_endpoints", ["https://api.ipify.org", "https://icanhazip.com"]
        )
        deep_n = farm_cfg.get("deep_test_top_n", 800)

        async def probe_row(r):
            async with sem:
                try:
                    host, port = parse_endpoint(r["proxyUrl"])
                except Exception:
                    return r, testers.Verdict(False, reason="url_tak_terbaca")
                tcp = await testers.tcp_probe(host, port, tcp_to)
                if not tcp.alive:
                    return r, tcp
                return r, await testers.live_probe(r["proxyUrl"], endpoints, deep_to, lip)

        results = []
        done = 0
        total = len(old_rows)
        alive_old = 0
        for fut in asyncio.as_completed([probe_row(r) for r in old_rows]):
            row, verdict = await fut
            results.append((row, verdict))
            if verdict.alive:
                alive_old += 1
            done += 1
            if done % 250 == 0 or done == total:
                progress(done, total, f"hidup={alive_old}")
        dead_old = total - alive_old
        logger.info(f"  [3b] recheck: {alive_old} hidup / {dead_old} mati")

        # tulis hasil recheck — TIDAK boleh jalan saat --dry-run, karena
        # mark_result menaikkan strike & mematikan isActive. Proxy yang kebetulan
        # lambat saat diuji akan tercopot dari kolam rotasi 9router hanya karena
        # sebuah uji coba.
        if args.dry_run:
            logger.info(f"  [3c] DRY-RUN: {len(results)} hasil recheck tidak ditulis ke DB")
        else:
            now = now_iso()
            con.execute("BEGIN IMMEDIATE")
            try:
                for row, verdict in results:
                    dbmod.mark_result(con, row["id"], verdict, is_new_row=False, now=now)
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise

        # ── 4) PRUNE (yang mati & strike cukup) ──────────────────────────
        prune_stats = {"pruned": [], "skipped_bound": [], "skipped_grace": 0}
        dead_striked = [r for r, v in results if not v.alive and r["owned"]]
        if args.no_prune:
            logger.info(f"  [4] --no-prune: {len(dead_striked)} baris mati dibiarkan")
        elif not dead_striked:
            logger.info("  [4] tak ada baris mati milik tool -> tak ada yang dipangkas")
        else:
            if args.dry_run:
                logger.info(f"  [4] DRY-RUN: akan memangkas {len(dead_striked)} baris "
                            f"(strike >= {farm_cfg['grace_strikes']} di run ini)")
                for r in dead_striked[:10]:
                    logger.info(f"        - {r['name']}")
            else:
                prune_stats = dbmod.prune_dead(
                    con,
                    {
                        "prune_types": scope["prune_types"],
                        "only_prune_owned": scope.get("only_prune_owned", True),
                        "grace_strikes": farm_cfg["grace_strikes"],
                    },
                )
                logger.info(f"  [4] dipangkas      : {len(prune_stats['pruned'])}")
                logger.info(f"      ditahan (grace): {prune_stats['skipped_grace']}")
                logger.info(f"      dilewati (terikat koneksi): {len(prune_stats['skipped_bound'])}")

        # ── 5) INJECT kandidat baru (uji dulu, baru tulis) ───────────────
        new_results = []
        alive_new = 0
        skipped_deep = 0
        if not args.recheck_only and fresh:
            target_alive = farm_cfg.get("target_fresh_alive", 0)
            target_str = f" (target: {target_alive})" if target_alive > 0 else ""
            if mode == "tcp":
                deep_note = "lompati uji exit-IP"
            elif deep_n <= 0:
                deep_note = "exit-IP utk semua yang lolos TCP"
            else:
                deep_note = f"exit-IP utk {deep_n} tercepat"
            mode_note = " [mode: tcp]" if mode == "tcp" else ""
            logger.info(f"\n  [5] UJI {human(len(fresh))} kandidat baru{target_str}{mode_note} "
                        f"(tcp dulu, lalu {deep_note})")

            async def probe_tcp_only(c):
                """Tahap 1 murah: TCP saja, tanpa mengontak endpoint keluar."""
                async with sem:
                    return c, await testers.tcp_probe(c.host, c.port, tcp_to)

            async def probe_deep(item):
                """Tahap 2: jalur HTTPS sungguhan, hanya untuk yang lolos TCP."""
                c, tcp = item
                if not tcp.alive:
                    return c, tcp
                async with sem:
                    return c, await testers.live_probe(c.proxy_url, endpoints, deep_to, lip)

            done = 0
            total = len(fresh)
            tcp_sorted = []
            tcp_tasks = [asyncio.create_task(probe_tcp_only(c)) for c in fresh]
            for fut in asyncio.as_completed(tcp_tasks):
                try:
                    item = await fut
                except asyncio.CancelledError:
                    continue
                tcp_sorted.append(item)
                done += 1
                if done % 250 == 0 or done == total:
                    progress(done, total, f"tcp lolos={sum(1 for _, v in tcp_sorted if v.alive)}")
            survived = [it for it in tcp_sorted if it[1].alive]

            # deep_test_top_n = batas uji mendalam, diambil dari yang TCP-nya tercepat.
            # 0 / tak diset = uji semua yang lolos TCP.
            deep_n_eff = len(survived) if deep_n <= 0 else min(deep_n, len(survived))

            if mode == "tcp":
                # --mode tcp: tahap mendalam dilewati sepenuhnya. Kandidat yang TCP-nya
                # hidup tetap disuntik, tetapi tanpa bukti tunnel HTTPS & tanpa exit-IP.
                # Ini pilihan sadar operator untuk run cepat, bukan default.
                for cand, tcp_v in survived:
                    new_results.append((cand, tcp_v))
                    alive_new += 1
                logger.info(f"  [5a] mode tcp: {len(survived):,} kandidat lolos TCP disuntik "
                            f"tanpa uji exit-IP (tanpa jaminan tunnel HTTPS)")
                deep_taken = []
            else:
                skipped_deep = len(survived) - deep_n_eff
                logger.info(f"  [5a] TCP lolos: {len(survived):,} dari {len(fresh):,} kandidat"
                            + (f" · uji mendalam {deep_n_eff:,} tercepat, dilewati {skipped_deep:,}"
                               if skipped_deep else " · semuanya diuji mendalam"))
                ranked = sorted(survived, key=lambda it: it[1].latency_ms or 9_999_999)
                deep_taken = ranked[:deep_n_eff]

            done = 0
            total = len(deep_taken)
            tasks = [asyncio.create_task(probe_deep(it)) for it in deep_taken]
            for fut in asyncio.as_completed(tasks):
                try:
                    cand, verdict = await fut
                except asyncio.CancelledError:
                    continue
                new_results.append((cand, verdict))
                if verdict.alive:
                    alive_new += 1
                done += 1
                if done % 250 == 0 or done == total:
                    progress(done, total, f"hidup={alive_new}")
                if target_alive > 0 and alive_new >= target_alive:
                    progress(done, total, f"hidup={alive_new}")
                    logger.info(f"\n  [5-Exit] 🎯 Target {target_alive} proxy hidup baru tercapai pada pengujian ke-{done:,}!")
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break
            # yang terpangkas oleh batas TIDAK dicatat sebagai "mati" (mereka tidak
            # pernah diuji) — dilaporkan terpisah supaya tidak ada yang hilang diam-diam.
            if skipped_deep:
                logger.info(f"       {skipped_deep:,} kandidat dilewati tahap mendalam "
                            f"(batas deep_test_top_n={deep_n}) — tidak masuk DB run ini")
            dead_new = sum(1 for _, v in new_results if not v.alive)
            logger.info(f"  [5b] kandidat baru: {alive_new} hidup / {dead_new} mati "
                        f"(dari {len(new_results):,} dinilai)")

            # ── 5c) enrich GeoIP / negara untuk proxy yang hidup ────────────
            alive_fresh = [(c, v) for c, v in new_results if v.alive]
            if alive_fresh:
                logger.info(f"  [5c] deteksi negara untuk {len(alive_fresh)} proxy hidup (batch GeoIP)...")
                geo_stats, isp_stats = geomod.enrich_verdicts_geo(new_results, timeout=6.0)
                if geo_stats:
                    top_cc = ", ".join(f"{cc}={cnt}" for cc, cnt in list(geo_stats.items())[:8])
                    logger.info(f"       Negara : {top_cc}")
                if isp_stats:
                    top_isp = ", ".join(f"{isp[:20]}={cnt}" for isp, cnt in list(isp_stats.items())[:5])
                    logger.info(f"       Top ISP: {top_isp}")
        elif args.recheck_only:
            logger.info("\n  [5] --recheck-only: lewati pengujian kandidat baru")

        if args.dry_run:
            logger.info("\n  [6] DRY-RUN: tidak menulis kandidat baru ke DB")
            inserted = 0
        else:
            con.execute("BEGIN IMMEDIATE")
            try:
                inserted = 0
                for cand, verdict in new_results:
                    if not verdict.alive:
                        continue
                    dbmod.insert_new(con, cand, verdict, now_iso())
                    inserted += 1
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            if skipped_deep:
                logger.info(f"  [6] {inserted} proxy baru masuk ke DB"
                            f" ({skipped_deep:,} kandidat terpangkas batas deep_test_top_n)")
            else:
                logger.info(f"  [6] {inserted} proxy baru masuk ke DB")

            # ── 6b) OpenCode DeepSeek Validator ─────────────────────────────
            # Validasi nyata: jika proxy tidak bisa dipakai di OpenCode (diblokir 403
            # abusive traffic atau timeout), proxy LANGSUNG DIBUANG dari DB.
            opencode_cfg = cfg.get("opencode", {})
            if opencode_cfg.get("validate", True):
                api_key = testers.get_9router_api_key(db_path)
                if api_key and testers.is_9router_online():
                    model_oc = opencode_cfg.get("model", "oc/deepseek-v4.1-flash-free")
                    to_oc = opencode_cfg.get("timeout", 5.0)
                    target_verified = opencode_cfg.get("max_verified", 20)

                    active_rows = [
                        r for r in dbmod.row_view(con)
                        if r["type"] == "http" and r["testStatus"] == "active"
                    ]
                    # Prioritaskan proxy ID dulu, lalu urut latensi terendah
                    active_rows.sort(key=lambda r: (
                        0 if (r["data"] or {}).get("country") == "ID" else 1,
                        (r["data"] or {}).get("latencyMs") if (r["data"] or {}).get("latencyMs") is not None else 999999,
                    ))
                    # Uji hingga target_verified proxy lolos
                    logger.info(f"\n  [6b] Validasi OpenCode DeepSeek ({model_oc})...")
                    oc_passed = 0
                    oc_pruned = 0
                    row_orig = con.execute("SELECT data FROM settings WHERE id=1").fetchone()
                    orig_settings_data = row_orig[0] if row_orig else None
                    try:
                        for r in active_rows:
                            if oc_passed >= target_verified:
                                break
                            con.execute("BEGIN IMMEDIATE")
                            dbmod.set_opencode_proxy_override(con, r["id"])
                            con.execute("COMMIT")

                            ok, reason = await testers.test_opencode_proxy_request(
                                api_key, model=model_oc, timeout=to_oc
                            )
                            if ok:
                                oc_passed += 1
                                logger.info(f"       ✅ {r['name']:<36s} -> lolos OpenCode ({reason})")
                            else:
                                oc_pruned += 1
                                logger.info(f"       ❌ {r['name']:<36s} -> DIBUANG: tak bisa dipakai OpenCode ({reason})")
                                dbmod.prune_ids(con, [r["id"]])
                    finally:
                        if orig_settings_data:
                            con.execute("BEGIN IMMEDIATE")
                            con.execute("UPDATE settings SET data=? WHERE id=1", (orig_settings_data,))
                            con.execute("COMMIT")

                    logger.info(f"       Hasil OpenCode: {oc_passed} lolos dipertahankan / {oc_pruned} dibuang dari DB")
                else:
                    logger.info("\n  [6b] 9Router offline di localhost:20128 — validasi OpenCode dilewati")

        # ── 6) rangkap: vercel/cloudflare tak tersentuh ─────────────────
        after = dbmod.row_view(con)
        vc_before = {r["id"]: r["updatedAt"] for r in before if r["type"] in ("vercel", "cloudflare")}
        vc_after = {r["id"]: r["updatedAt"] for r in after if r["type"] in ("vercel", "cloudflare")}
        touched = [i for i, ts in vc_after.items() if vc_before.get(i) != ts]
        if touched:
            # Ini tak boleh terjadi. Lebih baik gagal keras daripada diam.
            raise RuntimeError(f"RANGKAP MELANGAR: {len(touched)} baris vercel/cloudflare berubah")

        # ── 7) rapikan urutan (prioritaskan [ID] di atas) ───────────────
        if args.do_order and not args.dry_run:
            con.execute("BEGIN IMMEDIATE")
            try:
                n = dbmod.order_rows(con, cfg["order"]["groups"], top_id="ID")
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            logger.info(f"  [7] {n} baris disusun (prioritas [ID] di atas): " + " -> ".join(cfg["order"]["groups"]))

            # Pastikan 9Router otomatis memutar proxy aktif untuk OpenCode
            ok_strat = dbmod.enable_opencode_strategy(con, "round-robin")
            if ok_strat:
                logger.info("  [7b] 9Router providerStrategies.opencode -> rotateStrategy: round-robin (aktif)")
        else:
            logger.info("  [7] urutan dilewati (--dry-run / --no-order)")

        integrity = con.execute("PRAGMA integrity_check(1)").fetchone()[0]

        # ── 8) laporan ─────────────────────────────────────────────────
        final = dbmod.row_view(con)
        http_rows = [r for r in final if r["type"] == "http"]
        http_alive = sum(1 for r in http_rows if r["testStatus"] == "active")
        summary = {
            "mode": mode,
            "duration_s": round(time.monotonic() - t_start, 1),
            "sources": len(sources),
            "candidates": len(cands),
            "fresh": len(fresh),
            "rechecked": len(old_rows),
            "alive_old": alive_old,
            "dead_old": dead_old,
            "new_alive": alive_new,
            "skipped_deep": skipped_deep,
            "inserted": inserted,
            "pruned": len(prune_stats["pruned"]),
            "held_grace": prune_stats["skipped_grace"],
            "skipped_bound": len(prune_stats["skipped_bound"]),
            "http_total": len(http_rows),
            "http_alive": http_alive,
            "db_total": len(final),
            "vercel": sum(1 for r in final if r["type"] == "vercel"),
            "cloudflare": sum(1 for r in final if r["type"] == "cloudflare"),
            "integrity": integrity,
            "guard_ok": True,
        }
        stamp = report_mod.stamp_now()
        per_source: dict[str, dict] = {}
        for c in cands:
            s = per_source.setdefault(c.source, {"candidates": 0})
            s["candidates"] += 1
        new_by_src = {}
        for c, v in new_results:
            s = new_by_src.setdefault(c.source, {"alive": 0, "dead": 0})
            s["alive" if v.alive else "dead"] += 1
        fastest = sorted(
            [
                {
                    "proxyUrl": c.proxy_url,
                    "protocol": c.protocol,
                    "latencyMs": v.latency_ms,
                    "source": c.source,
                }
                for c, v in new_results
                if v.alive and v.latency_ms is not None
            ],
            key=lambda x: x["latencyMs"],
        )
        # gabung hitungan per sumber: kandidat (dari fetch) + hidup/mati (dari uji baru)
        merged = {}
        for sid, v in per_source.items():
            merged[sid] = {"candidates": v["candidates"], "alive": 0, "dead": 0}
        for sid, v in new_by_src.items():
            m = merged.setdefault(sid, {"candidates": 0, "alive": 0, "dead": 0})
            m.update(v)
        jpath, mpath = report_mod.write_reports(
            os.path.join(HERE, "reports"),
            {"summary": summary, "per_source": merged, "per_protocol": {}, "fastest": fastest},
            stamp,
        )

        logger.info("\n" + "=" * 66)
        logger.info("  SELESAI" + ("  (DRY-RUN, DB tak diubah)" if args.dry_run else ""))
        logger.info("=" * 66)
        for k in ("duration_s", "rechecked", "alive_old", "new_alive", "inserted",
                  "pruned", "held_grace", "http_total", "http_alive", "vercel",
                  "cloudflare", "integrity", "guard_ok"):
            logger.info(f"   {k:14s} {summary[k]}")
        logger.info(f"\n   laporan : {mpath}")
        logger.info(f"   data    : {jpath}")
        return 0
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser(
        description="proxy-farm-9router: farm proxy publik, recheck, bersihkan, inject ke 9router"
    )
    p.add_argument("--dry-run", action="store_true",
                   help="uji semuanya, jangan tulis ke DB")
    p.add_argument("--no-prune", action="store_true", help="jangan hapus baris mati")
    p.add_argument("--no-order", action="store_false", dest="do_order", help="jangan susun ulang")
    p.add_argument("--mode", choices=["deep", "tcp"], default=None,
                   help="deep = TCP + exit-IP (default), tcp = TCP saja")
    p.add_argument("--limit-sources", default=None, help="id sumber, koma dipisah")
    p.add_argument("--recheck-only", action="store_true",
                   help="hanya uji ulang dan pangkas proxy lama di DB, lewati fetch baru")
    p.add_argument("--action", choices=["auto", "indonesia", "cek", "clean"], default=None,
                   help="auto (default) | indonesia (fokus IP ID) | cek (uji & hapus mati) "
                        "| clean (hapus semua proxy custom)")
    p.add_argument("--confirm", default=None,
                   help="untuk --action clean: isi dengan HAPUS sebagai konfirmasi")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None,
                   help="level detail log (default: INFO / config.toml)")
    p.add_argument("--log-file", default=None,
                   help="nama file log khusus di folder logs/ (default: farm.log)")
    p.add_argument("--logs", action="store_true",
                   help="tampilkan 50 baris log terakhir dari logs/farm.log dan keluar")
    p.add_argument("--protocol", choices=["all", "http", "https", "socks5"], default="all",
                   help="filter protokol proxy tertentu: all (default) | http | https | socks5")
    p.add_argument("--selftest", action="store_true",
                   help="periksa kesiapan lingkungan (python, dependensi, DB, 9router) lalu keluar")
    args = p.parse_args()
    if args.selftest:
        raise SystemExit(selftest(args))
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        logger = get_logger()
        logger.warning("\ndibatalkan oleh pengguna (SIGINT)")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
