#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Telegram Proxy Collector v3.1
جمع‌آوری، تست و ارسال پروکسی به همراه ساعت تهران، تاریخ شمسی و میلادی
"""

import asyncio
import os
import re
import sys
import random
import logging
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiohttp

# ==================== تنظیم Logging ====================
def setup_logging():
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('proxy_collector.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== خواندن تنظیمات از متغیرهای مخفی ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
SOURCES_ENV = os.environ.get("PROXY_SOURCES", "").strip()

SOURCES = [line.strip() for line in SOURCES_ENV.splitlines() if line.strip() and not line.strip().startswith("#")]

OUTPUT_FILE = "TELEGRAM_PROXY_SUB_TXT"
CHANNEL_ID = "@Goodbaye_filtering"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"
GROUP_LINK = "https://t.me/CONFIG_V2RAY_VIP"

FETCH_TIMEOUT = 15.0
TCP_TIMEOUT = 5.0
MAX_CONCURRENT_TESTS = 40
MAX_RETRIES = 3
RETRY_DELAY = 2.0

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")

POST_TEXTS = [
    "✨ «امید، نوری است که حتی در تاریک‌ترین شب‌ها مسیر را روشن می‌کند.»",
    "🌌 «هر مانعی در مسیر، دعوتی است برای قوی‌تر شدن و پرواز بالاتر.»",
    "🌿 «صبور باش؛ قشنگ‌ترین گل‌ها در دل سنگ سخت و در سکوت رشد می‌کنند.»",
    "🔭 جالب است بدانید: کهکشان راه شیری با سرعتی حدود ۲ میلیون کیلومتر در ساعت در حال حرکت در کیهان است!",
    "📖 «در نومیدی بسی امید است / پایان شب سیه سپید است»",
    "💫 «جهان متعلق به کسانی است که به زیبایی رویاهایشان باور دارند.»",
    "🪐 جالب است بدانید: یک روز در سیاره زهره، طولانی‌تر از یک سال در همان سیاره است!",
    "🌊 «آرامش، هنر رها کردن چیزهایی است که تحت کنترل تو نیستند.»",
    "🚀 «شجاعت به معنای نترسیدن نیست؛ شجاعت یعنی با وجود ترس، رو به جلو قدم برداشتن.»",
    "🕊️ «بزرگ‌ترین افتخار این نیست که هرگز زمین نخوریم، بلکه این است که هر بار برخیزیم.»"
]

RANDOM_IMAGE_URL = "https://picsum.photos/1080/720"


# ==================== تبدیل تاریخ به شمسی ====================
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """تبدیل تقویم میلادی به شمسی بدون نیاز به کتابخانه جانبی"""
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
    """محاسبه دقیق ساعت به وقت تهران، تاریخ شمسی و میلادی"""
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tehran_tz)
    
    time_str = now.strftime("%H:%M:%S")
    gregorian_str = now.strftime("%Y/%m/%d")
    
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    jalali_str = f"{jy:04d}/{jm:02d}/{jd:02d}"
    
    return time_str, jalali_str, gregorian_str


# ==================== Data Classes ====================
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


# ==================== Parsing ====================
def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    line = line.strip()
    if not line:
        return None
    try:
        m = PROXY_RE.search(line)
        if not m:
            return None
        url = m.group(0)
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


# ==================== Fetching ====================
async def fetch_source(session: aiohttp.ClientSession, url: str, retries: int = MAX_RETRIES) -> List[str]:
    for attempt in range(retries):
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
                ssl=False
            ) as r:
                if r.status != 200:
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue
                text = await r.text(errors="ignore")
                return text.splitlines()
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    return []


async def collect_all() -> List[ProxyLink]:
    if not SOURCES:
        logger.error("❌ هیچ لینکی در متغیر PROXY_SOURCES تعریف نشده است!")
        return []

    logger.info(f"🚀 دریافت پروکسی‌ها از {len(SOURCES)} منبع مخفی...")
    connector = aiohttp.TCPConnector(limit_per_host=5, limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        all_lines = await asyncio.gather(
            *[fetch_source(session, u) for u in SOURCES],
            return_exceptions=True
        )

    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []

    for lines in all_lines:
        if isinstance(lines, Exception) or not lines:
            continue
        for line in lines:
            p = parse_proxy_line(line)
            if not p:
                continue
            key = (p.server, p.port, p.secret)
            if key in seen:
                continue
            seen.add(key)
            proxies.append(p)

    logger.info(f"✅ {len(proxies)} پروکسی یکتا استخراج شد")
    return proxies


# ==================== Testing ====================
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
    logger.info(f"🧪 شروع بررسی {len(proxies)} پروکسی...")
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    alive = [p for p in results if p is not None]
    alive.sort(key=lambda x: x.latency)
    logger.info(f"✅ {len(alive)} پروکسی فعال و پاسخ‌گو تایید شد")
    return alive


# ==================== File Operations ====================
async def save_proxies_to_file(file_path: str, proxies: List[ProxyLink]) -> bool:
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(p.raw for p in proxies))
        return True
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره فایل: {e}")
        return False


# ==================== ساخت متن هایپرلینک پست تصویری ====================
def build_caption_with_hyperlinks(top_proxies: List[ProxyLink]) -> str:
    motivational_text = random.choice(POST_TEXTS)
    hyperlink_tags = [f'<a href="{p.raw}">پروکسی</a>' for p in top_proxies]
    
    rows = []
    i = 0
    if len(hyperlink_tags) >= 2:
        rows.append(" | ".join(hyperlink_tags[0:2]))
        i = 2

    while i < len(hyperlink_tags):
        chunk = hyperlink_tags[i:i+3]
        rows.append(" | ".join(chunk))
        i += 3

    proxies_section = "\n".join(rows)

    caption = (
        f"{motivational_text}\n\n"
        f"{proxies_section}\n\n"
        f"🔥 {CHANNEL_ID}\n"
        f"💬 <a href=\"{GROUP_LINK}\">سوپرگروه ما</a>"
    )
    return caption


# ==================== ارسال به تلگرام ====================
async def send_to_telegram(file_path: str, proxies: List[ProxyLink]) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("⚠️ اطلاعات BOT_TOKEN یا CHAT_ID موجود نیست.")
        return

    logger.info("📤 درحال ارسال پست و فایل به تلگرام...")
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    url_pin = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # ۱. ارسال پست عکس با هایپرلینک‌ها
            top_proxies = proxies[:14]
            caption = build_caption_with_hyperlinks(top_proxies)

            photo_payload = {
                "chat_id": CHAT_ID,
                "photo": RANDOM_IMAGE_URL,
                "caption": caption,
                "parse_mode": "HTML"
            }

            async with session.post(url_photo, json=photo_payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
                res = await r.json()
                if res.get("ok"):
                    logger.info("✅ پست تصویری با موفقیت ارسال شد")
                    message_id = res["result"]["message_id"]

                    pin_payload = {"chat_id": CHAT_ID, "message_id": message_id}
                    async with session.post(url_pin, json=pin_payload, timeout=aiohttp.ClientTimeout(total=15)) as pin_res:
                        pin_json = await pin_res.json()
                        if pin_json.get("ok"):
                            logger.info("📌 پست با موفقیت پین شد")

            # ۲. ساخت کپشن حرفه‌ای و کامل فایل پروکسی‌ها
            time_str, jalali_str, gregorian_str = get_tehran_date_and_time()

            file_caption = (
                "📁 <b>فایل جامع سابسکرایب پروکسی‌های تلگرام</b>\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                f"📊 تعداد کل پروکسی‌های فعال: <b>{len(proxies)} عدد</b>\n"
                "⚡️ نوع پروتکل: <b>MTProto (High Speed)</b>\n"
                "🔍 وضعیت: <b>تست‌شده و بدون قطعی ✅</b>\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                f"⏰ ساعت به‌روزرسانی: <b>{time_str}</b> (به وقت تهران)\n"
                f"📅 تاریخ شمسی: <b>{jalali_str}</b>\n"
                f"📆 تاریخ میلادی: <b>{gregorian_str}</b>\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                f"✨ <b>کانال:</b> <a href=\"{CHANNEL_LINK}\">عضویت در کانال</a>\n"
                f"💬 <b>گروه:</b> <a href=\"{GROUP_LINK}\">عضویت در سوپرگروه</a>"
            )

            # ارسال فایل متنی
            if Path(file_path).exists():
                with open(file_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field("chat_id", CHAT_ID)
                    data.add_field("caption", file_caption)
                    data.add_field("parse_mode", "HTML")
                    data.add_field("document", f, filename="TELEGRAM_PROXIES.txt")

                    async with session.post(url_doc, data=data, timeout=aiohttp.ClientTimeout(total=40)) as doc_r:
                        doc_res = await doc_r.json()
                        if doc_res.get("ok"):
                            logger.info("✅ فایل کلی پروکسی‌ها با کپشن جدید ارسال شد")

    except Exception as e:
        logger.error(f"❌ خطا در فرآیند ارسال تلگرام: {e}")


# ==================== Main ====================
async def main() -> None:
    all_proxies = await collect_all()
    if not all_proxies:
        return

    alive = await filter_and_sort_alive(all_proxies)
    if not alive:
        return

    if await save_proxies_to_file(OUTPUT_FILE, alive):
        await send_to_telegram(OUTPUT_FILE, alive)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("توقف برنامه")
    except Exception as e:
        logger.error(f"خطا: {e}", exc_info=True)
        sys.exit(1)
