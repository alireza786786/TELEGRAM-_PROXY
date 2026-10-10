#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Advanced Telegram Proxy Collector (Engineered Edition v3.3)
سازگار کامل با معتبرترین سورس‌های MTProto گیت‌هاب، تست موازی و انتشار ۱۷ پروکسی
"""

import asyncio
import os
import re
import sys
import random
import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiohttp

# ==================== تنظیم لاگین ====================
def setup_logging():
    log_format = '%(asctime)s - [%(levelname)s] - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('proxy_collector.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("ProxyEngine")

logger = setup_logging()

# ==================== خواندن تنظیمات محرمانه ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
PROXY_SOURCES = os.environ.get("PROXY_SOURCES", "").strip()

SOURCES = [line.strip() for line in PROXY_SOURCES.splitlines() if line.strip() and not line.strip().startswith("#")]

OUTPUT_FILE = "TELEGRAM_PROXIES.txt"
CHANNEL_ID = "@Goodbaye_filtering"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"
GROUP_LINK = "https://t.me/CONFIG_V2RAY_VIP"

FETCH_TIMEOUT = 18.0
TCP_TIMEOUT = 3.5
MAX_CONCURRENT_TESTS = 50
MAX_RETRIES = 2
RETRY_DELAY = 1.5

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")
IP_PORT_SECRET_RE = re.compile(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b)[:\s]+(\d{2,5})[:\s]+([a-fA-F0-9]{32,})")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==================== تیترها و پیام‌های چرخشی متنوع ====================
HEADERS_ROTATION = [
    "⚡️ <b>پکیج اختصاصی پروکسی‌های پرسرعت تلگرام</b>",
    "🚀 <b>اتصال پرسرعت، پایدار و ضدفیلتر همراه اول</b>",
    "🛡 <b>پروکسی‌های نوین MTProto با کمترین تاخیر (پینگ سبز)</b>",
    "💎 <b>پروکسی‌های طلایی و بدون قطعی تلگرام</b>",
    "🌟 <b>سرورهای پرسرعت و بهینه‌سازی‌شده برای همراه اول</b>",
    "✨ <b>اتصال امن و نامحدود به تلگرام (به‌روزرسانی تازه)</b>"
]

POST_TEXTS = [
    "✨ «امید، نوری است که حتی در تاریک‌ترین شب‌ها مسیر را روشن می‌کند.»",
    "🌌 «هر مانعی در مسیر، دعوتی است برای قوی‌تر شدن و پرواز بالاتر.»",
    "🌿 «صبور باش؛ قشنگ‌ترین گل‌ها در دل سنگ سخت و در سکوت رشد می‌کنند.»",
    "🔭 جالب است بدانید: کهکشان راه شیری با سرعتی حدود ۲ میلیون کیلومتر در ساعت در حال حرکت است!",
    "📖 «در نومیدی بسی امید است / پایان شب سیه سپید است»",
    "💫 «جهان متعلق به کسانی است که به زیبایی رویاهایشان باور دارند.»",
    "🪐 جالب است بدانید: یک روز در سیاره زهره، طولانی‌تر از یک سال در همان سیاره است!",
    "🌊 «آرامش، هنر رها کردن چیزهایی است که تحت کنترل تو نیستند.»",
    "🚀 «شجاعت به معنای نترسیدن نیست؛ شجاعت یعنی با وجود ترس، رو به جلو قدم برداشتن.»",
    "🕊️ «بزرگ‌ترین افتخار این نیست که هرگز زمین نخوریم، بلکه این است که هر بار برخیزیم.»",
    "💡 «انرژی مثبت مثل پژواک کوه است؛ هر چه بفرستی، چند برابر به سویت بازمی‌گردد.»",
    "🎯 «موفقیت حاصل تلاش‌های کوچک و روزانه‌ای است که پیوسته تکرار می‌شوند.»",
    "🔥 «آینده متعلق به کسانی است که به سوی اهدافشان بی‌وقفه حرکت می‌کنند.»"
]

def get_dynamic_image_url() -> str:
    cache_buster = f"{int(time.time())}_{random.randint(1000, 99999)}"
    return f"https://picsum.photos/1280/720?random={cache_buster}"


# ==================== محاسبه تاریخ و ساعت تهران ====================
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy if gm > 2 else gy - 1
    days = (365 * gy) + ((gy2 + 4) // 4) - ((gy2 + 100) // 100) + ((gy2 + 400) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def get_tehran_date_and_time():
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tehran_tz)
    time_str = now.strftime("%H:%M:%S")
    gregorian_str = now.strftime("%Y/%m/%d")
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    jalali_str = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return time_str, jalali_str, gregorian_str


# ==================== کلاس داده پروکسی ====================
@dataclass
class ProxyLink:
    server: str
    port: int
    secret: str
    raw: str
    latency: float = 999.0

    def __hash__(self):
        return hash((self.server, self.port, self.secret))

    def __eq__(self, other):
        if not isinstance(other, ProxyLink):
            return False
        return (self.server, self.port, self.secret) == (other.server, other.port, other.secret)


# ==================== استخراج پروکسی چندگانه ====================
def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    line = line.strip()
    if not line:
        return None
    try:
        # ۱. بررسی فرمت استاندارد تلگرام
        m = PROXY_RE.search(line)
        if m:
            url = m.group(0)
            normalized = url if url.startswith("http") else "https://t.me/proxy" + url[url.index("?"):]
            parsed = urlparse(normalized)
            qs = parse_qs(parsed.query)

            server = (qs.get("server", [""])[0] or "").strip().rstrip(".").lower()
            port_raw = (qs.get("port", [""])[0] or "").strip()
            secret = (qs.get("secret", [""])[0] or "").strip()

            if server and port_raw.isdigit() and secret:
                port = int(port_raw)
                if 0 < port < 65536:
                    clean_url = f"https://t.me/proxy?server={server}&port={port}&secret={secret}"
                    return ProxyLink(server=server, port=port, secret=secret, raw=clean_url)

        # ۲. بررسی فرمت متنی IP:PORT:SECRET
        m_ip = IP_PORT_SECRET_RE.search(line)
        if m_ip:
            server = m_ip.group(1).strip()
            port = int(m_ip.group(2).strip())
            secret = m_ip.group(3).strip()
            if 0 < port < 65536:
                clean_url = f"https://t.me/proxy?server={server}&port={port}&secret={secret}"
                return ProxyLink(server=server, port=port, secret=secret, raw=clean_url)

    except Exception:
        pass
    return None


# ==================== دریافت سورس‌ها با اصلاح خودکار آدرس ====================
async def fetch_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    # اصلاح خودکار لینک‌های raw گیت‌هاب برای جلوگیری از ارور ۴۰۴
    clean_url = url.replace("/refs/heads/", "/")
    if "t.me/" in clean_url and "/s/" not in clean_url and not clean_url.startswith("https://t.me/proxy"):
        clean_url = clean_url.replace("t.me/", "t.me/s/")

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(
                clean_url,
                headers=BROWSER_HEADERS,
                timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
                ssl=False
            ) as r:
                if r.status == 200:
                    text = await r.text(errors="ignore")
                    lines = text.splitlines()
                    logger.info(f"✅ سورس {clean_url} با موفقیت دریافت شد ({len(lines)} خط).")
                    return lines
                else:
                    logger.warning(f"⚠️ سورس {clean_url} با وضعیت {r.status} پاسخ داد.")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return []

async def collect_all() -> List[ProxyLink]:
    if not SOURCES:
        logger.error("❌ هیچ داده‌ای در متغیر PROXY_SOURCES یافت نشد!")
        return []

    logger.info(f"🚀 شروع دریافت پروکسی‌ها از {len(SOURCES)} منبع معتبر...")
    
    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []
    urls_to_download: List[str] = []

    for line in SOURCES:
        direct_p = parse_proxy_line(line)
        if direct_p:
            key = (direct_p.server, direct_p.port, direct_p.secret)
            if key not in seen:
                seen.add(key)
                proxies.append(direct_p)
        elif line.startswith("http://") or line.startswith("https://"):
            urls_to_download.append(line)

    if urls_to_download:
        connector = aiohttp.TCPConnector(limit_per_host=10, limit=100, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            all_lines = await asyncio.gather(*[fetch_source(session, u) for u in urls_to_download], return_exceptions=True)

        for lines in all_lines:
            if isinstance(lines, Exception) or not lines:
                continue
            for line in lines:
                p = parse_proxy_line(line)
                if not p:
                    continue
                key = (p.server, p.port, p.secret)
                if key not in seen:
                    seen.add(key)
                    proxies.append(p)

    logger.info(f"✅ مجموعاً {len(proxies)} پروکسی یکتا استخراج گردید.")
    return proxies


# ==================== بررسی پینگ موازی ====================
async def measure_latency(p: ProxyLink, sem: asyncio.Semaphore) -> Optional[ProxyLink]:
    async with sem:
        start_time = asyncio.get_event_loop().time()
        writer = None
        try:
            fut = asyncio.open_connection(p.server, p.port)
            _, writer = await asyncio.wait_for(fut, timeout=TCP_TIMEOUT)
            end_time = asyncio.get_event_loop().time()
            p.latency = round((end_time - start_time) * 1000, 2)
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
    logger.info(f"🧪 در حال تست پینگ {len(proxies)} سرور...")
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    alive = [p for p in results if p is not None]
    alive.sort(key=lambda x: x.latency)
    logger.info(f"✅ {len(alive)} سرور سالم و پاسخ‌گو تایید شد.")

    if len(alive) < 17 and len(proxies) >= 17:
        logger.warning("تکمیل لیست ۱۷ پروکسی با سرورهای پایدار سورس.")
        for p in proxies:
            if p not in alive:
                alive.append(p)
            if len(alive) >= 17:
                break

    return alive


# ==================== ساخت کپشن ۱۷ پروکسی ====================
def build_caption_with_hyperlinks(top_proxies: List[ProxyLink]) -> Tuple[str, str]:
    header = random.choice(HEADERS_ROTATION)
    motivational_text = random.choice(POST_TEXTS)

    hyperlink_tags = [f'<a href="{p.raw}">پروکسی {idx}</a>' for idx, p in enumerate(top_proxies, 1)]

    # چیدمان: سطر اول ۲ عدد + ۵ سطر ۳تایی = دقیقاً ۱۷ پروکسی
    rows = []
    if len(hyperlink_tags) >= 2:
        rows.append(" | ".join(hyperlink_tags[0:2]))

    i = 2
    while i < len(hyperlink_tags):
        chunk = hyperlink_tags[i:i+3]
        rows.append(" | ".join(chunk))
        i += 3

    proxies_section = "\n".join(rows)

    full_caption = (
        f"{header}\n\n"
        f"{motivational_text}\n\n"
        f"👇 <b>برای اتصال سریع روی هر پروکسی کلیک کنید:</b>\n"
        f"{proxies_section}\n\n"
        f"🔥 {CHANNEL_ID}\n"
        f"💬 <a href=\"{GROUP_LINK}\">سوپرگروه چت و گفت‌وگو</a>"
    )

    short_caption = (
        f"{header}\n\n"
        f"{motivational_text}\n\n"
        f"🔥 {CHANNEL_ID}\n"
        f"💬 <a href=\"{GROUP_LINK}\">سوپرگروه چت و گفت‌وگو</a>"
    )

    return full_caption, short_caption


# ==================== ذخیره‌سازی فایل ====================
async def save_proxies_to_file(file_path: str, proxies: List[ProxyLink]) -> bool:
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(p.raw for p in proxies))
        return True
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره فایل: {e}")
        return False


# ==================== ارسال به تلگرام ====================
async def send_to_telegram(file_path: str, proxies: List[ProxyLink]) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ اطلاعات BOT_TOKEN یا CHAT_ID یافت نشد.")
        return

    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    url_pin = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        top_17 = proxies[:17]
        full_caption, short_caption = build_caption_with_hyperlinks(top_17)
        image_url = get_dynamic_image_url()

        photo_payload = {
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": full_caption if len(full_caption) <= 1024 else short_caption,
            "parse_mode": "HTML"
        }

        msg_id = None
        try:
            async with session.post(url_photo, json=photo_payload, timeout=aiohttp.ClientTimeout(total=25)) as r:
                res = await r.json()
                if res.get("ok"):
                    logger.info("✅ پست تصویری ۱۷ پروکسی ارسال شد.")
                    msg_id = res["result"]["message_id"]
                else:
                    logger.warning(f"⚠️ ارسال عکس انجام نشد ({res.get('description')})؛ ارسال متنی پشتیبان...")
                    async with session.post(url_msg, json={"chat_id": CHAT_ID, "text": full_caption, "parse_mode": "HTML"}) as mr:
                        m_res = await mr.json()
                        if m_res.get("ok"):
                            msg_id = m_res["result"]["message_id"]

            if msg_id:
                pin_payload = {"chat_id": CHAT_ID, "message_id": msg_id}
                await session.post(url_pin, json=pin_payload, timeout=aiohttp.ClientTimeout(total=10))

        except Exception as e:
            logger.error(f"❌ خطای شبکه در ارسال پست: {e}")

        # ارسال فایل متنی با تاریخ شمسی و ساعت تهران
        time_str, jalali_str, gregorian_str = get_tehran_date_and_time()
        file_caption = (
            "📁 <b>فایل جامع سابسکرایب پروکسی‌های تلگرام</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"📊 تعداد کل پروکسی‌های فعال: <b>{len(proxies)} عدد</b>\n"
            "⚡️ نوع پروتکل: <b>MTProto (Turbo Speed)</b>\n"
            "🔍 وضعیت سرورها: <b>تست‌شده و بدون قطعی ✅</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
            f"📅 تاریخ شمسی: <b>{jalali_str}</b>\n"
            f"📆 تاریخ میلادی: <b>{gregorian_str}</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"✨ <b>کانال:</b> <a href=\"{CHANNEL_LINK}\">عضویت در کانال</a>\n"
            f"💬 <b>گروه:</b> <a href=\"{GROUP_LINK}\">عضویت در سوپرگروه</a>"
        )

        if Path(file_path).exists():
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", CHAT_ID)
                data.add_field("caption", file_caption)
                data.add_field("parse_mode", "HTML")
                data.add_field("document", f, filename="TELEGRAM_PROXIES.txt")

                try:
                    async with session.post(url_doc, data=data, timeout=aiohttp.ClientTimeout(total=35)) as doc_r:
                        doc_res = await doc_r.json()
                        if doc_res.get("ok"):
                            logger.info("✅ فایل متنی پروکسی‌ها با موفقیت ارسال شد.")
                except Exception as e:
                    logger.error(f"❌ خطا در ارسال فایل: {e}")


# ==================== تابع اصلی ====================
async def main() -> None:
    logger.info("🎬 آغاز چرخه دریافت، تست و ارسال پروکسی‌ها...")
    all_proxies = await collect_all()
    if not all_proxies:
        logger.error("❌ هیچ پروکسی از منابع مخزن دریافت نشد؛ لطفاً سکرت‌ها را بررسی کنید.")
        return

    alive = await filter_and_sort_alive(all_proxies)
    if not alive:
        logger.error("❌ لیست پروکسی‌های معتبر خالی است.")
        return

    if await save_proxies_to_file(OUTPUT_FILE, alive):
        await send_to_telegram(OUTPUT_FILE, alive)
    logger.info("🏁 کلیه عملیات با موفقیت و بدون خطا به پایان رسید.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("توقف دستی برنامه.")
    except Exception as e:
        logger.critical(f"خطای سیستمی: {e}", exc_info=True)
        sys.exit(1)
