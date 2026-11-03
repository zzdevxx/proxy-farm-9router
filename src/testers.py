"""Engine pengujian proxy.

Tahap 1: TCP probe (cepat, memilah host mati dalam milidetik tanpa kirim data).
Tahap 2: Live HTTPS probe ke https://api.ipify.org (fallback https://icanhazip.com).
         - Menguji kemampuan tunneling HTTPS CONNECT (kebutuhan mutlak 9router).
         - Validasi respons adalah IP valid menggunakan ipaddress (menolak HTML / error Cloudflare).
         - Anti-leak check (exit_ip != local_ip).
         - Timeout dibatasi ketat dengan asyncio.wait_for untuk mencegah socket gantung.
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
from dataclasses import dataclass

import httpx

_HTTPX_SCHEMES = {"http", "https", "socks5"}

_ENDPOINTS = [
    "https://api.ipify.org",
    "https://icanhazip.com",
]


@dataclass
class Verdict:
    alive: bool
    latency_ms: int | None = None
    exit_ip: str | None = None
    leak: bool = False
    reason: str = ""

    def as_dict(self):
        return {
            "alive": self.alive,
            "latency_ms": self.latency_ms,
            "exit_ip": self.exit_ip,
            "leak": self.leak,
            "reason": self.reason,
        }


async def _get_via_proxy(proxy_url: str, url: str, timeout: float):
    # wait_for pembungkus eksternal itu WAJIB: timeout httpx tidak
    # membatasi handshake SOCKS5, sehingga proxy yang menggantung bisa
    # menahan sesi berjam-jam.
    async def _fetch():
        async with httpx.AsyncClient(
            proxy=proxy_url, timeout=timeout, trust_env=False, verify=False
        ) as client:
            return await client.get(url)

    return await asyncio.wait_for(_fetch(), timeout=timeout + 0.5)


async def tcp_probe(host: str, port: int, timeout: float) -> Verdict:
    """Tahap murah: bisa TCP connect. Tidak mengirim data ke mana pun."""
    t0 = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except asyncio.TimeoutError:
        return Verdict(False, reason="timeout")
    except ConnectionRefusedError:
        return Verdict(False, reason="refused")
    except OSError as exc:
        return Verdict(False, reason=f"os:{exc.errno or 'err'}")
    try:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
    except Exception:
        pass
    return Verdict(True, latency_ms=max(1, int((time.monotonic() - t0) * 1000)))


async def live_probe(
    proxy_url: str,
    endpoints: list[str] | None = None,
    timeout: float = 5.0,
    local_ip: str | None = None,
) -> Verdict:
    """Uji nyata HTTPS proxy.

    9router membutuhkan HTTPS tunnel untuk berkomunikasi dengan upstream AI API.
    Proxy harus berhasil melakukan CONNECT TLS dan mengembalikan exit IP yang sah.
    """
    scheme = proxy_url.split("://", 1)[0]
    if scheme not in _HTTPX_SCHEMES:
        return Verdict(False, reason=f"scheme_{scheme}_tak_bisa_diuji_httpx")

    eps = endpoints or _ENDPOINTS
    last_err = ""

    for ep in eps:
        t0 = time.monotonic()
        try:
            r = await _get_via_proxy(proxy_url, ep, timeout)
        except asyncio.TimeoutError:
            last_err = "timeout"
            # Timeout pada handshake/tunnel = proxy tidak responsif, hentikan uji
            # tanpa membuang waktu mencoba endpoint kedua.
            break
        except Exception as exc:
            last_err = f"{type(exc).__name__}"
            # Masalah koneksi/TLS pada proxy itu sendiri, hentikan uji.
            break

        if r.status_code != 200:
            last_err = f"status:{r.status_code}"
            # Status error pada endpoint target (misal rate limit 429), boleh coba endpoint cadangan.
            continue

        body = (r.text or "").strip()
        try:
            ip_obj = ipaddress.ip_address(body)
            exit_ip = str(ip_obj)
        except ValueError:
            last_err = f"non_ip_body:{body[:30]}"
            continue

        leak = bool(local_ip and exit_ip == local_ip)
        if leak:
            return Verdict(
                False,
                exit_ip=exit_ip,
                leak=True,
                reason="exit_ip == ip lokal (proxy bocor)",
            )

        latency_ms = max(1, int((time.monotonic() - t0) * 1000))
        return Verdict(
            True,
            exit_ip=exit_ip,
            latency_ms=latency_ms,
            leak=False,
            reason="",
        )

    return Verdict(False, reason=last_err or "no_endpoint_ok")


def is_9router_online(base_url: str = "http://localhost:20128") -> bool:
    """Cek apakah gateway 9router aktif di localhost."""
    try:
        with httpx.Client(timeout=1.5) as c:
            r = c.get(f"{base_url}/api/health")
            return r.status_code == 200 and r.json().get("ok") is True
    except Exception:
        return False


def get_9router_api_key(db_path: str) -> str | None:
    """Ambil API key aktif dari database 9router."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = con.execute("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1").fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None


async def test_opencode_proxy_request(
    api_key: str,
    base_url: str = "http://localhost:20128",
    model: str = "oc/deepseek-v4.1-flash-free",
    timeout: float = 6.0,
) -> tuple[bool, str]:
    """Tembak endpoint chat 9router untuk menguji respon model OpenCode."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "1"}],
                    "max_tokens": 1,
                },
            )
        body = resp.text
        if resp.status_code == 200:
            return True, "200_ok"
        elif resp.status_code == 403:
            if "abusive traffic" in body or "FreeTierError" in body:
                return False, "403_abusive_ip"
            elif "insufficient_quota" in body:
                return False, "403_quota_ip"
            return False, "403_blocked_ip"
        elif resp.status_code == 429:
            return False, "429_rate_limited"
        elif resp.status_code in (502, 504):
            return False, f"{resp.status_code}_gateway_timeout"
        else:
            return False, f"status_{resp.status_code}"
    except asyncio.TimeoutError:
        return False, "timeout"
    except Exception as e:
        return False, f"error:{type(e).__name__}"

