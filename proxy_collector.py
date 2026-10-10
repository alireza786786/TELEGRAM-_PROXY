#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram MTProto Proxy Collector v6.0

هر اجرا:
  ۱) پروکسی‌ها را از PROXY_SOURCES (متغیر محرمانه) جمع می‌کند (لینک مستقیم، فایل متنی، صفحهٔ کانال t.me)
  ۲) نوع سکرت را درست تشخیص می‌دهد (Fake-TLS = ee ، padded = dd ، ساده، base64url)
  ۳) روی هر پروکسی ۳ بار تست اتصال TCP می‌زند و با امتیاز (نوع سکرت، پورت، تأخیر، نوسان، سابقه) رتبه می‌دهد
  ۴) دو پست جدا می‌فرستد (عکس + ۱۷ هایپرلینک + ۳ دکمه): لینک‌های MTProto وب (t.me) و لینک‌های tg://
  ۵) دو فایل جدا (هر کدام تا ۱۰۰ پروکسی) می‌فرستد و در مخزن ذخیره می‌کند

نکته: تست فقط «باز بودن پورت از محل اجرای برنامه» را می‌سنجد، نه اینکه تلگرام از ایران وصل می‌شود.
متن پست‌ها همین را صادقانه می‌گویند (TEST_LABEL).

متغیرهای محیطی:
  BOT_TOKEN, CHAT_ID, PROXY_SOURCES   (الزامی برای ارسال)
  TEST_LABEL   محل تست در متن پست (پیش‌فرض: سرور GitHub، خارج از ایران)
  LINK_STYLE   plain (پیش‌فرض) یا ping  (نمایش پینگ کنار «پروکسی»)

فایل اختیاری rotation.json برای افزودن عکس/متن/تیتر بدون ویرایش کد:
  {"images": ["https://..."], "texts": ["..."], "headers": ["..."], "replace": false}
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import html
import ipaddress
import json
import logging
import os
import random
import re
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlparse

# ============================== تنظیمات ==============================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
TEST_LABEL = os.environ.get("TEST_LABEL", "سرور GitHub (خارج از ایران)").strip()
LINK_STYLE = os.environ.get("LINK_STYLE", "plain").strip().lower()
API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
ALLOW_PRIVATE = os.environ.get("ALLOW_PRIVATE", "") == "1"      # فقط برای تست محلی

FILE_TG = "PROXIES_TG_TOP100.txt"        # لینک‌های tg://proxy
FILE_HTTP = "PROXIES_HTTP_TOP100.txt"    # لینک‌های https://t.me/proxy
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
ROTATION_FILE = Path(os.environ.get("ROTATION_FILE", "rotation.json"))

CHANNEL_ID = "@Goodbaye_filtering"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"
GROUP_LINK = "https://t.me/CONFIG_V2RAY_VIP"
SHARE_TEXT = "⚡️ پکیج پروکسی‌های پرسرعت و تست‌شدهٔ تلگرام"

TOP_LINKS = 17            # تعداد هایپرلینک در هر پست (ردیف اول ۲ تا، بعد ردیف‌های ۳تایی)
TOP_FILE = 100            # تعداد پروکسی در هر فایل
MIN_POST = 3              # اگر کمتر از این تعداد پروکسی سالم بود، پست نمی‌فرستد
DISTINCT_SETS = False     # True: پست دوم (tg) از رتبه‌های بعدی انتخاب شود، نه همان ۱۷ تا
PER_SUBNET_LINKS = 2      # سقف پروکسی از هر زیرشبکه در ۱۷ تای پست
PER_SUBNET_FILE = 4       # سقف پروکسی از هر زیرشبکه در فایل ۱۰۰تایی
RECENT_PENALTY = 150      # کم کردن امتیاز پروکسی‌هایی که در ۳ اجرای اخیر منتشر شده‌اند (۰ = خاموش)

FETCH_TIMEOUT = 20
MAX_RETRIES = 2
DNS_TIMEOUT = 4.0
TCP_TIMEOUT = 3.0
EXTRA_SAMPLES = 2         # بعد از اتصال اول، چند نمونهٔ دیگر
MIN_SUCCESS = 2           # حداقل چند اتصال موفق از ۳ تا
MAX_DNS = 100
MAX_TCP = 200

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

PROXY_RE = re.compile(
    r"(?:https?://(?:t\.me|telegram\.me|telegram\.dog)|tg://)/?(?:proxy)?\?[^\s'\"<>]+", re.I)
IP_PORT_SECRET_RE = re.compile(
    r"(\b(?:\d{1,3}\.){3}\d{1,3}\b)[:\s]+(\d{2,5})[:\s]+([A-Fa-f0-9]{32,})")
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z0-9-]{2,63}$")

# ============================== لاگ ==============================


class _MaskFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if BOT_TOKEN:
            record.msg = str(record.msg).replace(BOT_TOKEN, "***")
            if record.args:
                record.args = tuple(str(a).replace(BOT_TOKEN, "***") if isinstance(a, str) else a
                                    for a in record.args)
        return True


def setup_logging() -> logging.Logger:
    fmt = "%(asctime)s - [%(levelname)s] - %(message)s"
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler("proxy_collector.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    lg = logging.getLogger("ProxyEngine")
    for h in logging.getLogger().handlers:
        h.addFilter(_MaskFilter())
    return lg


logger = setup_logging()


def mask(text: str) -> str:
    return text.replace(BOT_TOKEN, "***") if BOT_TOKEN else text


# ============================== ساعت تهران و تقویم شمسی ==============================
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def tehran_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=3, minutes=30)))


def tehran_strings() -> Tuple[str, str, int]:
    now = tehran_now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return now.strftime("%H:%M"), f"{jy:04d}/{jm:02d}/{jd:02d}", now.hour


def greeting(hour: int) -> str:
    if 5 <= hour < 11:
        return "🌅 صبح بخیر"
    if 11 <= hour < 15:
        return "☀️ ظهر بخیر"
    if 15 <= hour < 19:
        return "🌇 عصر بخیر"
    if 19 <= hour < 24:
        return "🌙 شب بخیر"
    return "🌌 شب‌زنده‌دارها سلام"


# ============================== ساختار پروکسی و تشخیص نوع سکرت ==============================
def secret_bytes(secret: str) -> Optional[bytes]:
    """سکرت را (hex یا base64/base64url) به بایت تبدیل می‌کند."""
    if re.fullmatch(r"[0-9a-fA-F]+", secret) and len(secret) % 2 == 0:
        return bytes.fromhex(secret)
    try:
        t = secret.replace("-", "+").replace("_", "/")
        t += "=" * (-len(t) % 4)
        return base64.b64decode(t, validate=True)
    except Exception:
        return None


def analyze_secret(secret: str) -> Tuple[str, str, str]:
    """-> (kind, domain, normalized_hex)  ؛ kind: faketls | padded | plain | unknown | invalid"""
    b = secret_bytes(secret)
    if not b or len(b) < 16:
        return "invalid", "", ""
    if b[0] == 0xEE and len(b) > 17:
        dom = b[17:].decode("ascii", "ignore").strip().lower()
        return "faketls", dom, b.hex()
    if b[0] == 0xDD and len(b) == 17:
        return "padded", "", b.hex()
    if len(b) == 16:
        return "plain", "", b.hex()
    return "unknown", "", b.hex()


@dataclass
class ProxyLink:
    server: str
    port: int
    secret: str
    kind: str
    domain: str
    norm: str
    ip: str = ""
    latencies: List[float] = field(default_factory=list)
    attempts: int = 0
    score: float = 0.0

    @property
    def is_faketls(self) -> bool:
        return self.kind == "faketls"

    @property
    def key(self) -> str:
        return f"{self.ip or self.server}:{self.port}:{self.norm}"

    @property
    def hid(self) -> str:
        return hashlib.sha1(self.key.encode()).hexdigest()[:12]

    @property
    def median(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 9999.0

    @property
    def jitter(self) -> float:
        return (max(self.latencies) - min(self.latencies)) if len(self.latencies) > 1 else 0.0

    @property
    def tg_url(self) -> str:
        return f"tg://proxy?server={self.server}&port={self.port}&secret={quote(self.secret, safe='-_=~')}"

    @property
    def http_url(self) -> str:
        return f"https://t.me/proxy?server={self.server}&port={self.port}&secret={quote(self.secret, safe='-_=~')}"

    def subnet(self) -> str:
        host = self.ip or self.server
        try:
            ip = ipaddress.ip_address(host)
            prefix = 24 if ip.version == 4 else 48
            return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
        except ValueError:
            return host


def is_valid_host(server: str) -> bool:
    try:
        ip = ipaddress.ip_address(server)
        if not ALLOW_PRIVATE and (ip.is_private or ip.is_loopback or ip.is_link_local
                                  or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
        return True
    except ValueError:
        return bool(DOMAIN_RE.match(server))


def make_proxy(server: str, port_raw: str, secret: str) -> Optional[ProxyLink]:
    server = (server or "").strip().strip("[]").rstrip(".").lower()
    secret = (secret or "").strip().replace(" ", "+")
    port_raw = str(port_raw or "").strip()
    if not server or not secret or not port_raw.isdigit():
        return None
    port = int(port_raw)
    if not 0 < port < 65536 or not is_valid_host(server):
        return None
    kind, domain, norm = analyze_secret(secret)
    if kind == "invalid":
        return None
    return ProxyLink(server=server, port=port, secret=secret, kind=kind, domain=domain, norm=norm)


def parse_proxy_url(url: str) -> Optional[ProxyLink]:
    try:
        query = url.split("?", 1)[1]
        qs: Dict[str, str] = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                qs[k.strip().lower()] = unquote(v)
        return make_proxy(qs.get("server", ""), qs.get("port", ""), qs.get("secret", ""))
    except Exception:
        return None


def extract_proxies(text: str) -> List[ProxyLink]:
    """همهٔ پروکسی‌های داخل یک متن (حتی چند تا در یک خط، و لینک‌های HTML-escaped)."""
    text = html.unescape(text)
    found: List[ProxyLink] = []
    for m in PROXY_RE.finditer(text):
        p = parse_proxy_url(m.group(0))
        if p:
            found.append(p)
    for m in IP_PORT_SECRET_RE.finditer(text):
        p = make_proxy(m.group(1), m.group(2), m.group(3))
        if p:
            found.append(p)
    return found


# ============================== شبکه (فقط کتابخانهٔ استاندارد) ==============================
def http_request(url: str, method: str = "GET", data: Optional[bytes] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: float = 20,
                 max_bytes: int = 5_000_000) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(max_bytes) if method != "HEAD" else b""
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(max_bytes)
        except Exception:
            body = b""
        return e.code, dict(e.headers or {}), body
    except Exception as e:  # noqa: BLE001
        return 0, {}, mask(str(e)).encode("utf-8", "ignore")


def normalize_source_url(url: str) -> str:
    u = url.strip()
    p = urlparse(u)
    host = p.netloc.lower()
    if host == "raw.githubusercontent.com":
        return u.replace("/refs/heads/", "/", 1)
    if host in ("t.me", "telegram.me") and p.path.strip("/") and not p.path.startswith(("/s/", "/proxy")):
        return f"{p.scheme}://{host}/s/{p.path.lstrip('/')}" + (f"?{p.query}" if p.query else "")
    return u


async def fetch_source(idx: int, url: str, sem: asyncio.Semaphore) -> str:
    target = normalize_source_url(url)
    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            status, _, body = await asyncio.to_thread(http_request, target, "GET", None, UA, FETCH_TIMEOUT)
            if status == 200:
                text = body.decode("utf-8", "ignore")
                logger.info(f"✅ منبع #{idx}: دریافت شد ({len(text.splitlines())} خط).")
                return text
            if status in (429, 500, 502, 503, 504, 0) and attempt < MAX_RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            logger.warning(f"⚠️ منبع #{idx}: پاسخ نامعتبر (وضعیت {status}).")
            return ""
    return ""


async def collect_all(sources: List[str]) -> List[ProxyLink]:
    if not sources:
        logger.error("❌ هیچ منبعی در PROXY_SOURCES نیست.")
        return []
    logger.info(f"🚀 دریافت از {len(sources)} ورودی (آدرس‌ها عمداً در لاگ چاپ نمی‌شوند)...")
    seen: set = set()
    proxies: List[ProxyLink] = []
    urls: List[str] = []

    def add(plist: List[ProxyLink]) -> None:
        for p in plist:
            k = (p.server, p.port, p.norm)
            if k not in seen:
                seen.add(k)
                proxies.append(p)

    for line in sources:
        direct = extract_proxies(line)
        if direct:
            add(direct)
        elif re.match(r"https?://", line, re.I):
            urls.append(line)

    if urls:
        sem = asyncio.Semaphore(8)
        texts = await asyncio.gather(*[fetch_source(i + 1, u, sem) for i, u in enumerate(urls)])
        for t in texts:
            if t:
                add(extract_proxies(t))
    logger.info(f"✅ {len(proxies)} پروکسی یکتا استخراج شد.")
    return proxies


# ============================== تست اتصال ==============================
async def resolve_host(server: str, port: int, sem: asyncio.Semaphore) -> Optional[str]:
    try:
        ipaddress.ip_address(server)
        return server
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    async with sem:
        try:
            infos = await asyncio.wait_for(
                loop.getaddrinfo(server, port, type=socket.SOCK_STREAM), DNS_TIMEOUT)
        except Exception:
            return None
    v4 = [i[4][0] for i in infos if i[0] == socket.AF_INET]
    cand = (v4 or [i[4][0] for i in infos])
    if not cand:
        return None
    ip = cand[0]
    return ip if is_valid_host(ip) else None


async def tcp_probe(ip: str, port: int, timeout: float) -> Optional[float]:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
    except Exception:
        return None
    ms = (loop.time() - t0) * 1000
    try:
        w.close()
        await asyncio.wait_for(w.wait_closed(), 1.0)
    except Exception:
        pass
    return ms


async def test_proxy(p: ProxyLink, sem_dns: asyncio.Semaphore, sem_tcp: asyncio.Semaphore) -> bool:
    ip = await resolve_host(p.server, p.port, sem_dns)
    if not ip:
        return False
    p.ip = ip
    async with sem_tcp:
        first = await tcp_probe(ip, p.port, TCP_TIMEOUT)
    p.attempts = 1
    if first is None:
        return False
    p.latencies.append(first)
    for _ in range(EXTRA_SAMPLES):
        await asyncio.sleep(0.2)
        async with sem_tcp:
            ms = await tcp_probe(ip, p.port, TCP_TIMEOUT)
        p.attempts += 1
        if ms is not None:
            p.latencies.append(ms)
    return len(p.latencies) >= MIN_SUCCESS


async def test_all(proxies: List[ProxyLink]) -> List[ProxyLink]:
    logger.info(f"🧪 تست اتصال TCP (۳ نمونه برای هر پروکسی) روی {len(proxies)} پروکسی...")
    sem_dns, sem_tcp = asyncio.Semaphore(MAX_DNS), asyncio.Semaphore(MAX_TCP)
    results = await asyncio.gather(*[test_proxy(p, sem_dns, sem_tcp) for p in proxies])
    alive, seen = [], set()
    for p, ok in zip(proxies, results):
        if ok and p.key not in seen:
            seen.add(p.key)
            alive.append(p)
    logger.info(f"✅ {len(alive)} پروکسی زنده از {len(proxies)}.")
    return alive


# ============================== امتیازدهی و انتخاب ==============================
KIND_BASE = {"faketls": 1000, "padded": 420, "plain": 300, "unknown": 250}


def compute_score(p: ProxyLink, history: dict, recent: set) -> float:
    s = float(KIND_BASE.get(p.kind, 250))
    if p.port == 443:
        s += 120
    s -= min(p.median, 1500) * 0.40
    s -= min(p.jitter, 800) * 0.30
    s += 60 * (len(p.latencies) / max(1, p.attempts))
    h = history.get(p.hid)
    if h:
        s += min(int(h.get("alive", 0)), 10) * 10
    if p.hid in recent:
        s -= RECENT_PENALTY
    return s


def select_diverse(ranked: List[ProxyLink], n: int, per_subnet: int) -> List[ProxyLink]:
    chosen: List[ProxyLink] = []
    counts: Dict[str, int] = defaultdict(int)
    for p in ranked:
        sub = p.subnet()
        if counts[sub] >= per_subnet:
            continue
        chosen.append(p)
        counts[sub] += 1
        if len(chosen) >= n:
            return chosen
    for p in ranked:                      # اگر کم آمد، سقف زیرشبکه را نادیده بگیر
        if len(chosen) >= n:
            break
        if all(p is not c for c in chosen):
            chosen.append(p)
    return chosen


# ============================== وضعیت بین اجراها (state.json) ==============================
def load_state() -> dict:
    default = {"version": 1, "history": {}, "posted": [], "recent_images": [],
               "recent_texts": [], "recent_headers": [], "runs": 0}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        pass
    return default


def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except OSError as e:
        logger.warning(f"ذخیرهٔ state ناموفق: {e}")


def update_history(state: dict, tested: List[ProxyLink], alive: List[ProxyLink]) -> None:
    now = int(time.time())
    hist = state["history"]
    alive_ids = {p.hid for p in alive}
    for p in alive:
        h = hist.get(p.hid, {"alive": 0})
        h["alive"] = int(h.get("alive", 0)) + 1
        h["last"] = now
        hist[p.hid] = h
    for p in tested:
        if p.hid not in alive_ids and p.hid in hist:
            hist[p.hid]["alive"] = 0
    cutoff = now - 14 * 86400
    for k in [k for k, v in hist.items() if int(v.get("last", 0)) < cutoff]:
        del hist[k]
    if len(hist) > 4000:
        for k, _ in sorted(hist.items(), key=lambda kv: kv[1].get("last", 0))[:len(hist) - 4000]:
            del hist[k]


# ============================== عکس و متن چرخشی ==============================
DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1543722530-d2c3201371e7?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=1280&auto=format&fit=crop",
]

# {n}: تعداد پروکسی زنده ، {fake}: تعداد Fake-TLS در منتخب‌ها
DEFAULT_HEADERS = [
    "⚡️ <b>پروکسی‌های تازهٔ MTProto، مرتب‌شده بر اساس تأخیر و پایداری</b>",
    "🚀 <b>گزیدهٔ پروکسی‌های پرسرعت تلگرام</b>",
    "🛡 <b>{fake} پروکسی Fake-TLS در میان منتخب‌های این ساعت</b>",
    "💎 <b>{n} پروکسی زنده بررسی شد؛ این‌ها بهترین‌ها هستند</b>",
    "🌟 <b>پروکسی‌های گلچین‌شدهٔ این ساعت</b>",
    "✨ <b>اتصال سریع به تلگرام با پروکسی‌های امتیازدار</b>",
    "📡 <b>بروزرسانی تازهٔ پروکسی‌های MTProto</b>",
    "🔥 <b>منتخب پروکسی‌ها؛ آمادهٔ اتصال</b>",
]

DEFAULT_TEXTS = [
    # شعر (متن‌های کلاسیک فارسی)
    "🌿 «بنی‌آدم اعضای یکدیگرند / که در آفرینش ز یک گوهرند» — سعدی",
    "🌿 «چو عضوی به درد آورد روزگار / دگر عضوها را نماند قرار» — سعدی",
    "🌟 «یوسف گم‌گشته بازآید به کنعان غم مخور / کلبهٔ احزان شود روزی گلستان غم مخور» — حافظ",
    "📖 «توانا بود هر که دانا بود / ز دانش دل پیر برنا بود» — فردوسی",
    "🌌 «هر که را جامه ز عشقی چاک شد / او ز حرص و عیب کلی پاک شد» — مولوی",
    "🕊 «در نومیدی بسی امید است / پایان شب سیه سپید است»",
    # جمله‌های انگیزشی
    "✨ امید، نوری است که حتی در تاریک‌ترین شب‌ها مسیر را روشن می‌کند.",
    "🌱 هر مانعی در مسیر، دعوتی است برای قوی‌تر شدن.",
    "🌊 آرامش، هنر رها کردن چیزهایی است که تحت کنترل ما نیستند.",
    "🚀 شجاعت یعنی با وجود ترس، رو به جلو قدم برداشتن.",
    "🌅 هر روز یک شروع تازه است.",
    "💫 قدم‌های کوچکِ هر روز، از جهش‌های بزرگِ گاه‌به‌گاه ماندگارترند.",
    # نکتهٔ علمی
    "🔭 نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه طول می‌کشد تا به زمین برسد.",
    "🪐 یک روز در سیاره زهره (یک دور چرخش به دور خود) طولانی‌تر از یک سال آن (یک دور گردش به دور خورشید) است.",
    "🐙 اختاپوس سه قلب دارد.",
    "🍯 عسل به‌دلیل رطوبت کم و اسیدی بودن، به‌سختی فاسد می‌شود.",
    "🌍 حدود ۷۱ درصد سطح زمین را آب پوشانده است.",
    "🧠 مغز انسان حدود ۲۰ درصد انرژی بدن را مصرف می‌کند.",
    "🌙 ماه هر سال حدود ۳٫۸ سانتی‌متر از زمین دورتر می‌شود.",
    "🐘 فیل‌ها از معدود جانورانی هستند که می‌توانند خودشان را در آینه تشخیص دهند.",
    "🌌 کهکشان راه شیری نسبت به تابش زمینهٔ کیهانی با سرعتی حدود ۲ میلیون کیلومتر بر ساعت حرکت می‌کند.",
    # نکتهٔ کاربردی
    "💡 اگر پروکسی وصل نشد، سراغ پروکسی بعدی بروید؛ پروکسی‌های عمومی ممکن است ساعتی عوض شوند.",
    "🔐 پروکسی عمومی فقط مسیر اتصال تلگرام را عوض می‌کند؛ مالک پروکسی آدرس IP شما را می‌بیند.",
    "📲 چند پروکسی را در تنظیمات تلگرام ذخیره کنید تا اگر یکی قطع شد، سریع‌تر به بعدی بروید.",
    "⚙️ مسیر افزودن: تنظیمات ← داده‌ها و حافظه ← تنظیمات پروکسی.",
]


def load_pools() -> Dict[str, List[str]]:
    pools = {"images": list(DEFAULT_IMAGES), "texts": list(DEFAULT_TEXTS), "headers": list(DEFAULT_HEADERS)}
    if ROTATION_FILE.is_file():
        try:
            data = json.loads(ROTATION_FILE.read_text(encoding="utf-8"))
            replace = bool(data.get("replace"))
            for k in pools:
                extra = [x.strip() for x in data.get(k, []) if isinstance(x, str) and x.strip()]
                if extra:
                    pools[k] = extra if replace else pools[k] + [x for x in extra if x not in pools[k]]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"خواندن rotation.json ناموفق بود: {e}")
    return pools


def pick_rotating(pool: List[str], recent: List[str], keep: int) -> str:
    candidates = [x for x in pool if x not in recent] or pool
    choice = random.choice(candidates)
    recent.append(choice)
    del recent[:-max(1, min(keep, len(pool) - 1)) if len(pool) > 1 else None]
    return choice


def image_ok(url: str) -> bool:
    status, hdrs, _ = http_request(url, "HEAD", None, UA, 12)
    if status in (403, 405, 501):
        status, hdrs, _ = http_request(url, "GET", None, {**UA, "Range": "bytes=0-1023"}, 12, 2048)
    ctype = next((v for k, v in hdrs.items() if k.lower() == "content-type"), "")
    return status in (200, 206) and ctype.lower().startswith("image/")


def pick_valid_image(pool: List[str], recent: List[str]) -> Optional[str]:
    tried: List[str] = []
    for _ in range(min(5, len(pool))):
        cand = [x for x in pool if x not in recent and x not in tried] or [x for x in pool if x not in tried]
        if not cand:
            break
        url = random.choice(cand)
        tried.append(url)
        if image_ok(url):
            recent.append(url)
            keep = max(1, min(6, len(pool) - 1))
            del recent[:-keep]
            return url
        logger.warning("⚠️ یک عکس چرخشی در دسترس نبود؛ عکس بعدی امتحان می‌شود.")
    return None


# ============================== ساخت پست و کپشن ==============================
def inline_keyboard() -> dict:
    share = ("https://t.me/share/url?url=" + quote(CHANNEL_LINK, safe="") + "&text=" + quote(SHARE_TEXT))
    return {"inline_keyboard": [
        [{"text": "📢 کانال رسمی", "url": CHANNEL_LINK},
         {"text": "💬 گروه چت و گفت‌وگو", "url": GROUP_LINK}],
        [{"text": "👥 معرفی کانال به دوستان", "url": share}],
    ]}


def visible_len(s: str) -> int:
    return len(html.unescape(re.sub(r"<[^>]+>", "", s)))


def link_label(p: ProxyLink) -> str:
    if LINK_STYLE == "ping":
        return f"پروکسی·{int(p.median)}ms"
    return "پروکسی"


def build_rows(proxies: List[ProxyLink], fmt: str) -> str:
    tags = []
    for p in proxies:
        url = p.http_url if fmt == "http" else p.tg_url
        tags.append(f'<a href="{html.escape(url, quote=True)}">{link_label(p)}</a>')
    rows: List[str] = []
    if tags[:2]:
        rows.append(" | ".join(tags[:2]))
    i = 2
    while i < len(tags):
        rows.append(" | ".join(tags[i:i + 3]))
        i += 3
    return "\n".join(rows)


def build_caption(proxies: List[ProxyLink], fmt: str, header: str, text: str,
                  ok_count: int, total: int) -> str:
    time_str, jalali, hour = tehran_strings()
    label = ("لینک‌های MTProto (باز شدن با t.me)" if fmt == "http"
             else "لینک‌های tg (باز شدن مستقیم در برنامه)")
    rows = build_rows(proxies, fmt)
    footer = (
        f"🧪 تست اتصال TCP از {html.escape(TEST_LABEL)}: <b>{ok_count}</b> زنده از {total}\n"
        f"🕒 {time_str} (تهران) | 📅 {jalali}\n"
        f"🔥 {CHANNEL_ID}\n"
        f"💬 <a href=\"{GROUP_LINK}\">سوپرگروه چت و گفت‌وگو</a>"
    )
    body_text = html.escape(text, quote=False)

    def assemble(with_text: bool) -> str:
        parts = [f"{greeting(hour)}\n{header}"]
        if with_text:
            parts.append(body_text)
        parts.append(f"👇 <b>{label}:</b>\n{rows}")
        parts.append(footer)
        return "\n\n".join(parts)

    cap = assemble(True)
    if visible_len(cap) > 1024:
        cap = assemble(False)
    return cap


def kind_counts(proxies: List[ProxyLink]) -> int:
    return sum(1 for p in proxies if p.is_faketls)


# ============================== فایل‌ها ==============================
def save_files(top_tg: List[ProxyLink], top_http: List[ProxyLink]) -> None:
    Path(FILE_TG).write_text("\n".join(p.tg_url for p in top_tg) + "\n", encoding="utf-8")
    Path(FILE_HTTP).write_text("\n".join(p.http_url for p in top_http) + "\n", encoding="utf-8")
    logger.info(f"💾 فایل‌ها ذخیره شد: {FILE_TG} ({len(top_tg)}) و {FILE_HTTP} ({len(top_http)}).")


def file_caption(n: int, fake: int, fmt: str, ok_count: int, total: int) -> str:
    time_str, jalali, _ = tehran_strings()
    kind = "tg://" if fmt == "tg" else "t.me (وب)"
    return (
        f"📁 <b>فایل جامع {n} پروکسی MTProto — لینک {kind}</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"⚡️ تعداد: <b>{n}</b> | Fake-TLS: <b>{fake}</b>\n"
        f"🧪 تست اتصال TCP از {html.escape(TEST_LABEL)}: <b>{ok_count}</b> زنده از {total}\n"
        "↕️ مرتب‌شده بر اساس امتیاز (نوع سکرت، تأخیر، پایداری)\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"🕒 {time_str} (تهران) | 📅 {jalali}\n"
        f"👉🆔 {CHANNEL_ID}"
    )


# ============================== تلگرام ==============================
def encode_multipart(fields: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]]) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode("utf-8")
    for k, (fname, data, ctype) in files.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                f'Content-Type: {ctype}\r\n\r\n').encode("utf-8")
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def tg_call(method: str, payload: Optional[dict] = None, fields: Optional[Dict[str, str]] = None,
            files: Optional[Dict[str, Tuple[str, bytes, str]]] = None, timeout: float = 45) -> dict:
    url = f"{API_BASE}/bot{BOT_TOKEN}/{method}"
    res: dict = {"ok": False, "description": "no attempt"}
    for attempt in range(4):
        if files is not None:
            body, ctype = encode_multipart(fields or {}, files)
        else:
            body, ctype = json.dumps(payload or {}).encode("utf-8"), "application/json"
        status, _, raw = http_request(url, "POST", body, {"Content-Type": ctype}, timeout)
        try:
            res = json.loads(raw.decode("utf-8", "ignore"))
        except Exception:
            res = {"ok": False, "description": f"HTTP {status}: {mask(raw[:160].decode('utf-8', 'ignore'))}"}
        if res.get("ok"):
            return res
        retry = (res.get("parameters") or {}).get("retry_after")
        if status == 429 and retry and attempt < 3:
            time.sleep(min(int(retry) + 1, 30))
            continue
        break
    return res


async def send_photo_post(fmt: str, caption: str, image: Optional[str]) -> bool:
    kb = inline_keyboard()
    if image:
        sep = "&" if "?" in image else "?"
        res = await asyncio.to_thread(tg_call, "sendPhoto", {
            "chat_id": CHAT_ID, "photo": f"{image}{sep}t={int(time.time())}",
            "caption": caption, "parse_mode": "HTML", "reply_markup": kb})
        if res.get("ok"):
            return True
        logger.warning(f"⚠️ sendPhoto ({fmt}) ناموفق: {mask(str(res.get('description')))}")
    res = await asyncio.to_thread(tg_call, "sendMessage", {
        "chat_id": CHAT_ID, "text": caption, "parse_mode": "HTML",
        "disable_web_page_preview": True, "reply_markup": kb})
    if res.get("ok"):
        return True
    logger.error(f"❌ sendMessage ({fmt}) ناموفق: {mask(str(res.get('description')))}")
    return False


async def send_file(path: str, filename: str, caption: str) -> bool:
    data = Path(path).read_bytes()
    res = await asyncio.to_thread(
        tg_call, "sendDocument", None,
        {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML",
         "reply_markup": json.dumps(inline_keyboard())},
        {"document": (filename, data, "text/plain")}, 60)
    if res.get("ok"):
        return True
    logger.error(f"❌ sendDocument ({filename}) ناموفق: {mask(str(res.get('description')))}")
    return False


# ============================== برنامهٔ اصلی ==============================
def read_sources(path: Optional[str]) -> List[str]:
    raw = Path(path).read_text(encoding="utf-8") if path else os.environ.get("PROXY_SOURCES", "")
    return [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]


async def main(args: argparse.Namespace) -> int:
    logger.info("🎬 شروع چرخهٔ جمع‌آوری، تست و انتخاب...")
    state = load_state()
    state["runs"] = int(state.get("runs", 0)) + 1

    proxies = await collect_all(read_sources(args.sources_file))
    if not proxies:
        logger.error("❌ هیچ پروکسی‌ای دریافت نشد.")
        return 2
    total = len(proxies)

    alive = await test_all(proxies)
    update_history(state, proxies, alive)
    if len(alive) < MIN_POST:
        logger.error(f"❌ فقط {len(alive)} پروکسی زنده؛ پستی ارسال نمی‌شود.")
        save_state(state)
        return 2

    recent = {h for run in state["posted"][-3:] for h in run}
    for p in alive:
        p.score = compute_score(p, state["history"], recent)
    ranked = sorted(alive, key=lambda p: p.score, reverse=True)

    top_http = select_diverse(ranked, TOP_LINKS, PER_SUBNET_LINKS)
    if DISTINCT_SETS:
        rest = [p for p in ranked if all(p is not q for q in top_http)]
        top_tg = select_diverse(rest, TOP_LINKS, PER_SUBNET_LINKS) or top_http
    else:
        top_tg = top_http
    pool_file = select_diverse(ranked, TOP_FILE, PER_SUBNET_FILE)
    file_http = top_http + [p for p in pool_file if all(p is not q for q in top_http)][:TOP_FILE - len(top_http)]
    file_tg = top_tg + [p for p in pool_file if all(p is not q for q in top_tg)][:TOP_FILE - len(top_tg)]
    logger.info(f"🎯 انتخاب شد: {len(top_http)} لینک در هر پست | {len(file_http)} در هر فایل | "
                f"Fake-TLS در منتخب‌ها: {kind_counts(top_http)}")

    save_files(file_tg, file_http)

    pools = load_pools()
    state["posted"] = (state["posted"] + [[p.hid for p in top_http + top_tg]])[-3:]

    def prepare(fmt: str, group: List[ProxyLink]) -> Tuple[str, Optional[str]]:
        header = pick_rotating(pools["headers"], state["recent_headers"], 4)
        header = header.format(n=len(alive), fake=kind_counts(group)) if "{" in header else header
        text = pick_rotating(pools["texts"], state["recent_texts"], 12)
        image = None if args.dry_run else pick_valid_image(pools["images"], state["recent_images"])
        return build_caption(group, fmt, header, text, len(alive), total), image

    cap_http, img_http = prepare("http", top_http)
    cap_tg, img_tg = prepare("tg", top_tg)

    if args.dry_run or not BOT_TOKEN or not CHAT_ID:
        why = "--dry-run" if args.dry_run else "BOT_TOKEN یا CHAT_ID تنظیم نیست"
        logger.info(f"ℹ️ ارسال انجام نشد ({why}). پیش‌نمایش پست MTProto:")
        print(re.sub(r"<[^>]+>", "", html.unescape(cap_http)))
        save_state(state)
        return 0

    ok = True
    ok &= await send_photo_post("http", cap_http, img_http)
    await asyncio.sleep(2)
    ok &= await send_file(FILE_HTTP, "PROXIES_HTTP_TOP100.txt",
                          file_caption(len(file_http), kind_counts(file_http), "http", len(alive), total))
    await asyncio.sleep(2)
    ok &= await send_photo_post("tg", cap_tg, img_tg)
    await asyncio.sleep(2)
    ok &= await send_file(FILE_TG, "PROXIES_TG_TOP100.txt",
                          file_caption(len(file_tg), kind_counts(file_tg), "tg", len(alive), total))

    save_state(state)
    logger.info("🏁 پایان." if ok else "🏁 پایان، ولی بعضی ارسال‌ها ناموفق بود (لاگ بالا را ببینید).")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Telegram MTProto Proxy Collector v6")
    ap.add_argument("--dry-run", action="store_true", help="فقط جمع‌آوری و تست؛ چیزی به تلگرام نفرست")
    ap.add_argument("--sources-file", help="به‌جای PROXY_SOURCES، منابع را از این فایل بخوان")
    return ap.parse_args()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main(parse_args())))
    except KeyboardInterrupt:
        logger.info("توقف دستی.")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        logger.critical(f"خطای سیستمی: {mask(str(exc))}", exc_info=True)
        sys.exit(1)
