"""Modul Resolusi GeoIP & Deteksi Negara Proxy via batch ip-api.com.

Mendeteksi negara, kode ISO ([SG], [ID], [US], [DE]), serta ISP dari setiap
proxy hidup yang lolos uji tanpa memerlukan API key atau dependensi eksternal.
Mendukung querying dalam batch 100 IP sekaligus (efisien & cepat: ~0.5s per 100 IP).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger("geo")

BATCH_ENDPOINT = "http://ip-api.com/batch"


def batch_lookup_geoip(
    ips: list[str], timeout: float = 6.0
) -> dict[str, dict[str, str]]:
    """Query informasi negara untuk kumpulan IP dalam batch (100 IP per request).

    Mengembalikan kamus: {ip: {"country": "Singapore", "country_code": "SG", "isp": "..."}}
    """
    if not ips:
        return {}

    # Deduplikasi IP
    unique_ips = list(dict.fromkeys(ips))
    results: dict[str, dict[str, str]] = {}
    chunk_size = 100

    for i in range(0, len(unique_ips), chunk_size):
        chunk = unique_ips[i : i + chunk_size]
        try:
            req_data = json.dumps(chunk).encode("utf-8")
            req = urllib.request.Request(
                BATCH_ENDPOINT,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in data:
                        q_ip = item.get("query")
                        if q_ip and item.get("status") == "success":
                            results[q_ip] = {
                                "country": item.get("country", "Unknown"),
                                "country_code": item.get("countryCode", "??"),
                                "city": item.get("city", "-"),
                                "isp": item.get("isp", "-"),
                            }
        except Exception as exc:
            logger.warning("Gagal query batch GeoIP untuk %d IP: %s", len(chunk), exc)
            continue

    return results


def enrich_verdicts_geo(
    new_results: list[tuple[Any, Any]], timeout: float = 6.0
) -> tuple[dict[str, int], dict[str, int]]:
    """Isi metadata negara & ISP pada verdict kandidat yang hidup.

    Mengembalikan tuple: (distribusi_negara, distribusi_isp)
    """
    alive_items = [
        (c, v) for c, v in new_results if getattr(v, "alive", False)
    ]
    if not alive_items:
        return {}, {}

    # Kumpulkan target IP: utamakan exit_ip nyata jika ada, fallback ke c.host
    ips_to_query = []
    for c, v in alive_items:
        target_ip = getattr(v, "exit_ip", None) or getattr(c, "host", "")
        if target_ip:
            ips_to_query.append(target_ip)

    geo_map = batch_lookup_geoip(ips_to_query, timeout=timeout)

    country_counts: dict[str, int] = {}
    isp_counts: dict[str, int] = {}
    for c, v in alive_items:
        target_ip = getattr(v, "exit_ip", None) or getattr(c, "host", "")
        geo = geo_map.get(target_ip, {})
        cc = geo.get("country_code", "??")
        c_name = geo.get("country", "Unknown")
        isp = geo.get("isp", "-")

        # Pasang atribut dinamis ke verdict
        v.country_code = cc
        v.country = c_name
        v.isp = isp

        country_counts[cc] = country_counts.get(cc, 0) + 1
        if isp and isp != "-":
            isp_counts[isp] = isp_counts.get(isp, 0) + 1

    sorted_countries = dict(sorted(country_counts.items(), key=lambda x: x[1], reverse=True))
    sorted_isps = dict(sorted(isp_counts.items(), key=lambda x: x[1], reverse=True))
    return sorted_countries, sorted_isps
