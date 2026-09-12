#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Telegram Proxy Collector v1.0
جمع‌آوری، حذف تکراری و ارسال خودکار پروکسی‌های MTProto تلگرام به کانال.

نحوه‌ی کار:
  1) از ۱۰ منبع، لینک‌های پروکسی (t.me/proxy?server=...&port=...&secret=...) را می‌گیرد.
  2) بر اساس (سرور، پورت، سکرت) موارد تکراری را حذف می‌کند.
  3) با یک اتصال TCP سریع، پروکسی‌های از کار افتاده را کنار می‌گذارد.
  4) نتیجه را در فایلی به نام TELEGRAM_PROXY_SUB_TXT می‌نویسد.
  5) همان فایل را با کپشن به کانال تلگرام ارسال می‌کند.

این اسکریپت با GitHub Actions هر ۴ ساعت یک‌بار (۶ بار در روز) اجرا می‌شود.
"""

import asyncio
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs

import aiohttp

# =============================================================================
# تنظیمات
# =============================================================================

SOURCES = [
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no1.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no2.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no3.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no4.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no5.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no6.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no7.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no8.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no9.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/TELEGRAM_PROXY_SUB/refs/heads/main/telegram_proxy_no10.txt",
]

OUTPUT_FILE = "TELEGRAM_PROXY_SUB_TXT"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"

# همان Secretهایی که از قبل برای پروژه‌ی V2Ray در گیت‌هاب ثبت کرده‌اید — نیازی
# به ساخت Secret جدید نیست.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

FETCH_TIMEOUT = 10.0
TCP_TIMEOUT = 4.0
MAX_CONCURRENT_TESTS = 60

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")


# =============================================================================
# مدل داده
# =============================================================================

@dataclass(frozen=True)
class ProxyLink:
    server: str
    port: int
    secret: str
    raw: str


def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    """یک خط را به یک ProxyLink معتبر تبدیل می‌کند، یا در صورت نامعتبر بودن None."""
    line = line.strip()
    if not line:
        return None
    m = PROXY_RE.search(line)
    if not m:
        return None
    url = m.group(0)
    try:
        # urlparse با اسکیم tg:// مشکل دارد، پس آن را موقتاً https می‌کنیم
        normalized = url if url.startswith("http") else "https://t.me/proxy" + url[url.index("?"):]
        parsed = urlparse(normalized)
        qs = parse_qs(parsed.query)
        server = (qs.get("server", [""])[0] or "").strip().rstrip(".").lower()
        port_raw = (qs.get("port", [""])[0] or "").strip()
        secret = (qs.get("secret", [""])[0] or "").strip()
        if not server or not port_raw.isdigit() or not secret:
            return None
        port = int(port_raw)
        if not (0 < port < 65536):
            return None
        # همیشه لینک را به فرمت استاندارد و یکسان برمی‌گردانیم
        clean_url = f"https://t.me/proxy?server={server}&port={port}&secret={secret}"
        return ProxyLink(server=server, port=port, secret=secret, raw=clean_url)
    except Exception:
        return None


# =============================================================================
# جمع‌آوری از منابع
# =============================================================================

async def fetch_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT)) as r:
            if r.status != 200:
                print(f"   ⚠️ منبع پاسخ نداد ({r.status}): {url}")
                return []
            text = await r.text(errors="ignore")
            return text.splitlines()
    except Exception as e:
        print(f"   ⚠️ خطا در دریافت منبع: {url} -> {e}")
        return []


async def collect_all() -> List[ProxyLink]:
    async with aiohttp.ClientSession() as session:
        all_lines = await asyncio.gather(*[fetch_source(session, u) for u in SOURCES])

    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []
    for lines in all_lines:
        for line in lines:
            p = parse_proxy_line(line)
            if not p:
                continue
            key = (p.server, p.port, p.secret)
            if key in seen:
                continue
            seen.add(key)
            proxies.append(p)
    return proxies


# =============================================================================
# تست زنده بودن (اتصال سریع TCP)
# =============================================================================
# توجه: این فقط باز بودن پورت را می‌سنجد، نه صحت کامل پروتکل MTProto —
# اما همین کافی است که پروکسی‌های کاملاً از کار افتاده حذف شوند.

async def tcp_alive(host: str, port: int, sem: asyncio.Semaphore) -> bool:
    async with sem:
        writer = None
        try:
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=TCP_TIMEOUT)
            return True
        except Exception:
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass


async def filter_alive(proxies: List[ProxyLink]) -> List[ProxyLink]:
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[tcp_alive(p.server, p.port, sem) for p in proxies])
    return [p for p, ok in zip(proxies, results) if ok]


# =============================================================================
# ارسال به تلگرام
# =============================================================================

async def send_to_telegram(file_path: str, count: int) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN یا CHAT_ID تنظیم نشده؛ فقط فایل ساخته شد، ارسال انجام نشد.")
        return

    caption = (
        "📡 <b>پروکسی‌های MTProto تلگرام</b>\n\n"
        f"📦 تعداد: <b>{count}</b> پروکسی زنده\n"
        "⏱ هر ۴ ساعت یک‌بار به‌روزرسانی می‌شود\n\n"
        "روی هر لینک داخل فایل بزنید تا مستقیم به تلگرام اضافه شود.\n\n"
        f"✨ منبع: {CHANNEL_LINK}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", CHAT_ID)
                data.add_field("caption", caption)
                data.add_field("parse_mode", "HTML")
                data.add_field(
                    "document", f,
                    filename=os.path.basename(file_path),
                    content_type="text/plain",
                )
                async with session.post(
                    url, data=data, timeout=aiohttp.ClientTimeout(total=30)
                ) as r:
                    res = await r.json()
                    if res.get("ok"):
                        print(f"✅ فایل با موفقیت به تلگرام ارسال شد ({count} پروکسی زنده).")
                    else:
                        print(f"❌ خطای تلگرام: {res.get('description')}")
    except Exception as e:
        print(f"❌ استثنا هنگام ارسال به تلگرام: {e}")


# =============================================================================
# اجرای اصلی
# =============================================================================

async def main() -> None:
    print("=" * 60)
    print("🚀 Telegram Proxy Collector — شروع")
    print("=" * 60)

    all_proxies = await collect_all()
    print(f"📥 مرحله ۱: {len(all_proxies)} پروکسی یکتا از {len(SOURCES)} منبع جمع شد.")

    alive = await filter_alive(all_proxies)
    print(f"🧪 مرحله ۲: {len(alive)} پروکسی زنده از {len(all_proxies)} تأیید شد.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(p.raw for p in alive))
    print(f"💾 مرحله ۳: فایل «{OUTPUT_FILE}» ساخته شد.")

    print("📤 مرحله ۴: ارسال به تلگرام...")
    await send_to_telegram(OUTPUT_FILE, len(alive))

    print("=" * 60)
    print("✅ پایان.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
