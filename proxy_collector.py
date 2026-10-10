#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Advanced Telegram Proxy Collector (Speed-Oriented v4.0)
پایش دقیق سرعت، حذف قطعی سرورهای خاموش، انتشار ۱۷ هایپرلینک پرسرعت و ۲ فایل مجزا با ۳ دکمه شیشه‌ای
"""

import asyncio
import json
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

# ==================== تنظیم لاگ سیستم ====================
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

# استخراج سورس‌ها مستقیماً از سکرت مخزن شما
SOURCES = [line.strip() for line in PROXY_SOURCES.splitlines() if line.strip() and not line.strip().startswith("#")]

FILE_TG = "PROXIES_TG_FORMAT.txt"
FILE_HTTP = "PROXIES_HTTP_FORMAT.txt"

CHANNEL_ID = "@Goodbaye_filtering"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"
GROUP_LINK = "https://t.me/CONFIG_V2RAY_VIP"

FETCH_TIMEOUT = 18.0
TCP_TIMEOUT = 2.5       # تایم‌اوت سخت‌گیرانه برای حذف سرورهای قطعی و ضعیف
MAX_CONCURRENT_TESTS = 60
MAX_RETRIES = 2
RETRY_DELAY = 1.5

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")
IP_PORT_SECRET_RE = re.compile(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b)[:\s]+(\d{2,5})[:\s]+([a-fA-F0-9]{32,})")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==================== ۳ دکمه شیشه‌ای مصوب و پین‌شده ====================
INLINE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "📢 کانال رسمی", "url": CHANNEL_LINK},
            {"text": "💬 گروه چت و گفت‌وگو", "url": GROUP_LINK}
        ],
        [
            {
                "text": "👥 معرفی کانال به دوستان خود",
                "url": f"https://t.me/share/url?url={CHANNEL_LINK}&text=" +
                       "⚡️ پکیج پروکسی‌های پرسرعت، تست‌شده و ضدفیلتر تلگرام"
            }
        ]
    ]
}

# ==================== پیام‌ها و تیترهای چرخشی ====================
HEADERS_ROTATION = [
    "⚡️ <b>پکیج طلایی پروکسی‌های پرسرعت تلگرام</b>",
    "🚀 <b>سریع‌ترین پروکسی‌های تست‌شده MTProto همراه اول</b>",
    "🛡 <b>سرورهای ضدفیلتر با کمترین تاخیر (پینگ سبز)</b>",
    "💎 <b>اتصال فوق‌سریع و بدون قطعی به تلگرام</b>",
    "🌟 <b>پروکسی‌های گلچین‌شده و اختصاصی کانال</b>",
    "✨ <b>پینگ پایدار و سرعت دانلود حداکثری</b>"
]

POST_TEXTS = [
    "✨ «امید، نوری است که حتی در تاریک‌ترین شب‌ها مسیر را روشن می‌کند.»",
    "🌌 «هر مانعی در مسیر، دعوتی است برای قوی‌تر شدن و پرواز بالاتر.»",
    "🌿 «صبور باش؛ قشنگ‌ترین گل‌ها در دل سنگ سخت و در سکوت رشد می‌کنند.»",
    "🔭 جالب است بدانید: کهکشان راه شیری با سرعتی حدود ۲ میلیون کیلومتر در ساعت در فضا حرکت می‌کند!",
    "📖 «در نومیدی بسی امید است / پایان شب سیه سپید است»",
    "💫 «جهان متعلق به کسانی است که به زیبایی رویاهایشان باور دارند.»",
    "🪐 جالب است بدانید: یک روز در سیاره زهره، طولانی‌تر از یک سال در همان سیاره است!",
    "🌊 «آرامش، هنر رها کردن چیزهایی است که تحت کنترل تو نیستند.»",
    "🚀 «شجاعت به معنای نترسیدن نیست؛ شجاعت یعنی با وجود ترس، رو به جلو قدم برداشتن.»",
    "🕊️ «بزرگ‌ترین افتخار این نیست که هرگز زمین نخوریم، بلکه این است که هر بار برخیزیم.»",
    "💡 «انرژی مثبت مثل پژواک کوه است؛ هر چه بفرستی، چند برابر به سویت بازمی‌گردد.»",
    "🎯 «موفقیت مجموعه‌ای از تلاش‌های کوچک و روزانه‌ای است که تکرار می‌شوند.»",
    "🔥 «آینده متعلق به کسانی است که امروز برای اهدافشان می‌جنگند.»"
]

# ==================== تصاویر چرخشی با کیفیت بالا ====================
CURATED_WALLPAPERS = [
    # طبیعت و مناظر تیره
    "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1280&auto=format&fit=crop",
    # کهکشان و فضا
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1543722530-d2c3201371e7?q=80&w=1280&auto=format&fit=crop",
    # نئونی و تکنولوژی
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=1280&auto=format&fit=crop"
]

def get_dynamic_image_url() -> str:
    base = random.choice(CURATED_WALLPAPERS)
    cache_buster = f"{int(time.time())}_{random.randint(1000, 99999)}"
    return f"{base}&cache={cache_buster}"


# ==================== ساعت تهران و تقویم شمسی ====================
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


# ==================== ساختار داده پروکسی ====================
@dataclass
class ProxyLink:
    server: str
    port: int
    secret: str
    latency: float = 999.0

    @property
    def tg_url(self) -> str:
        return f"tg://proxy?server={self.server}&port={self.port}&secret={self.secret}"

    @property
    def http_url(self) -> str:
        return f"https://t.me/proxy?server={self.server}&port={self.port}&secret={self.secret}"

    def __hash__(self):
        return hash((self.server, self.port, self.secret))

    def __eq__(self, other):
        if not isinstance(other, ProxyLink):
            return False
        return (self.server, self.port, self.secret) == (other.server, other.port, other.secret)


# ==================== استخراج دوگانه و شناسایی الگوها ====================
def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    line = line.strip()
    if not line:
        return None
    try:
        # ۱. شناسایی الگوهای استاندارد tg:// و https://t.me/proxy
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
                    return ProxyLink(server=server, port=port, secret=secret)

        # ۲. شناسایی الگوهای متنی IP:PORT:SECRET
        m_ip = IP_PORT_SECRET_RE.search(line)
        if m_ip:
            server = m_ip.group(1).strip()
            port = int(m_ip.group(2).strip())
            secret = m_ip.group(3).strip()
            if 0 < port < 65536:
                return ProxyLink(server=server, port=port, secret=secret)
    except Exception:
        pass
    return None


# ==================== باز کردن لینک‌ها و استخراج ====================
async def fetch_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    # اصلاح خودکار ساختار آدرس‌ها برای جلوگیری از ارور ۴۰۴
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
                    logger.info(f"✅ سورس {clean_url} دریافت شد ({len(lines)} رکورد).")
                    return lines
                else:
                    logger.warning(f"⚠️ دریافت {clean_url} با کد {r.status} ناموفق بود.")
        except Exception:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return []

async def collect_all() -> List[ProxyLink]:
    if not SOURCES:
        logger.error("❌ هیچ داده‌ای در متغیر PROXY_SOURCES یافت نشد!")
        return []

    logger.info(f"🚀 دریافت پروکسی‌ها از {len(SOURCES)} منبع معتبر...")
    
    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []
    urls_to_download: List[str] = []

    # خواندن مستقیم اگر خود خط پروکسی باشد یا ثبت لینک برای دانلود
    for line in SOURCES:
        p = parse_proxy_line(line)
        if p:
            key = (p.server, p.port, p.secret)
            if key not in seen:
                seen.add(key)
                proxies.append(p)
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

    logger.info(f"✅ مجموعاً {len(proxies)} پروکسی یکتا استخراج گردید (پیش از تست سرعت).")
    return proxies


# ==================== تست پینگ واقعی و حذف ۱۰۰٪ موارد مرده ====================
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
            return None  # سرور کند یا مرده درجا حذف می‌شود
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

async def filter_and_sort_alive(proxies: List[ProxyLink]) -> List[ProxyLink]:
    logger.info(f"🧪 آغاز تست سرعت روی {len(proxies)} سرور (حذف قطعی سرورهای خاموش)...")
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    
    # نگه‌داری فقط سرورهای زنده و سالم
    alive = [p for p in results if p is not None]
    
    # مرتب‌سازی بر اساس بالاترین سرعت (کمترین پینگ در بالای لیست)
    alive.sort(key=lambda x: x.latency)
    logger.info(f"🎯 تعداد {len(alive)} سرور ۱۰۰٪ سالم با پینگ واقعی تایید شدند.")
    return alive


# ==================== تولید کپشن ۱۷ پروکسی با بالاترین سرعت ====================
def build_caption_with_hyperlinks(top_17: List[ProxyLink]) -> Tuple[str, str]:
    header = random.choice(HEADERS_ROTATION)
    motivational_text = random.choice(POST_TEXTS)

    hyperlink_tags = [f'<a href="{p.http_url}">⚡️ پروکسی {idx}</a>' for idx, p in enumerate(top_17, 1)]

    # چیدمان منظم: سطر اول ۲ عدد + ۵ سطر ۳تایی = دقیقاً ۱۷ پروکسی
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
        f"👇 <b>۱۷ پروکسی گلچین‌شده با بالاترین سرعت (تست‌شده ✅):</b>\n"
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


# ==================== ذخیره دو فایل تفکیک‌شده ====================
def save_dual_files(alive: List[ProxyLink]) -> Tuple[str, str]:
    # ۱. فایل فرمت درون‌برنامه‌ای tg://
    with open(FILE_TG, "w", encoding="utf-8") as f:
        f.write("\n".join(p.tg_url for p in alive))

    # ۲. فایل فرمت تحت‌وب https://t.me/
    with open(FILE_HTTP, "w", encoding="utf-8") as f:
        f.write("\n".join(p.http_url for p in alive))

    logger.info(f"💾 هر دو فایل {FILE_TG} و {FILE_HTTP} با موفقیت ذخیره شدند.")
    return FILE_TG, FILE_HTTP


# ==================== ارسال به تلگرام با ۳ دکمه شیشه‌ای ====================
async def send_to_telegram(alive: List[ProxyLink]) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ اطلاعات BOT_TOKEN یا CHAT_ID یافت نشد.")
        return

    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    url_pin = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        
        # ۱. ارسال پست تصویر با ۱۷ پروکسی و ۳ دکمه شیشه‌ای
        top_17 = alive[:17]
        full_caption, short_caption = build_caption_with_hyperlinks(top_17)
        image_url = get_dynamic_image_url()

        photo_payload = {
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": full_caption if len(full_caption) <= 1024 else short_caption,
            "parse_mode": "HTML",
            "reply_markup": INLINE_KEYBOARD  # ۳ دکمه شیشه‌ای
        }

        msg_id = None
        try:
            async with session.post(url_photo, json=photo_payload, timeout=aiohttp.ClientTimeout(total=25)) as r:
                res = await r.json()
                if res.get("ok"):
                    logger.info("✅ پست تصویری ۱۷ پروکسی با ۳ دکمه شیشه‌ای ارسال شد.")
                    msg_id = res["result"]["message_id"]
                else:
                    logger.warning(f"⚠️ ارسال عکس انجام نشد ({res.get('description')})؛ ارسال متنی...")
                    text_payload = {
                        "chat_id": CHAT_ID,
                        "text": full_caption,
                        "parse_mode": "HTML",
                        "reply_markup": INLINE_KEYBOARD
                    }
                    async with session.post(url_msg, json=text_payload) as mr:
                        m_res = await mr.json()
                        if m_res.get("ok"):
                            msg_id = m_res["result"]["message_id"]

            if msg_id:
                pin_payload = {"chat_id": CHAT_ID, "message_id": msg_id}
                await session.post(url_pin, json=pin_payload, timeout=aiohttp.ClientTimeout(total=10))

        except Exception as e:
            logger.error(f"❌ خطای شبکه در ارسال پست عکس: {e}")

        # آماده‌سازی اطلاعات زمان و فایل‌ها
        time_str, jalali_str, gregorian_str = get_tehran_date_and_time()
        file_tg_path, file_http_path = save_dual_files(alive)

        # ۲. ارسال فایل اول: فرمت TG با ۳ دکمه شیشه‌ای
        caption_tg = (
            "📁 <b>فایل جامع پروکسی‌های تلگرام (فرمت اختصاصی TG)</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⚡️ تعداد سرورهای فعال و سالم: <b>{len(alive)} عدد</b>\n"
            "🔍 وضعیت: <b>تست سوکت شده و بدون قطعی ✅</b>\n"
            "🚀 مرتب‌سازی: <b>از بیشترین به کمترین سرعت</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
            f"📅 تاریخ شمسی: <b>{jalali_str}</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"👉🆔 {CHANNEL_ID}"
        )

        try:
            with open(file_tg_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", CHAT_ID)
                data.add_field("caption", caption_tg)
                data.add_field("parse_mode", "HTML")
                data.add_field("reply_markup", json.dumps(INLINE_KEYBOARD))  # ۳ دکمه شیشه‌ای
                data.add_field("document", f, filename="PROXIES_TG_FORMAT.txt")

                async with session.post(url_doc, data=data, timeout=aiohttp.ClientTimeout(total=35)) as r1:
                    res1 = await r1.json()
                    if res1.get("ok"):
                        logger.info("✅ فایل اول (فرمت TG) با ۳ دکمه شیشه‌ای ارسال شد.")
        except Exception as e:
            logger.error(f"❌ خطا در ارسال فایل اول: {e}")

        # ۳. ارسال فایل دوم: فرمت HTTP با ۳ دکمه شیشه‌ای
        caption_http = (
            "📁 <b>فایل جامع پروکسی‌های تلگرام (فرمت تحت‌وب HTTP)</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⚡️ تعداد سرورهای فعال و سالم: <b>{len(alive)} عدد</b>\n"
            "🔍 وضعیت: <b>تست سوکت شده و بدون قطعی ✅</b>\n"
            "🚀 مرتب‌سازی: <b>از بیشترین به کمترین سرعت</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
            f"📆 تاریخ میلادی: <b>{gregorian_str}</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"👉🆔 {CHANNEL_ID}"
        )

        try:
            with open(file_http_path, "rb") as f:
                data2 = aiohttp.FormData()
                data2.add_field("chat_id", CHAT_ID)
                data2.add_field("caption", caption_http)
                data2.add_field("parse_mode", "HTML")
                data2.add_field("reply_markup", json.dumps(INLINE_KEYBOARD))  # ۳ دکمه شیشه‌ای
                data2.add_field("document", f, filename="PROXIES_HTTP_FORMAT.txt")

                async with session.post(url_doc, data=data2, timeout=aiohttp.ClientTimeout(total=35)) as r2:
                    res2 = await r2.json()
                    if res2.get("ok"):
                        logger.info("✅ فایل دوم (فرمت HTTP) با ۳ دکمه شیشه‌ای ارسال شد.")
        except Exception as e:
            logger.error(f"❌ خطا در ارسال فایل دوم: {e}")


# ==================== بدنه اصلی برنامه ====================
async def main() -> None:
    logger.info("🎬 آغاز چرخه دریافت، تست سرعت و انتشار پروکسی‌ها...")
    all_proxies = await collect_all()
    if not all_proxies:
        logger.error("❌ هیچ پروکسی از منابع دریافت نشد.")
        return

    # تست سرعت سخت‌گیرانه و حذف کامل موارد خاموش
    alive = await filter_and_sort_alive(all_proxies)
    if not alive:
        logger.error("❌ هیچ سرور سالمی تست پینگ را پاس نکرد.")
        return

    # ارسال پست تصویر ۱۷ پروکسی + ۲ فایل مجزا همراه با ۳ دکمه شیشه‌ای
    await send_to_telegram(alive)
    logger.info("🏁 کلیه مراحل با موفقیت کامل و بدون نقص به پایان رسید.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("توقف دستی برنامه.")
    except Exception as e:
        logger.critical(f"خطای سیستمی: {e}", exc_info=True)
        sys.exit(1)
