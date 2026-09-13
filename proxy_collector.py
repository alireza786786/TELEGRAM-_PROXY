#!/usr/init/env python3
# -*- coding: utf-8 -*-
"""
🚀 Telegram Proxy Collector v2.0
جمع‌آوری، تست سرعت (پینگ واقعی)، مرتب‌سازی، ارسال فایل و ۳ پروکسی برتر با دکمه شیشه‌ای و قابلیت پین خودکار.
"""

import asyncio
import os
import re
import random
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs

import aiohttp

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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

FETCH_TIMEOUT = 10.0
TCP_TIMEOUT = 3.0
MAX_CONCURRENT_TESTS = 60

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")

@dataclass
class ProxyLink:
    server: str
    port: int
    secret: str
    raw: str
    latency: float = 999.0  # سرعت پاسخ‌دهی (پینگ)

def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    line = line.strip()
    if not line:
        return None
    m = PROXY_RE.search(line)
    if not m:
        return None
    url = m.group(0)
    try:
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
        clean_url = f"https://t.me/proxy?server={server}&port={port}&secret={secret}"
        return ProxyLink(server=server, port=port, secret=secret, raw=clean_url)
    except Exception:
        return None

async def fetch_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT)) as r:
            if r.status != 200:
                return []
            text = await r.text(errors="ignore")
            return text.splitlines()
    except Exception:
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

async def measure_latency(p: ProxyLink, sem: asyncio.Semaphore) -> Optional[ProxyLink]:
    """تست TCP همراه با محاسبه دقیق سرعت (Latency)"""
    async with sem:
        start_time = asyncio.get_event_loop().time()
        writer = None
        try:
            fut = asyncio.open_connection(p.server, p.port)
            _, writer = await asyncio.wait_for(fut, timeout=TCP_TIMEOUT)
            end_time = asyncio.get_event_loop().time()
            p.latency = round((end_time - start_time) * 1000, 2)  # تبدیل به میلی‌ثانیه
            return p
        except Exception:
            return None
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

async def filter_and_sort_alive(proxies: List[ProxyLink]) -> List[ProxyLink]:
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    # فیلتر پروکسی‌های سالم و مرتب‌سازی آن‌ها بر اساس کمترین پینگ (سریع‌ترین‌ها در ابتدا)
    alive_proxies = [p for p in results if p is not None]
    alive_proxies.sort(key=lambda x: x.latency)
    return alive_proxies

async def send_to_telegram(file_path: str, proxies: List[ProxyLink]) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN یا CHAT_ID تنظیم نشده است.")
        return

    count = len(proxies)
    
    caption = (
        "📡 <b>پروکسی‌های MTProto تلگرام</b>\n\n"
        f"📦 تعداد کل پروکسی‌های زنده: <b>{count}</b>\n"
        "⏱ هر ۴ ساعت یک‌بار به‌روزرسانی می‌شود\n\n"
        f"✨ منبع: {CHANNEL_LINK}"
    )

    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_pin = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"

    try:
        async with aiohttp.ClientSession() as session:
            # ۱. ارسال فایل سابسکرایب
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
                async with session.post(url_doc, data=data, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    res = await r.json()
                    if res.get("ok"):
                        print("✅ فایل پروکسی‌ها با موفقیت به تلگرام ارسال شد.")

            # ۲. انتخاب ۳ پروکسی برتر و سریع‌تر برای دکمه‌های شیشه‌ای
            if proxies:
                # ۳ پروکسی اول از لیست مرتب‌شده، سریع‌ترین‌ها هستند
                top_proxies = proxies[:3]
                
                inline_keyboard = []
                text_lines = ["🚀 <b>۳ پروکسی فوق‌سریع برتر (تست‌شده):</b>\n"]
                
                for i, p in enumerate(top_proxies, 1):
                    text_lines.append(f"پروکسی {i} (پینگ: {p.latency}ms):\n<code>{p.raw}</code>\n")
                    inline_keyboard.append([
                        {"text": f"⚡ اتصال سریع به پروکسی {i} ({int(p.latency)}ms)", "url": p.raw}
                    ])

                payload = {
                    "chat_id": CHAT_ID,
                    "text": "\n".join(text_lines),
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": inline_keyboard
                    }
                }

                async with session.post(url_msg, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    res = await r.json()
                    if res.get("ok"):
                        print("✅ پیام همراه با ۳ دکمه شیشه‌ای پرسرعت ارسال شد.")
                        
                        # ۳. پین کردن خودکار پیام دکمه‌دار در کانال
                        message_id = res["result"]["message_id"]
                        pin_payload = {
                            "chat_id": CHAT_ID,
                            "message_id": message_id,
                            "disable_notification": False
                        }
                        async with session.post(url_pin, json=pin_payload, timeout=aiohttp.ClientTimeout(total=15)) as pin_res:
                            pin_json = await pin_res.json()
                            if pin_json.get("ok"):
                                print("📌 پیام پروکسی‌های برتر با موفقیت در کانال پین شد.")
                            else:
                                print(f"⚠️ امکان پین کردن پیام نبود (ربات باید دسترسی Pin Messages داشته باشد): {pin_json.get('description')}")
                    else:
                        print(f"❌ خطای ارسال پیام دکمه‌دار: {res.get('description')}")

    except Exception as e:
        print(f"❌ خطا در ارتباط با تلگرام: {e}")

async def main() -> None:
    print("=" * 60)
    print("🚀 Telegram Proxy Collector v2.0 — شروع")
    print("=" * 60)

    all_proxies = await collect_all()
    print(f"📥 {len(all_proxies)} پروکسی یکتا جمع‌آوری شد.")

    # تست و مرتب‌سازی هوشمند بر اساس سرعت (پینگ)
    alive = await filter_and_sort_alive(all_proxies)
    print(f"🧪 {len(alive)} پروکسی زنده تأیید و بر اساس سرعت مرتب شدند.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(p.raw for p in alive))
    print(f"💾 فایل «{OUTPUT_FILE}» ساخته شد.")

    await send_to_telegram(OUTPUT_FILE, alive)
    print("=" * 60)
    print("✅ پایان.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
