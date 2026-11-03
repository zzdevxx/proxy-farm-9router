#!/usr/bin/env python3
"""Susun ulang tampilan proxy di 9router tanpa farm apa pun.

Dijalankan manual dari terminal untuk memastikan blok urutannya tetap
custom -> vercel -> cloudflare tanpa perlu menjalankan proses panjang.

Penting: rangkap relay (vercel/cloudflare) dicek dengan `relay_snapshot()`,
bukan dengan membandingkan `updatedAt`. `order_rows()` SENGAJA menulis ulang
stempel `updatedAt` pada SETIAP baris termasuk relay, karena stempel itu
adalah mekanisme urutannya. Memeriksa `updatedAt` berarti selalu melapor
pelanggaran palsu — dan melewatkan hal yang benar-benar penting: apakah relay
masih ada dan masih aktif.
"""

from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tomllib

from src import db as dbmod
from src import util as utilmod


def main() -> int:
    cfg = tomllib.load(open(os.path.join(HERE, "config.toml"), "rb"))
    db_path = utilmod.resolve_db_path(cfg["database"]["path"])
    con = dbmod.connect(db_path)
    con.execute("PRAGMA busy_timeout=60000")
    try:
        before = dbmod.relay_snapshot(con)
        con.execute("BEGIN IMMEDIATE")
        n = dbmod.order_rows(con, cfg["order"]["groups"])
        con.execute("COMMIT")

        ok = True
        try:
            dbmod.assert_relays_untouched(before, dbmod.relay_snapshot(con))
        except RuntimeError as exc:
            print(f"  rangkap vercel/cloudflare: ❌ {exc}")
            ok = False
        else:
            print(f"  rangkap vercel/cloudflare: ✅ tak tersentuh "
                  f"({len(before)} relay, tetap ada & aktif)")

        rows = dbmod.row_view(con)
        kinds: dict[str, int] = {}
        for r in rows:
            kinds[r["type"]] = kinds.get(r["type"], 0) + 1
        print(f"  {n} baris disusun: " + " -> ".join(cfg["order"]["groups"]))
        print("  isi DB: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
