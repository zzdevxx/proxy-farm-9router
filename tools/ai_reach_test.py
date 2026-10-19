#!/usr/bin/env python3
"""Uji apakah proxy benar-benar bisa dipakai provider AI (bukan cuma keluar internet).

farm.py hanya membuktikan proxy bisa menembus HTTPS CONNECT ke endpoint status
(ipify). Itu TIDAK membuktikan proxy bisa melewati Cloudflare milik provider AI,
dan tidak membuktikan endpoint provider mau melayani.

Skrip ini menambahkan lapisan yang hilang: menembak endpoint provider AI yang
NYATA lewat proxy, lalu menilai apakah responsnya benar-benar dari provider.

Ini yang menjelaskan kenapa sebagian proxy "hidup" tapi tetap error di opencode:
proxy bisa keluar ke internet, tapi ditolak (403/429) atau diblokir di jalur
menuju provider.

Pemakaian:
    python3 tools/ai_reach_test.py                    # uji semua proxy aktif
    python3 tools/ai_reach_test.py --country ID       # hanya Indonesia
    python3 tools/ai_reach_test.py --limit 40         # ambil N tercepat
    python3 tools/ai_reach_test.py --endpoint 9router # uji lewat 9router (butuh key)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
LOCAL_LIBS = os.path.join(ROOT, ".pylibs")
if os.path.isdir(LOCAL_LIBS) and LOCAL_LIBS not in sys.path:
    sys.path.insert(0, LOCAL_LIBS)

import httpx
import tomllib

# Endpoint provider AI yang benar-benar dipakai gateway. Ukurannya besar
# (ratusan KB) sehingga proxy palsu yang mengembalikan halaman kosong atau
# halaman blokir langsung ketahuan dari ukuran respons.
AI_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/models",
    "openrouter-key": "https://openrouter.ai/api/v1/key",
}
MIN_BYTES = 10_000        # respons sah jauh di atas ini; halaman blokir jauh di bawah


def load_cfg() -> dict:
    with open(os.path.join(ROOT, "config.toml"), "rb") as f:
        return tomllib.load(f)


def ambil_proxy(db_path: str, country: str | None, limit: int | None, jenis: str):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out = []
    for pid, active, status, data in con.execute(
        "SELECT id, isActive, testStatus, data FROM proxyPools"
    ):
        try:
            d = json.loads(data)
        except Exception:
            continue
        if d.get("type") != "http":
            continue
        if jenis == "aktif" and not active:
            continue
        if country and d.get("country") != country:
            continue
        url = d.get("proxyUrl")
        if not url:
            continue
        out.append({
            "id": pid,
            "url": url,
            "name": d.get("name") or url,
            "country": d.get("country"),
            "latencyMs": d.get("latencyMs"),
            "isp": d.get("isp"),
            "isActive": bool(active),
        })
    con.close()
    out.sort(key=lambda r: r["latencyMs"] if r["latencyMs"] else 9_999_999)
    return out[:limit] if limit else out


async def uji_lewat_proxy(item: dict, endpoint: str, timeout: float) -> dict:
    """Tembak endpoint provider lewat proxy; nilai apakah responsnya sah."""
    hasil = dict(item)
    t0 = time.monotonic()
    try:
        async def _fetch():
            async with httpx.AsyncClient(
                proxy=item["url"], timeout=timeout, trust_env=False, verify=False,
                follow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0 (compatible; proxy-farm-check)"},
            ) as c:
                return await c.get(endpoint)

        r = await asyncio.wait_for(_fetch(), timeout=timeout + 1.0)
    except asyncio.TimeoutError:
        hasil.update(ok=False, alasan="timeout", bytes=0)
        return hasil
    except Exception as exc:
        hasil.update(ok=False, alasan=type(exc).__name__, bytes=0)
        return hasil

    hasil["ms"] = int((time.monotonic() - t0) * 1000)
    hasil["status"] = r.status_code
    hasil["bytes"] = len(r.content)
    hasil["cf"] = r.headers.get("cf-mitigated") or r.headers.get("server")

    if r.status_code in (403, 407, 429):
        hasil.update(ok=False, alasan=f"ditolak_{r.status_code}")
        return hasil
    if r.status_code != 200:
        hasil.update(ok=False, alasan=f"status_{r.status_code}")
        return hasil
    if len(r.content) < MIN_BYTES:
        # 200 dengan badan kecil = halaman blokir/portal captive, bukan data provider
        hasil.update(ok=False, alasan=f"badan_kecil_{len(r.content)}B")
        return hasil
    hasil.update(ok=True, alasan="ok")
    return hasil


async def uji_lewat_9router(item: dict, base: str, key: str, model: str, timeout: float) -> dict:
    """Uji nyata: minta 9router bicara ke provider AI memakai proxy ini.

    Ini bisa dijalankan karena 9router membaca proxy langsung dari kolom
    proxyUrl saat request berjalan — jadi kita tidak perlu mengubah
    konfigurasi apa pun.
    """
    hasil = dict(item)
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Balas tepat satu kata: OK"}],
        "max_tokens": 8,
    }
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
            r = await c.post(
                f"{base}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "X-9Router-Proxy-Url": item["url"],
                },
                json=body,
            )
        hasil["ms"] = int((time.monotonic() - t0) * 1000)
        hasil["status"] = r.status_code
        if r.status_code == 200:
            try:
                j = r.json()
                teks = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
                hasil.update(ok=True, alasan="ok", jawab=(teks or "")[:30])
            except Exception:
                hasil.update(ok=False, alasan="json_tak_terbaca")
        else:
            hasil.update(ok=False, alasan=f"status_{r.status_code}",
                         pesan=(r.text or "")[:120])
    except Exception as exc:
        hasil.update(ok=False, alasan=type(exc).__name__, ms=int((time.monotonic() - t0) * 1000))
    return hasil


def ratakan(hasil: list[dict]) -> None:
    ok = [h for h in hasil if h.get("ok")]
    print("\n" + "=" * 78)
    print(f"  HASIL: {len(ok)} proxy berhasil dari {len(hasil)} diuji "
          f"({len(ok)*100//max(1,len(hasil))}%)")
    print("=" * 78)
    if ok:
        print("\n  ✅ BISA DIPAKAI:")
        print(f"  {'negara':6s} {'ms':>6s} {'ukuran':>9s}  proxy")
        for h in sorted(ok, key=lambda x: x.get("ms") or 9e9)[:25]:
            print(f"  {str(h.get('country')):6s} {str(h.get('ms')):>6s} "
                  f"{str(h.get('bytes')):>9s}  {h['name'][:46]}")
    gagal: dict[str, int] = {}
    for h in hasil:
        if not h.get("ok"):
            gagal[h.get("alasan", "?")] = gagal.get(h.get("alasan", "?"), 0) + 1
    if gagal:
        print("\n  ❌ GAGAL (per alasan):")
        for k, v in sorted(gagal.items(), key=lambda x: -x[1]):
            print(f"     {v:5d}  {k}")
    per_cc: dict[str, list[int]] = {}
    for h in hasil:
        cc = str(h.get("country") or "??")
        per_cc.setdefault(cc, [0, 0])
        per_cc[cc][0] += 1
        if h.get("ok"):
            per_cc[cc][1] += 1
    print("\n  PER NEGARA (berhasil/diuji):")
    for cc, (tot, oke) in sorted(per_cc.items(), key=lambda x: -x[1][0])[:12]:
        bar = "█" * int(20 * oke / tot) + "░" * (20 - int(20 * oke / tot))
        print(f"     {cc:4s} {bar} {oke:3d}/{tot:3d}")


async def main_async(args) -> int:
    cfg = load_cfg()
    db_path = args.db or cfg["database"]["path"]
    if not os.path.exists(db_path):
        print(f"DB tidak ada: {db_path}", file=sys.stderr)
        return 2

    rows = ambil_proxy(db_path, args.country, args.limit, args.jenis)
    if not rows:
        print("tidak ada proxy yang cocok dengan filter", file=sys.stderr)
        return 1

    if args.endpoint == "9router":
        key = args.key or os.environ.get("NINEROUTER_KEY", "")
        if not key:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = con.execute(
                "SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1"
            ).fetchone()
            key = row[0] if row else ""
            con.close()
        if not key:
            print("butuh API key 9router (--key / NINEROUTER_KEY)", file=sys.stderr)
            return 2
        print(f"  Menguji {len(rows)} proxy LEWAT 9router → {args.model}")
        print(f"  (ini uji sebenarnya: 9router bicara ke provider AI memakai proxy itu)")
        sem = asyncio.Semaphore(args.concurrency)

        async def kerja(it):
            async with sem:
                return await uji_lewat_9router(it, args.base, key, args.model, args.timeout)
    else:
        ep = AI_ENDPOINTS[args.endpoint]
        print(f"  Menguji {len(rows)} proxy → {ep}")
        print(f"  (menembak endpoint provider AI nyata; respons < {MIN_BYTES} byte = blokir)")
        sem = asyncio.Semaphore(args.concurrency)

        async def kerja(it):
            async with sem:
                return await uji_lewat_proxy(it, ep, args.timeout)

    t0 = time.monotonic()
    hasil = await asyncio.gather(*[kerja(r) for r in rows], return_exceptions=True)
    hasil = [h for h in hasil if isinstance(h, dict)]
    print(f"\n  selesai dalam {time.monotonic()-t0:.1f} s")
    ratakan(hasil)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(hasil, f, indent=1, ensure_ascii=False)
        print(f"\n  laporan: {args.out}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Uji jangkauan provider AI lewat proxy")
    p.add_argument("--endpoint", choices=[*AI_ENDPOINTS, "9router"], default="openrouter",
                   help="openrouter = tembak endpoint provider; 9router = uji nyata lewat gateway")
    p.add_argument("--country", default=None, help="filter kode negara, mis. ID")
    p.add_argument("--limit", type=int, default=None, help="ambil N tercepat saja")
    p.add_argument("--jenis", choices=["aktif", "semua"], default="aktif",
                   help="aktif = hanya isActive=1 (default)")
    p.add_argument("--concurrency", type=int, default=40)
    p.add_argument("--timeout", type=float, default=12.0)
    p.add_argument("--db", default=None, help="pakai salinan DB, bukan DB 9router")
    p.add_argument("--base", default="http://localhost:20128")
    p.add_argument("--key", default=None)
    p.add_argument("--model", default="oc/deepseek-v4.1-flash-free")
    p.add_argument("--out", default=None, help="simpan hasil ke JSON")
    args = p.parse_args()
    try:
        raise SystemExit(asyncio.run(main_async(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
