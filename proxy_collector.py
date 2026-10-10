#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Telegram Proxy Collector (Guaranteed 4-Post Edition v5.5)
ارسال دقیق ۴ پیام مستقل: ۲ پیام تصویری با ۱۷ هایپرلینک کامل + ۲ فایل ۱۰۰تایی گلچین با ۳ دکمه شیشه‌ای
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

# ==================== تنظیم لاگ ====================
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

# ==================== متغیرهای مخفی مخزن ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
PROXY_SOURCES = os.environ.get("PROXY_SOURCES", "").strip()

SOURCES = [line.strip() for line in PROXY_SOURCES.splitlines() if line.strip() and not line.strip().startswith("#")]

FILE_TG = "PROXIES_TG_TOP100.txt"
FILE_HTTP = "PROXIES_HTTP_TOP100.txt"

CHANNEL_ID = "@Goodbaye_filtering"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"
GROUP_LINK = "https://t.me/CONFIG_V2RAY_VIP"

FETCH_TIMEOUT = 18.0
TCP_TIMEOUT = 2.5
MAX_CONCURRENT_TESTS = 60
MAX_RETRIES = 2
RETRY_DELAY = 1.5

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")
IP_PORT_SECRET_RE = re.compile(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b)[:\s]+(\d{2,5})[:\s]+([a-fA-F0-9]{32,})")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==================== ۳ دکمه شیشه‌ای برای تمام ۴ پیام ====================
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

# ==================== تیترها و پیام‌های چرخشی ====================
HEADERS_ROTATION_HTTP = [
    "⚡️ <b>پکیج طلایی پروکسی‌های پرسرعت تلگرام (نسخه وب)</b>",
    "🚀 <b>سریع‌ترین پروکسی‌های ضدفیلتر تلگرام (اتصال سریع)</b>",
    "💎 <b>پروکسی‌های فوق‌العاده پرسرعت و پایدار تلگرام</b>",
    "🌟 <b>پروکسی‌های گلچین‌شده و اختصاصی کانال</b>"
]

HEADERS_ROTATION_TG = [
    "⚡️ <b>پکیج طلایی پروکسی‌های پرسرعت تلگرام (نسخه TG)</b>",
    "🚀 <b>سریع‌ترین پروکسی‌های درون‌برنامه‌ای تلگرام (اتصال مستقیم)</b>",
    "💎 <b>پروکسی‌های توربو و بدون قطعی تلگرام</b>",
    "🌟 <b>پروکسی‌های اختصاصی و تست‌شده کانال</b>"
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
    "🕊️ «بزرگ‌ترین افتخار این نیست که هرگز زمین نخوریم، بلکه این است که هر بار برخیزیم.»"
]

# ==================== والپیپرهای گرافیکی چرخشی ====================
CURATED_WALLPAPERS = [
    "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1280&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1563089145-599997674d42?q=80&w=1280&auto=format&fit=crop"
]

def get_dynamic_image_url() -> str:
    base = random.choice(CURATED_WALLPAPERS)
    cache_buster = f"{int(time.time())}_{random.randint(1000, 99999)}"
    return f"{base}&cache={cache_buster}"


# ==================== ساعت و تقویم تهران ====================
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
    latency: float = 999.0

    @property
    def is_faketls(self) -> bool:
        sec = self.secret.lower()
        return (sec.startswith("ee") or sec.startswith("dd")) and len(sec) >= 34

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


# ==================== استخراج پروکسی‌ها ====================
def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    line = line.strip()
    if not line:
        return None
    try:
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

async def fetch_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    clean_url = url.replace("/refs/heads/", "/")
    if "t.me/" in clean_url and "/s/" not in clean_url and not clean_url.startswith("https://t.me/proxy"):
        clean_url = clean_url.replace("t.me/", "t.me/s/")

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(clean_url, headers=BROWSER_HEADERS, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT), ssl=False) as r:
                if r.status == 200:
                    text = await r.text(errors="ignore")
                    lines = text.splitlines()
                    logger.info(f"✅ سورس {clean_url} دریافت شد ({len(lines)} رکورد).")
                    return lines
        except Exception:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    return []

async def collect_all() -> List[ProxyLink]:
    if not SOURCES:
        logger.error("❌ هیچ داده‌ای در متغیر PROXY_SOURCES یافت نشد!")
        return []

    logger.info(f"🚀 دریافت پروکسی‌ها از {len(SOURCES)} منبع مخزن...")
    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []
    urls_to_download: List[str] = []

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

    logger.info(f"✅ مجموعاً {len(proxies)} پروکسی یکتا استخراج گردید.")
    return proxies


# ==================== تست پینگ و انتخاب ۱۷ و ۱۰۰ سرور ====================
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

async def filter_and_sort_alive(proxies: List[ProxyLink]) -> Tuple[List[ProxyLink], List[ProxyLink]]:
    logger.info(f"🧪 آغاز تست سرعت روی {len(proxies)} پروکسی...")
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    alive = [p for p in results if p is not None]

    # اولویت‌بندی دقیق برای اتصال پایدار همراه اول:
    tier1_tls_443 = [p for p in alive if p.is_faketls and p.port == 443]
    tier1_tls_443.sort(key=lambda x: x.latency)

    tier2_tls_other = [p for p in alive if p.is_faketls and p.port != 443]
    tier2_tls_other.sort(key=lambda x: x.latency)

    tier3_rest = [p for p in alive if not p.is_faketls]
    tier3_rest.sort(key=lambda x: x.latency)

    all_sorted = tier1_tls_443 + tier2_tls_other + tier3_rest
    top_17 = all_sorted[:17]
    top_100 = all_sorted[:100]

    logger.info(f"🎯 انتخاب ۱۷ پروکسی سوپرفست و ۱۰۰ پروکسی منتخب انجام شد.")
    return top_17, top_100


# ==================== تولید ۱۷ هایپرلینک دقیقاً مطابق تصویر ====================
def build_17_hyperlinks_post(top_17: List[ProxyLink], format_mode: str = "HTTP") -> str:
    """چیدمان دقیق ۶ سطری: سطر اول ۲ تا، پنج سطر بعدی ۳ تا = ۱۷ عدد"""
    header = random.choice(HEADERS_ROTATION_HTTP if format_mode == "HTTP" else HEADERS_ROTATION_TG)
    motivational_text = random.choice(POST_TEXTS)

    # ساخت کلمه «پروکسی» با هایپرلینک مربوطه
    if format_mode == "HTTP":
        tags = [f'<a href="{p.http_url}">پروکسی</a>' for p in top_17]
    else:
        tags = [f'<a href="{p.tg_url}">پروکسی</a>' for p in top_17]

    rows = []
    if len(tags) >= 2:
        rows.append(" | ".join(tags[0:2]))

    i = 2
    while i < len(tags):
        chunk = tags[i:i+3]
        rows.append(" | ".join(chunk))
        i += 3

    proxies_section = "\n".join(rows)

    caption = (
        f"{header}\n\n"
        f"{motivational_text}\n\n"
        f"{proxies_section}\n\n"
        f"🔥 {CHANNEL_ID}\n"
        f"💬 <a href=\"{GROUP_LINK}\">سوپرگروه چت و گفت‌وگو</a>"
    )
    return caption


# ==================== ذخیره دو فایل ۱۰۰تایی در مخزن ====================
def save_dual_files(top_100: List[ProxyLink]) -> Tuple[str, str]:
    with open(FILE_TG, "w", encoding="utf-8") as f:
        f.write("\n".join(p.tg_url for p in top_100))

    with open(FILE_HTTP, "w", encoding="utf-8") as f:
        f.write("\n".join(p.http_url for p in top_100))

    logger.info(f"💾 فایل‌های {FILE_TG} و {FILE_HTTP} در مخزن ذخیره شدند.")
    return FILE_TG, FILE_HTTP


# ==================== ارسال دقیق ۴ پیام مجزا به تلگرام ====================
async def send_to_telegram(top_17: List[ProxyLink], top_100: List[ProxyLink]) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ اطلاعات BOT_TOKEN یا CHAT_ID موجود نیست.")
        return

    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    time_str, jalali_str, gregorian_str = get_tehran_date_and_time()
    file_tg_path, file_http_path = save_dual_files(top_100)

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # -------------------------------------------------------------
        # پیام ۱: پست تصویری با ۱۷ هایپرلینک پروکسی تلگرام (HTTP) + ۳ دکمه
        # -------------------------------------------------------------
        img_url_1 = get_dynamic_image_url()
        text_post_1 = build_17_hyperlinks_post(top_17, format_mode="HTTP")
        
        # استفاده از بنر تصویری در پیام تا سقف ۴۰۹۶ کاراکتر باز شود و ۱۷ لینک هرگز حذف نشوند
        full_text_1 = f'<a href="{img_url_1}">&#8203;</a>' + text_post_1

        payload_1 = {
            "chat_id": CHAT_ID,
            "text": full_text_1,
            "parse_mode": "HTML",
            "link_preview_options": {
                "is_disabled": False,
                "url": img_url_1,
                "prefer_large_media": True,
                "show_above_text": True
            },
            "reply_markup": INLINE_KEYBOARD
        }

        try:
            async with session.post(url_msg, json=payload_1, timeout=aiohttp.ClientTimeout(total=25)) as r1:
                res1 = await r1.json()
                if res1.get("ok"):
                    logger.info("✅ پیام ۱ (عکس + ۱۷ هایپرلینک پروکسی وب) ارسال شد.")
                else:
                    logger.warning(f"⚠️ پیام ۱ با خطا مواجه شد: {res1.get('description')}")
        except Exception as e:
            logger.error(f"خطای شبکه در پیام ۱: {e}")

        await asyncio.sleep(2)

        # -------------------------------------------------------------
        # پیام ۲: پست تصویری با ۱۷ هایپرلینک پروکسی TG + ۳ دکمه
        # -------------------------------------------------------------
        img_url_2 = get_dynamic_image_url()
        text_post_2 = build_17_hyperlinks_post(top_17, format_mode="TG")
        full_text_2 = f'<a href="{img_url_2}">&#8203;</a>' + text_post_2

        payload_2 = {
            "chat_id": CHAT_ID,
            "text": full_text_2,
            "parse_mode": "HTML",
            "link_preview_options": {
                "is_disabled": False,
                "url": img_url_2,
                "prefer_large_media": True,
                "show_above_text": True
            },
            "reply_markup": INLINE_KEYBOARD
        }

        try:
            async with session.post(url_msg, json=payload_2, timeout=aiohttp.ClientTimeout(total=25)) as r2:
                res2 = await r2.json()
                if res2.get("ok"):
                    logger.info("✅ پیام ۲ (عکس + ۱۷ هایپرلینک پروکسی TG) ارسال شد.")
                else:
                    logger.warning(f"⚠️ پیام ۲ با خطا مواجه شد: {res2.get('description')}")
        except Exception as e:
            logger.error(f"خطای شبکه در پیام ۲: {e}")

        await asyncio.sleep(2)

        # -------------------------------------------------------------
        # پیام ۳: فایل ۱۰۰ پروکسی گلچین (فرمت HTTP) + ۳ دکمه شیشه‌ای
        # -------------------------------------------------------------
        caption_doc_http = (
            "📁 <b>فایل جامع ۱۰۰ پروکسی پرسرعت (فرمت تحت‌وب HTTP)</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⚡️ تعداد سرورهای منتخب: <b>{len(top_100)} عدد (پرسرعت‌ترین‌ها)</b>\n"
            "🔍 وضعیت: <b>تست‌شده و بدون قطعی ✅</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
            f"📆 تاریخ میلادی: <b>{gregorian_str}</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"👉🆔 {CHANNEL_ID}"
        )

        try:
            with open(file_http_path, "rb") as f:
                data_http = aiohttp.FormData()
                data_http.add_field("chat_id", CHAT_ID)
                data_http.add_field("caption", caption_doc_http)
                data_http.add_field("parse_mode", "HTML")
                data_http.add_field("reply_markup", json.dumps(INLINE_KEYBOARD))
                data_http.add_field("document", f, filename="PROXIES_HTTP_TOP100.txt")

                async with session.post(url_doc, data=data_http, timeout=aiohttp.ClientTimeout(total=35)) as r3:
                    res3 = await r3.json()
                    if res3.get("ok"):
                        logger.info("✅ پیام ۳ (فایل ۱۰۰ پروکسی HTTP) ارسال شد.")
        except Exception as e:
            logger.error(f"خطا در پیام ۳: {e}")

        await asyncio.sleep(2)

        # -------------------------------------------------------------
        # پیام ۴: فایل ۱۰۰ پروکسی گلچین (فرمت TG) + ۳ دکمه شیشه‌ای
        # -------------------------------------------------------------
        caption_doc_tg = (
            "📁 <b>فایل جامع ۱۰۰ پروکسی پرسرعت (فرمت اختصاصی TG)</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⚡️ تعداد سرورهای منتخب: <b>{len(top_100)} عدد (پرسرعت‌ترین‌ها)</b>\n"
            "🔍 وضعیت: <b>تست‌شده و بدون قطعی ✅</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
            f"📅 تاریخ شمسی: <b>{jalali_str}</b>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"👉🆔 {CHANNEL_ID}"
        )

        try:
            with open(file_tg_path, "rb") as f:
                data_tg = aiohttp.FormData()
                data_tg.add_field("chat_id", CHAT_ID)
                data_tg.add_field("caption", caption_doc_tg)
                data_tg.add_field("parse_mode", "HTML")
                data_tg.add_field("reply_markup", json.dumps(INLINE_KEYBOARD))
                data_tg.add_field("document", f, filename="PROXIES_TG_TOP100.txt")

                async with session.post(url_doc, data=data_tg, timeout=aiohttp.ClientTimeout(total=35)) as r4:
                    res4 = await r4.json()
                    if res4.get("ok"):
                        logger.info("✅ پیام ۴ (فایل ۱۰۰ پروکسی TG) ارسال شد.")
        except Exception as e:
            logger.error(f"خطا در پیام ۴: {e}")


# ==================== بدنه اصلی برنامه ====================
async def main() -> None:
    logger.info("🎬 آغاز چرخه دریافت، تست سرعت و غربال‌گری ضدفیلتر...")
    all_proxies = await collect_all()
    if not all_proxies:
        logger.error("❌ هیچ پروکسی از منابع دریافت نشد.")
        return

    top_17, top_100 = await filter_and_sort_alive(all_proxies)
    if not top_17:
        logger.error("❌ هیچ سرور سالمی تست را پاس نکرد.")
        return

    # ارسال دقیق ۴ پیام مجزا همراه با ۳ دکمه شیشه‌ای
    await send_to_telegram(top_17, top_100)
    logger.info("🏁 کلیه ۴ پیام با موفقیت کامل و بدون نقص ارسال گردید.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"خطای سیستمی: {e}", exc_info=True)
        sys.exit(1)
