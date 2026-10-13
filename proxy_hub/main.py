import os
import re
import json
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# ==================== دریافت تنظیمات از گیت‌هاب ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

# منابع عمومی معتبر برای اسکرپ وب پروکسی‌ها
CHANNELS_LIST = [
    "TelMTProto",
    "ProxyMTProto",
    "iMTProto",
    "ProxyHagh",
    "proxies_free",
    "MTProtoProxies",
    "ProxyMTProto_Tel",
    "DailyMTProto",
    "VpnMTProto",
    "IR_Proxy",
    "ProxiesMTProto",
    "FreeProxyIran",
    "ProxyFast",
    "ProxyNational",
    "ProxySolid",
    "AlphaProxies"
]

# دکمه‌های شیشه‌ای ۳ گانه
INLINE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "📢 کانال اصلی ضد فیلتر", "url": "https://t.me/Goodbaye_filtering"},
            {"text": "⭐️ کانال VIP کانفیگ", "url": "https://t.me/CONFIG_V2RAY_VIP"}
        ],
        [
            {"text": "🚀 اشتراک‌گذاری با دوستان", "url": "https://t.me/share/url?url=https://t.me/Goodbaye_filtering"}
        ]
    ]
}

# متن‌های انگیزشی و آموزنده
MOTIVATIONAL_QUOTES = [
    "«هیچ دیواری پایدار نیست؛ راه آگاهی و آزادی همواره گشوده خواهد شد.» ✨",
    "«ارتباط بی‌پایان، حق مسلم دنیای امروز است؛ متصل و مانا بمانید.» 🌐",
    "«محدودیت‌ها تنها اراده ما را برای ساختن مسیرهای نو استوارتر می‌کنند.» 💡",
    "«تاریک‌ترین ساعت شب، مژده‌بخش طلوع روشن‌ترین سپیده‌دم است.» ☀️",
    "«پشتکار یعنی تکرار امید و تلاش، حتی در سخت‌ترین شرایط ممکن.» 🚀",
    "«آگاهی بزرگ‌ترین سپر انسان در برابر تاریکی و ناامیدی است.» 🌿"
]

# والپیپرهای مینیمال و بسیار شکیل
WALLPAPERS = [
    "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&q=80",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&q=80",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&q=80",
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1200&q=80"
]

PROXY_REGEX = re.compile(
    r'(?:https?:\/\/t\.me\/(?:proxy\?|socks\?)|tg:\/\/(?:proxy\?|socks\?))[^\s"\'<>]+',
    re.IGNORECASE
)

def normalize_link(link: str) -> str:
    """استانداردسازی لینک برای حذف قطعی تکراری‌ها"""
    clean = link.strip().replace("http://", "https://")
    if clean.startswith("https://t.me/proxy?"):
        clean = clean.replace("https://t.me/proxy?", "tg://proxy?")
    elif clean.startswith("https://t.me/socks?"):
        clean = clean.replace("https://t.me/socks?", "tg://socks?")
    return clean

def get_tehran_time() -> str:
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz).strftime("%Y/%m/%d - %H:%M")

def collect_proxies():
    """استخراج مستقیم پروکسی‌ها از صفحات عمومی وب تلگرام"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    proxies_list = []
    seen = set()

    for ch in CHANNELS_LIST:
        url = f"https://t.me/s/{ch}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                # یافتن در متن‌ها
                matches = PROXY_REGEX.findall(res.text)
                # یافتن در تگ‌های href لینک‌ها
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "proxy?" in href or "socks?" in href:
                        matches.append(href)

                for item in matches:
                    norm = normalize_link(item)
                    if norm not in seen and len(norm) > 15:
                        seen.add(norm)
                        proxies_list.append(norm)
        except Exception as e:
            print(f"[!] خطا در کانال {ch}: {e}")

    return proxies_list

def send_file_to_channel(filename: str, caption: str):
    """ارسال پیام اول: فایل به همراه دکمه‌های شیشه‌ای"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(INLINE_KEYBOARD)
        }
        r = requests.post(url, data=data, files={"document": f}, timeout=40)
        return r.json()

def send_photo_to_channel(photo_url: str, caption: str):
    """ارسال پیام دوم: تصویر باکیفیت + ۱۷ هایپرلینک + دکمه‌ها"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(INLINE_KEYBOARD)
    }
    r = requests.post(url, data=data, timeout=40)
    return r.json()

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] مقادیر BOT_TOKEN یا CHAT_ID در سکرت‌ها خالی است!")
        return

    print("[*] در حال جمع‌آوری پروکسی‌ها...")
    proxies = collect_proxies()
    total = len(proxies)
    print(f"[✓] تعداد پروکسی‌های یکتا: {total}")

    if total == 0:
        print("[!] پروکسی جدیدی یافت نشد.")
        return

    time_str = get_tehran_time()
    filename = "Proxies_Daily.txt"

    # ذخیره در فایل متنی
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Telegram Proxies Collection\n# Time: {time_str}\n# Count: {total}\n\n")
        f.write("\n".join(proxies))

    # ۱. آماده‌سازی پیام اول (فایل + مشخصات + قوانین)
    file_caption = (
        f"📁 <b>بسته جامع پروکسی‌های ضدفیلتر تلگرام</b>\n\n"
        f"📊 <b>تعداد کل پروکسی‌های یکتا:</b> <code>{total}</code> عدد\n"
        f"⏰ <b>زمان به‌روزرسانی:</b> <code>{time_str}</code>\n"
        f"🛡 <b>پروتکل‌ها:</b> MTProto & SOCKS5\n\n"
        f"📌 <b>قوانین و راهنما:</b>\n"
        f"▫️ هنگام اتصال، وی‌پی‌ان خود را خاموش نگه دارید.\n"
        f"▫️ جهت بهترین سرعت، به پروکسی با کمترین پینگ متصل شوید.\n"
        f"▫️ پروکسی‌ها کاملاً پالایش‌شده و بدون تبلیغات مزاحم هستند."
    )
    print("[*] در حال ارسال فایل به کانال...")
    res_file = send_file_to_channel(filename, file_caption)
    print("نتیجه ارسال فایل:", res_file.get("ok"))

    # ۲. آماده‌سازی پیام دوم (عکس + ۱۷ پروکسی هایپرلینک + سخن انگیزشی)
    top_17 = proxies[:17]
    quote = random.choice(MOTIVATIONAL_QUOTES)
    photo = random.choice(WALLPAPERS)

    links_block = ""
    for idx, link in enumerate(top_17, start=1):
        num_str = f"{idx:02d}"
        links_block += f"⚡️ <a href=\"{link}\">اتصال به پروکسی اختصاصی شماره {num_str}</a>\n"

    photo_caption = (
        f"💎 <b>منتخب ۱۷ پروکسی فوق‌سریع و پایدار</b>\n"
        f"⏰ <code>{time_str}</code>\n\n"
        f"{quote}\n\n"
        f"👇 <b>جهت اتصال، روی گزینه‌های زیر کلیک کنید:</b>\n\n"
        f"{links_block}\n"
        f"🌐 <i>اتصال آزاد، پایدار و با بالاترین امنیت</i>"
    )
    print("[*] در حال ارسال تصویر و ۱۷ پروکسی برتر...")
    res_photo = send_photo_to_channel(photo, photo_caption)
    print("نتیجه ارسال تصویر:", res_photo.get("ok"))

    # پاک‌کردن فایل موقت
    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    main()
